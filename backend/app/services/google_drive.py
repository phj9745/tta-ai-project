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
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import httpx
from docx import Document
from fastapi import HTTPException, UploadFile

from ..config import Settings
from ..token_store import StoredTokens, TokenStorage
from .oauth import GOOGLE_TOKEN_ENDPOINT, GoogleOAuthService

logger = logging.getLogger(__name__)

DRIVE_API_BASE = "https://www.googleapis.com/drive/v3"
DRIVE_FILES_ENDPOINT = "/files"
DRIVE_UPLOAD_BASE = "https://www.googleapis.com/upload/drive/v3"
DRIVE_FOLDER_MIME_TYPE = "application/vnd.google-apps.folder"
PROJECT_FOLDER_BASE_NAME = "GS-X-X-XXXX"
TEMPLATE_ROOT = Path(__file__).resolve().parents[2] / "템플릿"
PLACEHOLDER_PATTERNS: Tuple[str, ...] = (
    "GS-B-XX-XXXX",
    "GS-B-2X-XXXX",
    "GS-X-X-XXXX",
)
EXAM_NUMBER_PATTERN = re.compile(r"GS-[A-Z]-\d{2}-\d{4}")


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
                elif normalized_label in {"신청기업(기관)명", "신청기업(기관)명(국문)"}:
                    company_name = stripped_value.split("\n")[0].strip()
                elif normalized_label.startswith("제품명및버전"):
                    product_name = stripped_value.split("\n")[0].strip()

        for table in document.tables:
            cells: List[str] = []
            for row in table.rows:
                if len(row.cells) < 2:
                    continue
                cells.append(row.cells[0].text.strip())
                cells.append(row.cells[1].text.strip())
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
            raise HTTPException(status_code=422, detail="신청 기업(기관)명을 찾을 수 없습니다.")

        if not product_name:
            raise HTTPException(status_code=422, detail="제품명 및 버전을 찾을 수 없습니다.")

        return {
            "exam_number": exam_number.strip(),
            "company_name": company_name.strip(),
            "product_name": product_name.strip(),
        }

    @staticmethod
    def _build_project_folder_name(metadata: Dict[str, str]) -> str:
        parts = [
            metadata.get("exam_number", "").strip(),
            metadata.get("company_name", "").strip(),
            metadata.get("product_name", "").strip(),
        ]
        return " ".join(part for part in parts if part)

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

    async def _copy_template_to_drive(
        self,
        tokens: StoredTokens,
        *,
        parent_id: str,
        exam_number: str,
    ) -> StoredTokens:
        if not TEMPLATE_ROOT.exists():
            raise HTTPException(status_code=500, detail="템플릿 폴더를 찾을 수 없습니다.")

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

                data = response.json()
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

    async def ensure_drive_setup(self, google_id: Optional[str]) -> Dict[str, Any]:
        self._oauth_service.ensure_credentials()
        stored_tokens = self._load_tokens(google_id)
        active_tokens = await self._ensure_valid_tokens(stored_tokens)

        folder, active_tokens = await self._find_root_folder(active_tokens, folder_name="gs")
        folder_created = False

        if folder is None:
            folder, active_tokens = await self._create_root_folder(active_tokens, folder_name="gs")
            folder_created = True

        projects, active_tokens = await self._list_child_folders(active_tokens, parent_id=str(folder["id"]))

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
