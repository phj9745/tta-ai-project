from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from fastapi import HTTPException, UploadFile

from ...config import Settings
from ...token_store import StoredTokens, TokenStorage
from .client import (
    DRIVE_FILES_ENDPOINT,
    XLSX_MIME_TYPE,
    GoogleDriveClient,
)
from .metadata import EXAM_NUMBER_PATTERN, build_project_folder_name, extract_project_metadata
from .naming import drive_name_variants, drive_suffix_matches
from .templates import (
    SPREADSHEET_RULES,
    replace_placeholders,
)
from . import defect_reports, feature_lists, security_reports, templates, testcases
from ..excel_templates.models import DefectReportImage
from ..excel_templates.feature_list import extract_feature_list_overview

logger = logging.getLogger(__name__)


@dataclass
class _ResolvedSpreadsheet:
    rule: Mapping[str, Any]
    tokens: StoredTokens
    folder_id: str
    file_id: str
    file_name: str
    mime_type: Optional[str]
    modified_time: Optional[str]
    content: Optional[bytes] = None


class GoogleDriveService:
    """High level operations for interacting with Google Drive."""

    def __init__(
        self,
        settings: Settings,
        token_storage: TokenStorage,
        oauth_service: Any,
    ) -> None:
        self._settings = settings
        self._token_storage = token_storage
        self._oauth_service = oauth_service
        self._client = GoogleDriveClient(settings, token_storage)

    async def _get_active_tokens(self, google_id: Optional[str]) -> StoredTokens:
        self._oauth_service.ensure_credentials()
        stored_tokens = self._client.load_tokens(google_id)
        return await self._client.ensure_valid_tokens(stored_tokens)

    async def _resolve_menu_spreadsheet(
        self,
        *,
        project_id: str,
        menu_id: str,
        google_id: Optional[str],
        include_content: bool = False,
        file_id: Optional[str] = None,
    ) -> _ResolvedSpreadsheet:
        rule = SPREADSHEET_RULES.get(menu_id)
        if not rule:
            raise HTTPException(status_code=404, detail="지원하지 않는 스프레드시트 메뉴입니다.")

        active_tokens = await self._get_active_tokens(google_id)

        folder, active_tokens = await self._client.find_child_folder_by_name(
            active_tokens,
            parent_id=project_id,
            name=rule["folder_name"],
            matcher=drive_name_variants,
        )
        if folder is None or not folder.get("id"):
            raise HTTPException(status_code=404, detail=f"프로젝트에 '{rule['folder_name']}' 폴더를 찾을 수 없습니다.")

        folder_id = str(folder["id"])
        file_entry: Optional[Dict[str, Any]] = None
        if file_id:
            file_entry, active_tokens = await self._client.get_file_metadata(
                active_tokens,
                file_id=file_id,
            )
            if file_entry is None or not file_entry.get("id"):
                raise HTTPException(status_code=404, detail=f"프로젝트에 '{rule['file_suffix']}' 파일을 찾을 수 없습니다.")

            parents = file_entry.get("parents")
            if isinstance(parents, Sequence) and parents:
                parent_ids = {
                    parent.decode("utf-8") if isinstance(parent, bytes) else str(parent)
                    for parent in parents
                    if isinstance(parent, (str, bytes))
                }
                if folder_id not in parent_ids:
                    logger.warning(
                        "Drive file is outside expected folder",
                        extra={
                            "project_id": project_id,
                            "menu_id": menu_id,
                            "expected_folder_id": folder_id,
                            "file_parents": list(parent_ids),
                            "file_id": file_id,
                        },
                    )
        else:
            file_entry, active_tokens = await self._client.find_file_by_suffix(
                active_tokens,
                parent_id=folder_id,
                suffix=rule["file_suffix"],
                matcher=drive_suffix_matches,
                mime_type=XLSX_MIME_TYPE,
            )
            if file_entry is None or not file_entry.get("id"):
                raise HTTPException(status_code=404, detail=f"프로젝트에 '{rule['file_suffix']}' 파일을 찾을 수 없습니다.")

        file_id = str(file_entry["id"])
        file_name = str(file_entry.get("name", rule["file_suffix"]))
        mime_type = file_entry.get("mimeType")
        normalized_mime = mime_type if isinstance(mime_type, str) else None
        modified_time = (
            str(file_entry.get("modifiedTime"))
            if isinstance(file_entry.get("modifiedTime"), str)
            else None
        )

        content: Optional[bytes] = None
        if include_content:
            content, active_tokens = await self._client.download_file_content(
                active_tokens,
                file_id=file_id,
                mime_type=normalized_mime,
            )

        return _ResolvedSpreadsheet(
            rule=rule,
            tokens=active_tokens,
            folder_id=folder_id,
            file_id=file_id,
            file_name=file_name,
            mime_type=normalized_mime,
            modified_time=modified_time,
            content=content,
        )

    async def apply_csv_to_spreadsheet(
        self,
        *,
        project_id: str,
        menu_id: str,
        csv_text: str,
        google_id: Optional[str],
        project_overview: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        rule = SPREADSHEET_RULES.get(menu_id)
        if not rule:
            return None

        resolved = await self._resolve_menu_spreadsheet(
            project_id=project_id,
            menu_id=menu_id,
            google_id=google_id,
            include_content=True,
        )

        workbook_bytes = resolved.content
        if workbook_bytes is None:
            raise HTTPException(status_code=500, detail="스프레드시트 내용을 불러오지 못했습니다. 다시 시도해 주세요.")

        overview_value: Optional[str] = None
        try:
            populate = resolved.rule["populate"]
            if menu_id == "feature-list":
                overview_value = (
                    str(project_overview or "") if project_overview is not None else None
                )
                updated_bytes = populate(workbook_bytes, csv_text, overview_value)
            else:
                updated_bytes = populate(workbook_bytes, csv_text)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except Exception as exc:  # pragma: no cover - 안전망
            logger.exception(
                "Failed to populate spreadsheet for project",
                extra={"project_id": project_id, "menu_id": menu_id},
            )
            raise HTTPException(status_code=500, detail="엑셀 템플릿을 업데이트하지 못했습니다. 다시 시도해주세요.") from exc

        update_info, _ = await self._client.update_file_content(
            resolved.tokens,
            file_id=resolved.file_id,
            file_name=resolved.file_name,
            content=updated_bytes,
            content_type=XLSX_MIME_TYPE,
        )
        logger.info(
            "Populated project spreadsheet",
            extra={"project_id": project_id, "menu_id": menu_id, "file_id": resolved.file_id},
        )
        response: Dict[str, Any] = {
            "fileId": resolved.file_id,
            "fileName": resolved.file_name,
            "modifiedTime": update_info.get("modifiedTime") if isinstance(update_info, dict) else None,
        }
        if menu_id == "feature-list" and overview_value is not None:
            response["projectOverview"] = overview_value
        return response

    async def get_feature_list_rows(
        self,
        *,
        project_id: str,
        google_id: Optional[str],
        file_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        resolved = await self._resolve_menu_spreadsheet(
            project_id=project_id,
            menu_id="feature-list",
            google_id=google_id,
            include_content=True,
            file_id=file_id,
        )

        workbook_bytes = resolved.content
        if workbook_bytes is None:
            raise HTTPException(status_code=500, detail="기능리스트 파일을 불러오지 못했습니다. 다시 시도해 주세요.")

        _, project_overview = extract_feature_list_overview(workbook_bytes)
        sheet_title, start_row, headers, extracted_rows = feature_lists.parse_feature_list_workbook(
            workbook_bytes
        )

        return feature_lists.prepare_feature_list_response(
            file_id=resolved.file_id,
            file_name=resolved.file_name,
            sheet_name=sheet_title,
            start_row=start_row,
            headers=headers,
            rows=extracted_rows,
            modified_time=resolved.modified_time,
            project_overview=project_overview,
        )

    async def get_defect_report_rows(
        self,
        *,
        project_id: str,
        google_id: Optional[str],
        file_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        resolved = await self._resolve_menu_spreadsheet(
            project_id=project_id,
            menu_id="defect-report",
            google_id=google_id,
            include_content=True,
            file_id=file_id,
        )

        workbook_bytes = resolved.content
        if workbook_bytes is None:
            raise HTTPException(status_code=500, detail="결함 리포트 파일을 불러오지 못했습니다. 다시 시도해 주세요.")

        sheet_title, start_row, headers, rows = defect_reports.parse_defect_report_workbook(
            workbook_bytes
        )

        return defect_reports.prepare_defect_report_response(
            file_id=resolved.file_id,
            file_name=resolved.file_name,
            sheet_name=sheet_title,
            start_row=start_row,
            headers=headers,
            rows=rows,
            modified_time=resolved.modified_time,
        )

    async def get_testcase_rows(
        self,
        *,
        project_id: str,
        google_id: Optional[str],
        file_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        resolved = await self._resolve_menu_spreadsheet(
            project_id=project_id,
            menu_id="testcase-generation",
            google_id=google_id,
            include_content=True,
            file_id=file_id,
        )

        workbook_bytes = resolved.content
        if workbook_bytes is None:
            raise HTTPException(status_code=500, detail="테스트케이스 파일을 불러오지 못했습니다. 다시 시도해 주세요.")

        sheet_title, start_row, headers, extracted_rows = testcases.parse_testcase_workbook(
            workbook_bytes
        )

        return testcases.prepare_testcase_response(
            file_id=resolved.file_id,
            file_name=resolved.file_name,
            sheet_name=sheet_title,
            start_row=start_row,
            headers=headers,
            rows=extracted_rows,
            modified_time=resolved.modified_time,
        )

    async def update_feature_list_rows(
        self,
        *,
        project_id: str,
        rows: Sequence[Dict[str, str]],
        project_overview: str = "",
        google_id: Optional[str],
        file_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        resolved = await self._resolve_menu_spreadsheet(
            project_id=project_id,
            menu_id="feature-list",
            google_id=google_id,
            include_content=True,
            file_id=file_id,
        )

        workbook_bytes = resolved.content
        if workbook_bytes is None:
            raise HTTPException(status_code=500, detail="기능리스트 파일을 불러오지 못했습니다. 다시 시도해 주세요.")

        csv_text = feature_lists.build_feature_list_rows_csv(rows)

        try:
            updated_bytes = resolved.rule["populate"](
                workbook_bytes,
                csv_text,
                project_overview,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except Exception as exc:  # pragma: no cover - 안전망
            logger.exception("Failed to update feature list spreadsheet", extra={"project_id": project_id})
            raise HTTPException(status_code=500, detail="기능리스트를 업데이트하지 못했습니다. 다시 시도해 주세요.") from exc

        update_info, _ = await self._client.update_file_content(
            resolved.tokens,
            file_id=resolved.file_id,
            file_name=resolved.file_name,
            content=updated_bytes,
            content_type=XLSX_MIME_TYPE,
        )

        return {
            "fileId": resolved.file_id,
            "fileName": resolved.file_name,
            "modifiedTime": update_info.get("modifiedTime") if isinstance(update_info, dict) else None,
            "projectOverview": project_overview,
        }

    async def update_testcase_rows(
        self,
        *,
        project_id: str,
        rows: Sequence[Dict[str, str]],
        google_id: Optional[str],
        file_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        resolved = await self._resolve_menu_spreadsheet(
            project_id=project_id,
            menu_id="testcase-generation",
            google_id=google_id,
            include_content=True,
            file_id=file_id,
        )

        workbook_bytes = resolved.content
        if workbook_bytes is None:
            raise HTTPException(status_code=500, detail="테스트케이스 파일을 불러오지 못했습니다. 다시 시도해 주세요.")

        csv_text = testcases.build_testcase_rows_csv(rows)

        try:
            updated_bytes = resolved.rule["populate"](
                workbook_bytes,
                csv_text,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except Exception as exc:  # pragma: no cover - safety net
            logger.exception(
                "Failed to update testcase spreadsheet",
                extra={"project_id": project_id},
            )
            raise HTTPException(status_code=500, detail="테스트케이스를 업데이트하지 못했습니다. 다시 시도해 주세요.") from exc

        update_info, _ = await self._client.update_file_content(
            resolved.tokens,
            file_id=resolved.file_id,
            file_name=resolved.file_name,
            content=updated_bytes,
            content_type=XLSX_MIME_TYPE,
        )

        return {
            "fileId": resolved.file_id,
            "fileName": resolved.file_name,
            "modifiedTime": update_info.get("modifiedTime") if isinstance(update_info, dict) else None,
        }

    async def update_defect_report_rows(
        self,
        *,
        project_id: str,
        rows: Sequence[Dict[str, str]],
        google_id: Optional[str],
        file_id: Optional[str] = None,
        images: Optional[Mapping[int, Sequence[DefectReportImage]]] = None,
        attachment_notes: Optional[Mapping[int, Sequence[str]]] = None,
    ) -> Dict[str, Any]:
        resolved = await self._resolve_menu_spreadsheet(
            project_id=project_id,
            menu_id="defect-report",
            google_id=google_id,
            include_content=True,
            file_id=file_id,
        )

        workbook_bytes = resolved.content
        if workbook_bytes is None:
            raise HTTPException(status_code=500, detail="결함 리포트 파일을 불러오지 못했습니다. 다시 시도해 주세요.")

        csv_text = defect_reports.build_defect_report_rows_csv(rows)

        try:
            updated_bytes = resolved.rule["populate"](  # type: ignore[index]
                workbook_bytes,
                csv_text,
                images=images,
                attachment_notes=attachment_notes,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except Exception as exc:  # pragma: no cover - safety net
            logger.exception(
                "Failed to update defect report spreadsheet",
                extra={"project_id": project_id},
            )
            raise HTTPException(status_code=500, detail="결함 리포트를 업데이트하지 못했습니다. 다시 시도해 주세요.") from exc

        update_info, _ = await self._client.update_file_content(
            resolved.tokens,
            file_id=resolved.file_id,
            file_name=resolved.file_name,
            content=updated_bytes,
            content_type=XLSX_MIME_TYPE,
        )

        return {
            "fileId": resolved.file_id,
            "fileName": resolved.file_name,
            "modifiedTime": update_info.get("modifiedTime") if isinstance(update_info, dict) else None,
        }

    async def download_feature_list_workbook(
        self,
        *,
        project_id: str,
        google_id: Optional[str],
        file_id: Optional[str] = None,
    ) -> Tuple[str, bytes]:
        resolved = await self._resolve_menu_spreadsheet(
            project_id=project_id,
            menu_id="feature-list",
            google_id=google_id,
            include_content=True,
            file_id=file_id,
        )

        workbook_bytes = resolved.content
        if workbook_bytes is None:
            raise HTTPException(status_code=500, detail="기능리스트 파일을 불러오지 못했습니다. 다시 시도해 주세요.")

        return resolved.file_name, workbook_bytes

    async def download_testcase_workbook(
        self,
        *,
        project_id: str,
        google_id: Optional[str],
        file_id: Optional[str] = None,
    ) -> Tuple[str, bytes]:
        resolved = await self._resolve_menu_spreadsheet(
            project_id=project_id,
            menu_id="testcase-generation",
            google_id=google_id,
            include_content=True,
            file_id=file_id,
        )

        workbook_bytes = resolved.content
        if workbook_bytes is None:
            raise HTTPException(status_code=500, detail="테스트케이스 파일을 불러오지 못했습니다. 다시 시도해 주세요.")

        return resolved.file_name, workbook_bytes

    async def download_defect_report_workbook(
        self,
        *,
        project_id: str,
        google_id: Optional[str],
        file_id: Optional[str] = None,
    ) -> Tuple[str, bytes]:
        resolved = await self._resolve_menu_spreadsheet(
            project_id=project_id,
            menu_id="defect-report",
            google_id=google_id,
            include_content=True,
            file_id=file_id,
        )

        workbook_bytes = resolved.content
        if workbook_bytes is None:
            raise HTTPException(status_code=500, detail="결함 리포트 파일을 불러오지 못했습니다. 다시 시도해 주세요.")

        return resolved.file_name, workbook_bytes

    async def get_project_exam_number(
        self,
        *,
        project_id: str,
        google_id: Optional[str],
    ) -> str:
        """
        Retrieve the exam number (e.g. GS-B-12-3456) from the Drive project folder name.
        """
        active_tokens = await self._get_active_tokens(google_id)

        params = {"fields": "id,name"}
        data, _ = await self._client.drive_request(
            active_tokens,
            method="GET",
            path=f"{DRIVE_FILES_ENDPOINT}/{project_id}",
            params=params,
        )

        name = data.get("name")
        if not isinstance(name, str) or not name.strip():
            raise HTTPException(status_code=404, detail="프로젝트 폴더를 찾을 수 없습니다.")

        match = EXAM_NUMBER_PATTERN.search(name)
        if not match:
            raise HTTPException(status_code=404, detail="프로젝트 이름에서 시험신청 번호를 찾을 수 없습니다.")

        return match.group(0)

    async def ensure_drive_setup(self, google_id: Optional[str]) -> Dict[str, Any]:
        active_tokens = await self._get_active_tokens(google_id)

        folder, active_tokens = await self._client.find_root_folder(active_tokens, folder_name="gs")
        folder_created = False

        if folder is None:
            folder, active_tokens = await self._client.create_root_folder(
                active_tokens, folder_name="gs"
            )
            folder_created = True

        gs_folder_id = str(folder["id"])

        criteria_sheet, active_tokens, criteria_created = await security_reports.ensure_shared_criteria_file(
            self._client,
            active_tokens,
            parent_id=gs_folder_id,
        )

        projects, active_tokens = await self._client.list_child_folders(
            active_tokens, parent_id=str(folder["id"])
        )

        normalized_projects = []
        for item in projects:
            if not isinstance(item, dict):
                continue
            project_id = item.get("id")
            name = item.get("name")
            if not isinstance(project_id, str) or not isinstance(name, str):
                continue
            normalized_projects.append(
                {
                    "id": project_id,
                    "name": name,
                    "createdTime": item.get("createdTime"),
                    "modifiedTime": item.get("modifiedTime"),
                }
            )

        return {
            "folderCreated": folder_created,
            "folderId": folder["id"],
            "folderName": folder.get("name", "gs"),
            "criteria": {
                "created": criteria_created,
                "fileId": criteria_sheet.get("id"),
                "fileName": criteria_sheet.get("name"),
                "mimeType": criteria_sheet.get("mimeType"),
            },
            "projects": normalized_projects,
            "account": {
                "googleId": active_tokens.google_id,
                "displayName": active_tokens.display_name,
                "email": active_tokens.email,
            },
        }

    async def download_shared_security_criteria(
        self,
        *,
        google_id: Optional[str],
        file_name: str,
    ) -> bytes:
        active_tokens = await self._get_active_tokens(google_id)

        folder, active_tokens = await self._client.find_root_folder(active_tokens, folder_name="gs")
        if folder is None:
            folder, active_tokens = await self._client.create_root_folder(active_tokens, folder_name="gs")
        gs_folder_id = str(folder["id"])

        content, _ = await security_reports.download_shared_security_criteria(
            self._client,
            active_tokens,
            parent_id=gs_folder_id,
            file_name=file_name,
        )
        return content

    async def create_project(
        self,
        *,
        folder_id: Optional[str],
        files: Sequence[UploadFile],
        google_id: Optional[str],
    ) -> Dict[str, Any]:
        active_tokens = await self._get_active_tokens(google_id)

        parent_folder_id = folder_id
        if not parent_folder_id:
            folder, active_tokens = await self._client.find_root_folder(active_tokens, folder_name="gs")
            if folder is None:
                folder, active_tokens = await self._client.create_root_folder(active_tokens, folder_name="gs")
            parent_folder_id = str(folder["id"])

        if not files:
            raise HTTPException(status_code=422, detail="업로드할 파일이 필요합니다.")

        agreement_file = files[0]
        if not agreement_file.filename or not agreement_file.filename.lower().endswith(".docx"):
            raise HTTPException(status_code=422, detail="시험 합의서는 DOCX 파일이어야 합니다.")

        agreement_bytes = await agreement_file.read()
        metadata = extract_project_metadata(agreement_bytes)
        project_name = build_project_folder_name(metadata)
        if not project_name:
            raise HTTPException(status_code=422, detail="생성할 프로젝트 이름을 결정할 수 없습니다.")

        siblings, active_tokens = await self._client.list_child_folders(active_tokens, parent_id=parent_folder_id)
        existing_names = {
            str(item.get("name"))
            for item in siblings
            if isinstance(item, dict) and isinstance(item.get("name"), str)
        }

        unique_name = project_name
        suffix = 1
        while unique_name in existing_names:
            suffix += 1
            unique_name = f"{project_name} ({suffix})"

        project_folder, active_tokens = await self._client.create_child_folder(
            active_tokens,
            name=unique_name,
            parent_id=parent_folder_id,
        )
        project_id = str(project_folder["id"])

        active_tokens = await templates.copy_template_to_drive(
            self._client,
            active_tokens,
            parent_id=project_id,
            exam_number=metadata["exam_number"],
        )

        uploaded_files: List[Dict[str, Any]] = []

        agreement_name = agreement_file.filename or "시험 합의서.docx"
        agreement_name = replace_placeholders(agreement_name, metadata["exam_number"])
        file_info, active_tokens = await self._client.upload_file_to_folder(
            active_tokens,
            file_name=agreement_name,
            parent_id=project_id,
            content=agreement_bytes,
            content_type=agreement_file.content_type
            or "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
        uploaded_files.append(
            {
                "id": file_info.get("id"),
                "name": file_info.get("name", agreement_name),
                "size": len(agreement_bytes),
                "contentType": agreement_file.content_type
                or "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            }
        )
        await agreement_file.close()

        for upload in files[1:]:
            filename = upload.filename or "업로드된 파일.docx"
            content = await upload.read()
            file_info, active_tokens = await self._client.upload_file_to_folder(
                active_tokens,
                file_name=filename,
                parent_id=project_id,
                content=content,
                content_type=upload.content_type,
            )
            uploaded_files.append(
                {
                    "id": file_info.get("id"),
                    "name": file_info.get("name", filename),
                    "size": len(content),
                    "contentType": upload.content_type or "application/octet-stream",
                }
            )
            await upload.close()

        logger.info(
            "Created Drive project '%s' (%s) with metadata %s",
            unique_name,
            project_id,
            metadata,
        )

        return {
            "message": "새 프로젝트 폴더를 생성했습니다.",
            "project": {
                "id": project_id,
                "name": project_folder.get("name", unique_name),
                "parentId": parent_folder_id,
                "metadata": {
                    "examNumber": metadata["exam_number"],
                    "companyName": metadata["company_name"],
                    "productName": metadata["product_name"],
                },
            },
            "uploadedFiles": uploaded_files,
        }
