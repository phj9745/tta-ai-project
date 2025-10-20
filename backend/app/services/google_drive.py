from __future__ import annotations

import io
import json
import logging
import mimetypes
import os
import re
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple, TypedDict

import httpx
from docx import Document
from fastapi import HTTPException, UploadFile
from openpyxl import Workbook

from ..config import Settings
from ..token_store import StoredTokens, TokenStorage
from .excel_templates import (
    populate_defect_report,
    populate_feature_list,
    populate_testcase_list,
)
from .oauth import GOOGLE_TOKEN_ENDPOINT, GoogleOAuthService

logger = logging.getLogger(__name__)

DRIVE_API_BASE = "https://www.googleapis.com/drive/v3"
DRIVE_FILES_ENDPOINT = "/files"
DRIVE_UPLOAD_BASE = "https://www.googleapis.com/upload/drive/v3"
DRIVE_FOLDER_MIME_TYPE = "application/vnd.google-apps.folder"
GOOGLE_SHEETS_MIME_TYPE = "application/vnd.google-apps.spreadsheet"
XLSX_MIME_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
PROJECT_FOLDER_BASE_NAME = "GS-X-X-XXXX"
TEMPLATE_ROOT = Path(__file__).resolve().parents[2] / "template"
PLACEHOLDER_PATTERNS: Tuple[str, ...] = (
    "GS-B-XX-XXXX",
    "GS-B-2X-XXXX",
    "GS-X-X-XXXX",
)
EXAM_NUMBER_PATTERN = re.compile(r"GS-[A-Z]-\d{2}-\d{4}")


_SHARED_CRITERIA_FILE_CANDIDATES: Tuple[str, ...] = (
    "보안성 결함판단기준표 v1.0.xlsx",
    "결함판단기준표 v1.0.xlsx",
    "결함 판단 기준표 v1.0.xlsx",
    "결함 판단기준표 v1.0.xlsx",
    "공유 결함판단기준표 v1.0.xlsx",
    "공유 결함 판단 기준표 v1.0.xlsx",
)


def _normalize_shared_criteria_name(name: str) -> str:
    base = name.strip().lower()
    if base.endswith(".xlsx"):
        base = base[:-5]
    return re.sub(r"\s+", "", base)


_SHARED_CRITERIA_NORMALIZED_NAMES = {
    _normalize_shared_criteria_name(candidate) for candidate in _SHARED_CRITERIA_FILE_CANDIDATES
}
_PREFERRED_SHARED_CRITERIA_FILE_NAME = _SHARED_CRITERIA_FILE_CANDIDATES[0]


def _is_shared_criteria_candidate(filename: str) -> bool:
    """
    템플릿 파일명이 공유 결함판단기준표 후보들과 동일(공백/대소문자/확장자 무시)한지 판정.
    프로젝트 폴더 복사에서 제외하기 위해 사용.
    """
    try:
        normalized = _normalize_shared_criteria_name(filename)
    except Exception:
        return False
    return normalized in _SHARED_CRITERIA_NORMALIZED_NAMES


class _SpreadsheetRule(TypedDict):
    folder_name: str
    file_suffix: str
    populate: Any


_SPREADSHEET_RULES: Dict[str, _SpreadsheetRule] = {
    "feature-list": {
        "folder_name": "가.계획",
        "file_suffix": "기능리스트 v1.0.xlsx",
        "populate": populate_feature_list,
    },
    "testcase-generation": {
        "folder_name": "나.설계",
        "file_suffix": "테스트케이스.xlsx",
        "populate": populate_testcase_list,
    },
    "defect-report": {
        "folder_name": "다.수행",
        "file_suffix": "결함리포트 v1.0.xlsx",
        "populate": populate_defect_report,
    },
}


class GoogleDriveService:
    """High level operations for interacting with Google Drive."""

    def __init__(
        self,
        settings: Settings,
        token_storage: TokenStorage,
        oauth_service: GoogleOAuthService,
    ) -> None:
        self._settings = settings
        self._token_storage = token_storage
        self._oauth_service = oauth_service

    @staticmethod
    def _normalize_label(value: str) -> str:
        return re.sub(r"\s+", "", value or "")

    @staticmethod
    def _extract_project_metadata(file_bytes: bytes) -> Dict[str, str]:
        try:
            document = Document(io.BytesIO(file_bytes))
        except Exception as exc:  # pragma: no cover - library level validation
            raise HTTPException(status_code=422, detail="시험 합의서 파일을 읽지 못했습니다.") from exc

        exam_number: Optional[str] = None
        company_name: Optional[str] = None
        product_name: Optional[str] = None

        def _extract_from_cells(cells: Iterable[str]) -> None:
            nonlocal exam_number, company_name, product_name
            cell_iter = iter(cells)
            for label, value in zip(cell_iter, cell_iter):
                normalized_label = GoogleDriveService._normalize_label(label)
                stripped_value = value.strip()
                if not stripped_value:
                    continue
                if normalized_label == "시험신청번호":
                    match = EXAM_NUMBER_PATTERN.search(stripped_value)
                    if match:
                        exam_number = match.group(0)
                elif normalized_label == "제조자":
                    company_name = stripped_value
                elif normalized_label.startswith("제품명및버전"):
                    lines = [line.strip() for line in stripped_value.split('\n') if line.strip()]
                    if lines:
                        last_line = lines[-1]
                        if ":" in last_line:
                            product_name = last_line.split(":", 1)[1].strip()
                        else:
                            product_name = last_line

        for table in document.tables:
            cells: List[str] = []
            for row in table.rows:
                if len(row.cells) >= 2:
                    if row.cells[0].text.strip() and row.cells[1].text.strip():
                         cells.append(row.cells[0].text.strip())
                         cells.append(row.cells[1].text.strip())
                    if len(row.cells) >= 4 and row.cells[2].text.strip() and row.cells[3].text.strip():
                         cells.append(row.cells[2].text.strip())
                         cells.append(row.cells[3].text.strip())

            if cells:
                _extract_from_cells(cells)

        if exam_number is None:
            combined_text = "\n".join(
                paragraph.text.strip()
                for paragraph in document.paragraphs
                if paragraph.text and paragraph.text.strip()
            )
            match = EXAM_NUMBER_PATTERN.search(combined_text)
            if match:
                exam_number = match.group(0)

        if not exam_number:
            raise HTTPException(status_code=422, detail="시험신청 번호를 찾을 수 없습니다.")

        if not company_name:
            raise HTTPException(status_code=422, detail="제조자(업체명)를 찾을 수 없습니다.")

        if not product_name:
            raise HTTPException(status_code=422, detail="제품명 및 버전을 찾을 수 없습니다.")

        return {
            "exam_number": exam_number.strip(),
            "company_name": company_name.strip(),
            "product_name": product_name.strip(),
        }

    @staticmethod
    def _build_project_folder_name(metadata: Dict[str, str]) -> str:
        exam_number = metadata.get("exam_number", "").strip()
        company_name = metadata.get("company_name", "").strip()
        product_name = metadata.get("product_name", "").strip()

        return f"[{exam_number}] {company_name} - {product_name}"

    @staticmethod
    def _replace_placeholders(text: str, exam_number: str) -> str:
        result = text
        for placeholder in PLACEHOLDER_PATTERNS:
            result = result.replace(placeholder, exam_number)
        return result

    @staticmethod
    def _prepare_template_file_content(path: Path, exam_number: str) -> bytes:
        raw_bytes = path.read_bytes()
        extension = path.suffix.lower()
        if extension in {".docx", ".xlsx", ".pptx"}:
            raw_bytes = GoogleDriveService._replace_in_office_document(raw_bytes, exam_number)
        return raw_bytes

    @staticmethod
    def _replace_in_office_document(data: bytes, exam_number: str) -> bytes:
        original = io.BytesIO(data)
        updated = io.BytesIO()
        with zipfile.ZipFile(original, "r") as source_zip:
            with zipfile.ZipFile(updated, "w") as target_zip:
                for item in source_zip.infolist():
                    content = source_zip.read(item.filename)
                    try:
                        decoded = content.decode("utf-8")
                    except UnicodeDecodeError:
                        target_zip.writestr(item, content)
                        continue
                    replaced = GoogleDriveService._replace_placeholders(decoded, exam_number)
                    target_zip.writestr(item, replaced.encode("utf-8"))
        return updated.getvalue()

    @staticmethod
    def _guess_mime_type(path: Path) -> str:
        mime_type, _ = mimetypes.guess_type(path.name)
        return mime_type or "application/octet-stream"

    @staticmethod
    def _build_default_shared_criteria_workbook() -> bytes:
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "결함판단기준"
        headers = [
            "Invicti 결과",
            "결함 요약",
            "결함정도",
            "발생빈도",
            "품질특성",
            "결함 설명",
            "결함 제외 여부",
        ]
        sheet.append(headers)
        buffer = io.BytesIO()
        workbook.save(buffer)
        return buffer.getvalue()

    @staticmethod
    def _load_shared_criteria_template_bytes() -> bytes:
        for candidate in _SHARED_CRITERIA_FILE_CANDIDATES:
            template_path = TEMPLATE_ROOT / candidate
            if template_path.exists():
                return template_path.read_bytes()
        logger.warning(
            "Shared criteria template not found in template folder; generating a default workbook."
        )
        return GoogleDriveService._build_default_shared_criteria_workbook()

    async def _copy_template_to_drive(
        self,
        tokens: StoredTokens,
        *,
        parent_id: str,
        exam_number: str,
    ) -> StoredTokens:
        if not TEMPLATE_ROOT.exists():
            raise HTTPException(status_code=500, detail="template 폴더를 찾을 수 없습니다.")

        path_to_folder_id: Dict[Path, str] = {TEMPLATE_ROOT: parent_id}
        for root_dir, dirnames, filenames in os.walk(TEMPLATE_ROOT):
            current_path = Path(root_dir)
            drive_parent_id = path_to_folder_id[current_path]

            for dirname in sorted(dirnames):
                local_dir = current_path / dirname
                folder_name = self._replace_placeholders(dirname, exam_number)
                folder, tokens = await self._create_child_folder(
                    tokens,
                    name=folder_name,
                    parent_id=drive_parent_id,
                )
                path_to_folder_id[local_dir] = str(folder["id"])

            for filename in sorted(filenames):
                # ✅ 공유 결함판단기준표는 프로젝트 폴더에 복사하지 않음
                if _is_shared_criteria_candidate(filename):
                    logger.info("Skip copying shared criteria into project: %s", filename)
                    continue

                local_file = current_path / filename
                target_name = self._replace_placeholders(filename, exam_number)
                content = self._prepare_template_file_content(local_file, exam_number)
                mime_type = self._guess_mime_type(local_file)
                _, tokens = await self._upload_file_to_folder(
                    tokens,
                    file_name=target_name,
                    parent_id=drive_parent_id,
                    content=content,
                    content_type=mime_type,
                )

        return tokens

    def _load_tokens(self, google_id: Optional[str]) -> StoredTokens:
        if google_id:
            stored = self._token_storage.load_by_google_id(google_id)
            if stored is None:
                raise HTTPException(status_code=404, detail="요청한 Google 계정 토큰을 찾을 수 없습니다.")
            return stored

        accounts = self._token_storage.list_accounts()
        if not accounts:
            raise HTTPException(status_code=404, detail="저장된 Google 계정이 없습니다. 먼저 로그인하세요.")

        for account in accounts:
            stored = self._token_storage.load_by_google_id(account.google_id)
            if stored is not None:
                return stored

        raise HTTPException(status_code=404, detail="저장된 Google 계정 토큰을 찾을 수 없습니다.")

    def _is_token_expired(self, tokens: StoredTokens) -> bool:
        if tokens.expires_in <= 0:
            return False

        expires_at = tokens.saved_at + timedelta(seconds=tokens.expires_in)
        now = datetime.now(timezone.utc)
        return now >= expires_at - timedelta(minutes=1)

    async def _refresh_access_token(self, tokens: StoredTokens) -> StoredTokens:
        if not tokens.refresh_token:
            raise HTTPException(status_code=401, detail="Google 인증이 만료되었습니다. 다시 로그인해주세요.")

        data = {
            "client_id": self._settings.client_id,
            "client_secret": self._settings.client_secret,
            "refresh_token": tokens.refresh_token,
            "grant_type": "refresh_token",
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(GOOGLE_TOKEN_ENDPOINT, data=data)

        if response.is_error:
            logger.error("Google token refresh failed: %s", response.text)
            raise HTTPException(status_code=502, detail="Google 토큰을 새로고침하지 못했습니다. 다시 로그인해주세요.")

        payload = response.json()
        access_token = payload.get("access_token")
        if not isinstance(access_token, str) or not access_token:
            logger.error("Google token refresh response missing access_token: %s", payload)
            raise HTTPException(status_code=502, detail="Google 토큰을 새로고침하지 못했습니다. 다시 로그인해주세요.")

        merged_payload: Dict[str, Any] = {
            "access_token": access_token,
            "refresh_token": payload.get("refresh_token") or tokens.refresh_token,
            "scope": payload.get("scope", tokens.scope),
            "token_type": payload.get("token_type", tokens.token_type),
            "expires_in": int(payload.get("expires_in", tokens.expires_in)),
        }

        return self._token_storage.save(
            google_id=tokens.google_id,
            display_name=tokens.display_name,
            email=tokens.email,
            payload=merged_payload,
        )

    async def _ensure_valid_tokens(self, tokens: StoredTokens) -> StoredTokens:
        if self._is_token_expired(tokens):
            return await self._refresh_access_token(tokens)
        return tokens

    async def _drive_request(
        self,
        tokens: StoredTokens,
        *,
        method: str,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        json_body: Optional[Dict[str, Any]] = None,
    ) -> Tuple[Dict[str, Any], StoredTokens]:
        current_tokens = tokens

        for attempt in range(2):
            headers = {
                "Authorization": f"Bearer {current_tokens.access_token}",
                "Accept": "application/json",
            }

            async with httpx.AsyncClient(timeout=10.0, base_url=DRIVE_API_BASE) as client:
                response = await client.request(
                    method,
                    path,
                    params=params,
                    json=json_body,
                    headers=headers,
                )

            if response.status_code != 401:
                if response.is_error:
                    logger.error("Google Drive API %s %s failed: %s", method, path, response.text)
                    raise HTTPException(
                        status_code=502,
                        detail="Google Drive API 요청이 실패했습니다. 잠시 후 다시 시도해주세요.",
                    )

                data = response.json() if response.text else {}
                return data, current_tokens

            if attempt == 0:
                current_tokens = await self._refresh_access_token(current_tokens)
                continue

        raise HTTPException(status_code=401, detail="Google Drive 인증이 만료되었습니다. 다시 로그인해주세요.")

    async def _find_root_folder(
        self, tokens: StoredTokens, *, folder_name: str
    ) -> Tuple[Optional[Dict[str, Any]], StoredTokens]:
        escaped_name = folder_name.replace("'", "\\'")
        query = (
            f"name = '{escaped_name}' and "
            f"mimeType = '{DRIVE_FOLDER_MIME_TYPE}' and "
            "'root' in parents and trashed = false"
        )
        params = {
            "q": query,
            "fields": "files(id,name)",
            "pageSize": 1,
            "spaces": "drive",
        }

        data, updated_tokens = await self._drive_request(
            tokens,
            method="GET",
            path=DRIVE_FILES_ENDPOINT,
            params=params,
        )

        files = data.get("files")
        if isinstance(files, Sequence) and files:
            first = files[0]
            if isinstance(first, dict):
                return first, updated_tokens

        return None, updated_tokens

    async def _create_root_folder(
        self, tokens: StoredTokens, *, folder_name: str
    ) -> Tuple[Dict[str, Any], StoredTokens]:
        body = {
            "name": folder_name,
            "mimeType": DRIVE_FOLDER_MIME_TYPE,
            "parents": ["root"],
        }
        params = {"fields": "id,name"}

        data, updated_tokens = await self._drive_request(
            tokens,
            method="POST",
            path=DRIVE_FILES_ENDPOINT,
            params=params,
            json_body=body,
        )

        if not isinstance(data, dict) or "id" not in data:
            logger.error("Google Drive create folder response missing id: %s", data)
            raise HTTPException(status_code=502, detail="Google Drive 폴더를 생성하지 못했습니다. 다시 시도해주세요.")

        return data, updated_tokens

    async def _create_child_folder(
        self, tokens: StoredTokens, *, name: str, parent_id: str
    ) -> Tuple[Dict[str, Any], StoredTokens]:
        body = {
            "name": name,
            "mimeType": DRIVE_FOLDER_MIME_TYPE,
            "parents": [parent_id],
        }
        params = {"fields": "id,name,parents"}

        data, updated_tokens = await self._drive_request(
            tokens,
            method="POST",
            path=DRIVE_FILES_ENDPOINT,
            params=params,
            json_body=body,
        )

        if not isinstance(data, dict) or "id" not in data:
            logger.error("Google Drive create child folder response missing id: %s", data)
            raise HTTPException(status_code=502, detail="Google Drive 하위 폴더를 생성하지 못했습니다. 다시 시도해주세요.")

        return data, updated_tokens

    async def _upload_file_to_folder(
        self,
        tokens: StoredTokens,
        *,
        file_name: str,
        parent_id: str,
        content: bytes,
        content_type: Optional[str] = None,
    ) -> Tuple[Dict[str, Any], StoredTokens]:
        active_tokens = tokens

        for attempt in range(2):
            headers = {
                "Authorization": f"Bearer {active_tokens.access_token}",
            }
            metadata = {"name": file_name, "parents": [parent_id]}
            files = {
                "metadata": (
                    "metadata",
                    json.dumps(metadata),
                    "application/json; charset=UTF-8",
                ),
                "file": (
                    file_name,
                    content,
                    content_type or "application/pdf",
                ),
            }

            async with httpx.AsyncClient(timeout=30.0, base_url=DRIVE_UPLOAD_BASE) as client:
                response = await client.post(
                    f"{DRIVE_FILES_ENDPOINT}?uploadType=multipart&fields=id,name,parents",
                    headers=headers,
                    files=files,
                )

            if response.status_code == 401 and attempt == 0:
                active_tokens = await self._refresh_access_token(active_tokens)
                continue

            if response.is_error:
                logger.error("Google Drive file upload failed for %s: %s", file_name, response.text)
                raise HTTPException(
                    status_code=502,
                    detail="파일을 Google Drive에 업로드하지 못했습니다. 잠시 후 다시 시도해주세요.",
                )

            data = response.json()
            if not isinstance(data, dict) or "id" not in data:
                logger.error("Google Drive file upload response missing id: %s", data)
                raise HTTPException(status_code=502, detail="업로드한 파일의 ID를 확인하지 못했습니다. 다시 시도해주세요.")

            return data, active_tokens

        raise HTTPException(status_code=401, detail="Google Drive 인증이 만료되었습니다. 다시 로그인해주세요.")

    async def _download_file_content(
        self,
        tokens: StoredTokens,
        *,
        file_id: str,
        mime_type: Optional[str] = None,
    ) -> Tuple[bytes, StoredTokens]:
        active_tokens = tokens
        for attempt in range(2):
            headers = {
                "Authorization": f"Bearer {active_tokens.access_token}",
            }
            if mime_type == GOOGLE_SHEETS_MIME_TYPE:
                path = f"{DRIVE_FILES_ENDPOINT}/{file_id}/export"
                params = {"mimeType": XLSX_MIME_TYPE}
            else:
                path = f"{DRIVE_FILES_ENDPOINT}/{file_id}"
                params = {"alt": "media"}

            async with httpx.AsyncClient(timeout=30.0, base_url=DRIVE_API_BASE) as client:
                response = await client.get(
                    path,
                    params=params,
                    headers=headers,
                )

            if response.status_code == 401 and attempt == 0:
                active_tokens = await self._refresh_access_token(active_tokens)
                continue

            if response.is_error:
                logger.error("Google Drive file download failed for %s: %s", file_id, response.text)
                raise HTTPException(
                    status_code=502,
                    detail="Google Drive에서 파일을 다운로드하지 못했습니다. 잠시 후 다시 시도해주세요.",
                )

            return response.content, active_tokens

        raise HTTPException(status_code=401, detail="Google Drive 인증이 만료되었습니다. 다시 로그인해주세요.")

    async def _update_file_content(
        self,
        tokens: StoredTokens,
        *,
        file_id: str,
        file_name: str,
        content: bytes,
        content_type: str,
    ) -> Tuple[Dict[str, Any], StoredTokens]:
        active_tokens = tokens
        for attempt in range(2):
            headers = {
                "Authorization": f"Bearer {active_tokens.access_token}",
            }
            metadata = {"name": file_name}
            files = {
                "metadata": (
                    "metadata",
                    json.dumps(metadata),
                    "application/json; charset=UTF-8",
                ),
                "file": (
                    file_name,
                    content,
                    content_type,
                ),
            }

            async with httpx.AsyncClient(timeout=30.0, base_url=DRIVE_UPLOAD_BASE) as client:
                response = await client.patch(
                    f"{DRIVE_FILES_ENDPOINT}/{file_id}?uploadType=multipart&fields=id,name,modifiedTime",
                    headers=headers,
                    files=files,
                )

            if response.status_code == 401 and attempt == 0:
                active_tokens = await self._refresh_access_token(active_tokens)
                continue

            if response.is_error:
                logger.error("Google Drive file update failed for %s: %s", file_id, response.text)
                raise HTTPException(
                    status_code=502,
                    detail="Google Drive 파일을 업데이트하지 못했습니다. 잠시 후 다시 시도해주세요.",
                )

            data = response.json()
            if not isinstance(data, dict) or "id" not in data:
                logger.error("Google Drive file update response missing id: %s", data)
                raise HTTPException(status_code=502, detail="업데이트된 파일 정보를 확인하지 못했습니다. 다시 시도해주세요.")

            return data, active_tokens

        raise HTTPException(status_code=401, detail="Google Drive 인증이 만료되었습니다. 다시 로그인해주세요.")

    async def apply_csv_to_spreadsheet(
        self,
        *,
        project_id: str,
        menu_id: str,
        csv_text: str,
        google_id: Optional[str],
    ) -> None:
        rule = _SPREADSHEET_RULES.get(menu_id)
        if not rule:
            return

        self._oauth_service.ensure_credentials()
        stored_tokens = self._load_tokens(google_id)
        active_tokens = await self._ensure_valid_tokens(stored_tokens)

        folder, active_tokens = await self._find_child_folder_by_name(
            active_tokens,
            parent_id=project_id,
            name=rule["folder_name"],
        )
        if folder is None or not folder.get("id"):
            raise HTTPException(status_code=404, detail=f"프로젝트에 '{rule['folder_name']}' 폴더를 찾을 수 없습니다.")

        folder_id = str(folder["id"])
        file_entry, active_tokens = await self._find_file_by_suffix(
            active_tokens,
            parent_id=folder_id,
            suffix=rule["file_suffix"],
            mime_type=XLSX_MIME_TYPE,
        )
        if file_entry is None or not file_entry.get("id"):
            raise HTTPException(status_code=404, detail=f"프로젝트에 '{rule['file_suffix']}' 파일을 찾을 수 없습니다.")

        file_id = str(file_entry["id"])
        file_name = str(file_entry.get("name", rule["file_suffix"]))

        workbook_bytes, active_tokens = await self._download_file_content(
            active_tokens,
            file_id=file_id,
            mime_type=file_entry.get("mimeType"),
        )

        try:
            updated_bytes = rule["populate"](workbook_bytes, csv_text)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except Exception as exc:  # pragma: no cover - 안전망
            logger.exception(
                "Failed to populate spreadsheet for project", extra={"project_id": project_id, "menu_id": menu_id}
            )
            raise HTTPException(status_code=500, detail="엑셀 템플릿을 업데이트하지 못했습니다. 다시 시도해주세요.") from exc

        await self._update_file_content(
            active_tokens,
            file_id=file_id,
            file_name=file_name,
            content=updated_bytes,
            content_type=XLSX_MIME_TYPE,
        )
        logger.info(
            "Populated project spreadsheet", extra={"project_id": project_id, "menu_id": menu_id, "file_id": file_id}
        )

    async def get_project_exam_number(
        self,
        *,
        project_id: str,
        google_id: Optional[str],
    ) -> str:
        """
        Retrieve the exam number (e.g. GS-B-12-3456) from the Drive project folder name.
        """
        self._oauth_service.ensure_credentials()
        stored_tokens = self._load_tokens(google_id)
        active_tokens = await self._ensure_valid_tokens(stored_tokens)

        params = {"fields": "id,name"}
        data, _ = await self._drive_request(
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

    async def _ensure_shared_criteria_file(
        self,
        tokens: StoredTokens,
        *,
        parent_id: str,
        preferred_names: Optional[Sequence[str]] = None,
    ) -> Tuple[Dict[str, Any], StoredTokens, bool]:
        normalized_candidates = set(_SHARED_CRITERIA_NORMALIZED_NAMES)
        upload_name = _PREFERRED_SHARED_CRITERIA_FILE_NAME
        if preferred_names:
            normalized_candidates.update(
                _normalize_shared_criteria_name(name)
                for name in preferred_names
                if isinstance(name, str) and name.strip()
            )
            first_valid = next(
                (name.strip() for name in preferred_names if isinstance(name, str) and name.strip()),
                None,
            )
            if first_valid:
                upload_name = first_valid

        files, active_tokens = await self._list_child_files(tokens, parent_id=parent_id)
        for entry in files:
            if not isinstance(entry, dict):
                continue
            name = entry.get("name")
            if not isinstance(name, str):
                continue
            normalized_name = _normalize_shared_criteria_name(name)
            if normalized_name not in normalized_candidates:
                continue
            mime_type = entry.get("mimeType")
            if isinstance(mime_type, str) and mime_type not in {XLSX_MIME_TYPE, GOOGLE_SHEETS_MIME_TYPE}:
                logger.warning(
                    "Ignoring shared criteria candidate with unsupported mime type: %s (%s)",
                    name,
                    mime_type,
                )
                continue
            normalized_entry = dict(entry)
            normalized_entry["mimeType"] = mime_type if isinstance(mime_type, str) else None
            return normalized_entry, active_tokens, False

        content = GoogleDriveService._load_shared_criteria_template_bytes()
        uploaded_entry, updated_tokens = await self._upload_file_to_folder(
            active_tokens,
            file_name=upload_name,
            parent_id=parent_id,
            content=content,
            content_type=XLSX_MIME_TYPE,
        )
        uploaded_entry = dict(uploaded_entry)
        uploaded_entry.setdefault("name", upload_name)
        uploaded_entry["mimeType"] = XLSX_MIME_TYPE
        logger.info(
            "Uploaded shared criteria template to gs folder: %s",
            uploaded_entry.get("name"),
        )
        return uploaded_entry, updated_tokens, True

    async def download_shared_security_criteria(
        self,
        *,
        google_id: Optional[str],
        file_name: str,
    ) -> bytes:
        self._oauth_service.ensure_credentials()
        stored_tokens = self._load_tokens(google_id)
        active_tokens = await self._ensure_valid_tokens(stored_tokens)

        folder, active_tokens = await self._find_root_folder(active_tokens, folder_name="gs")
        if folder is None:
            folder, active_tokens = await self._create_root_folder(active_tokens, folder_name="gs")
        gs_folder_id = str(folder["id"])

        file_entry, active_tokens, _ = await self._ensure_shared_criteria_file(
            active_tokens,
            parent_id=gs_folder_id,
            preferred_names=(file_name,),
        )

        file_id = file_entry.get("id")
        if not isinstance(file_id, str):
            logger.error("Shared criteria entry missing id: %s", file_entry)
            raise HTTPException(status_code=502, detail="결함 판단 기준표 ID를 확인할 수 없습니다.")

        content, _ = await self._download_file_content(
            active_tokens,
            file_id=file_id,
            mime_type=file_entry.get("mimeType"),
        )
        return content

    async def _list_child_folders(
        self,
        tokens: StoredTokens,
        *,
        parent_id: str,
    ) -> Tuple[Sequence[Dict[str, Any]], StoredTokens]:
        query = (
            f"'{parent_id}' in parents and "
            f"mimeType = '{DRIVE_FOLDER_MIME_TYPE}' and trashed = false"
        )
        params = {
            "q": query,
            "fields": "files(id,name,createdTime,modifiedTime)",
            "orderBy": "name_natural",
            "spaces": "drive",
            "pageSize": 100,
        }

        data, updated_tokens = await self._drive_request(
            tokens,
            method="GET",
            path=DRIVE_FILES_ENDPOINT,
            params=params,
        )

        files = data.get("files")
        if isinstance(files, Sequence):
            return files, updated_tokens

        return [], updated_tokens

    async def _list_child_files(
        self,
        tokens: StoredTokens,
        *,
        parent_id: str,
        mime_type: Optional[str] = None,
    ) -> Tuple[Sequence[Dict[str, Any]], StoredTokens]:
        clauses = [f"'{parent_id}' in parents", "trashed = false"]
        if mime_type:
            clauses.append(f"mimeType = '{mime_type}'")
        params = {
            "q": " and ".join(clauses),
            "fields": "files(id,name,mimeType,modifiedTime)",
            "orderBy": "name_natural",
            "spaces": "drive",
            "pageSize": 100,
        }

        data, updated_tokens = await self._drive_request(
            tokens,
            method="GET",
            path=DRIVE_FILES_ENDPOINT,
            params=params,
        )

        files = data.get("files")
        if isinstance(files, Sequence):
            return files, updated_tokens

        return [], updated_tokens

    async def _find_child_folder_by_name(
        self,
        tokens: StoredTokens,
        *,
        parent_id: str,
        name: str,
    ) -> Tuple[Optional[Dict[str, Any]], StoredTokens]:
        folders, updated_tokens = await self._list_child_folders(tokens, parent_id=parent_id)
        for folder in folders:
            if not isinstance(folder, dict):
                continue
            folder_name = folder.get("name")
            if isinstance(folder_name, str) and folder_name == name:
                return folder, updated_tokens
        return None, updated_tokens

    async def _find_file_by_suffix(
        self,
        tokens: StoredTokens,
        *,
        parent_id: str,
        suffix: str,
        mime_type: Optional[str] = None,
    ) -> Tuple[Optional[Dict[str, Any]], StoredTokens]:
        files, updated_tokens = await self._list_child_files(tokens, parent_id=parent_id, mime_type=mime_type)
        normalized_suffix = suffix.strip()
        for entry in files:
            if not isinstance(entry, dict):
                continue
            name = entry.get("name")
            if isinstance(name, str) and name.endswith(normalized_suffix):
                return entry, updated_tokens
        return None, updated_tokens

    async def _find_file_by_name(
        self,
        tokens: StoredTokens,
        *,
        parent_id: str,
        name: str,
        mime_type: Optional[str] = None,
    ) -> Tuple[Optional[Dict[str, Any]], StoredTokens]:
        files, updated_tokens = await self._list_child_files(
            tokens, parent_id=parent_id, mime_type=mime_type
        )
        normalized_name = name.strip()
        for entry in files:
            if not isinstance(entry, dict):
                continue
            file_name = entry.get("name")
            if isinstance(file_name, str) and file_name.strip() == normalized_name:
                return entry, updated_tokens
        return None, updated_tokens

    async def ensure_drive_setup(self, google_id: Optional[str]) -> Dict[str, Any]:
        self._oauth_service.ensure_credentials()
        stored_tokens = self._load_tokens(google_id)
        active_tokens = await self._ensure_valid_tokens(stored_tokens)

        folder, active_tokens = await self._find_root_folder(active_tokens, folder_name="gs")
        folder_created = False

        if folder is None:
            folder, active_tokens = await self._create_root_folder(
                active_tokens, folder_name="gs"
            )
            folder_created = True

        gs_folder_id = str(folder["id"])

        criteria_sheet, active_tokens, criteria_created = await self._ensure_shared_criteria_file(
            active_tokens,
            parent_id=gs_folder_id,
        )

        projects, active_tokens = await self._list_child_folders(
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

    async def create_project(
        self,
        *,
        folder_id: Optional[str],
        files: List[UploadFile],
        google_id: Optional[str],
    ) -> Dict[str, Any]:
        self._oauth_service.ensure_credentials()
        stored_tokens = self._load_tokens(google_id)
        active_tokens = await self._ensure_valid_tokens(stored_tokens)

        parent_folder_id = folder_id
        if not parent_folder_id:
            folder, active_tokens = await self._find_root_folder(active_tokens, folder_name="gs")
            if folder is None:
                folder, active_tokens = await self._create_root_folder(active_tokens, folder_name="gs")
            parent_folder_id = str(folder["id"])

        agreement_file = files[0]
        if not agreement_file.filename or not agreement_file.filename.lower().endswith(".docx"):
            raise HTTPException(status_code=422, detail="시험 합의서는 DOCX 파일이어야 합니다.")

        agreement_bytes = await agreement_file.read()
        metadata = self._extract_project_metadata(agreement_bytes)
        project_name = self._build_project_folder_name(metadata)
        if not project_name:
            raise HTTPException(status_code=422, detail="생성할 프로젝트 이름을 결정할 수 없습니다.")

        siblings, active_tokens = await self._list_child_folders(active_tokens, parent_id=parent_folder_id)
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

        project_folder, active_tokens = await self._create_child_folder(
            active_tokens,
            name=unique_name,
            parent_id=parent_folder_id,
        )
        project_id = str(project_folder["id"])

        active_tokens = await self._copy_template_to_drive(
            active_tokens,
            parent_id=project_id,
            exam_number=metadata["exam_number"],
        )

        uploaded_files: List[Dict[str, Any]] = []

        agreement_name = agreement_file.filename or "시험 합의서.docx"
        agreement_name = self._replace_placeholders(agreement_name, metadata["exam_number"])
        file_info, active_tokens = await self._upload_file_to_folder(
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
            file_info, active_tokens = await self._upload_file_to_folder(
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
