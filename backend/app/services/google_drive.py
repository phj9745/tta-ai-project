from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Sequence, Tuple

import httpx
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
PROJECT_SUBFOLDERS = [
    "0. 사전 자료",
    "1. 형상 사진",
    "2. 기능리스트",
    "3. 테스트케이스",
    "4. 성능 시험",
    "5. 보안성 시험",
    "6. 결함리포트",
    "7. 산출물",
]


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

        siblings, active_tokens = await self._list_child_folders(active_tokens, parent_id=parent_folder_id)
        existing_names = {
            str(item.get("name"))
            for item in siblings
            if isinstance(item, dict) and isinstance(item.get("name"), str)
        }

        project_name = PROJECT_FOLDER_BASE_NAME
        suffix = 1
        while project_name in existing_names:
            suffix += 1
            project_name = f"{PROJECT_FOLDER_BASE_NAME} ({suffix})"

        project_folder, active_tokens = await self._create_child_folder(
            active_tokens,
            name=project_name,
            parent_id=parent_folder_id,
        )
        project_id = str(project_folder["id"])

        created_subfolders: List[Dict[str, Any]] = []
        upload_target_id: Optional[str] = None

        for index, subfolder_name in enumerate(PROJECT_SUBFOLDERS):
            subfolder, active_tokens = await self._create_child_folder(
                active_tokens,
                name=subfolder_name,
                parent_id=str(project_folder["id"]),
            )
            created_subfolders.append(
                {
                    "id": str(subfolder["id"]),
                    "name": subfolder.get("name", subfolder_name),
                }
            )
            if index == 0:
                upload_target_id = str(subfolder["id"])

        if upload_target_id is None:
            upload_target_id = project_id

        uploaded_files: List[Dict[str, Any]] = []
        for upload in files:
            file_name = upload.filename or "업로드된 파일.pdf"
            content = await upload.read()
            file_info, active_tokens = await self._upload_file_to_folder(
                active_tokens,
                file_name=file_name,
                parent_id=upload_target_id,
                content=content,
                content_type=upload.content_type,
            )
            uploaded_files.append(
                {
                    "id": file_info.get("id"),
                    "name": file_info.get("name", file_name),
                    "size": len(content),
                    "contentType": upload.content_type or "application/pdf",
                }
            )
            await upload.close()

        logger.info(
            "Created Drive project '%s' (%s) with %d PDF files",
            project_name,
            project_id,
            len(uploaded_files),
        )

        return {
            "message": "새 프로젝트 폴더를 생성했습니다.",
            "project": {
                "id": project_id,
                "name": project_folder.get("name", project_name),
                "parentId": parent_folder_id,
                "subfolders": created_subfolders,
            },
            "uploadedFiles": uploaded_files,
        }


# expose constants for router usage
GoogleDriveService.PROJECT_FOLDER_BASE_NAME = PROJECT_FOLDER_BASE_NAME
GoogleDriveService.PROJECT_SUBFOLDERS = PROJECT_SUBFOLDERS
