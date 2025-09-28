from __future__ import annotations

import json
import logging
import os
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from .token_store import StoredTokens, TokenStorage

logger = logging.getLogger(__name__)

load_dotenv()

GOOGLE_AUTH_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
GOOGLE_SCOPES = (
    "openid",
    "https://www.googleapis.com/auth/userinfo.profile",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/drive.file",
)

CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI")

FRONTEND_REDIRECT_URL = os.getenv("FRONTEND_REDIRECT_URL", "http://localhost:5173/")

tokens_path_env = os.getenv("GOOGLE_TOKEN_DB_PATH") or os.getenv("GOOGLE_TOKEN_PATH")
default_tokens_path = Path(__file__).resolve().parent / "google_tokens.db"
TOKENS_PATH = Path(tokens_path_env) if tokens_path_env else default_tokens_path
token_storage = TokenStorage(Path(TOKENS_PATH))

state_store: Set[str] = set()

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


def _ensure_credentials() -> None:
    if not CLIENT_ID or not CLIENT_SECRET or not REDIRECT_URI:
        raise HTTPException(
            status_code=500,
            detail="Google OAuth 환경 변수가 올바르게 설정되지 않았습니다.",
        )


def _build_frontend_redirect(status: str, message: Optional[str] = None) -> str:
    parsed = list(urlparse(FRONTEND_REDIRECT_URL))
    query: Dict[str, str] = dict(parse_qsl(parsed[4]))
    query["auth"] = status
    if message:
        query["message"] = message
    parsed[4] = urlencode(query, doseq=True)
    return urlunparse(parsed)


def _load_tokens_for_drive(google_id: Optional[str]) -> StoredTokens:
    if google_id:
        stored = token_storage.load_by_google_id(google_id)
        if stored is None:
            raise HTTPException(status_code=404, detail="요청한 Google 계정 토큰을 찾을 수 없습니다.")
        return stored

    accounts = token_storage.list_accounts()
    if not accounts:
        raise HTTPException(status_code=404, detail="저장된 Google 계정이 없습니다. 먼저 로그인하세요.")

    for account in accounts:
        stored = token_storage.load_by_google_id(account.google_id)
        if stored is not None:
            return stored

    raise HTTPException(status_code=404, detail="저장된 Google 계정 토큰을 찾을 수 없습니다.")


def _is_token_expired(tokens: StoredTokens) -> bool:
    if tokens.expires_in <= 0:
        return False

    expires_at = tokens.saved_at + timedelta(seconds=tokens.expires_in)
    now = datetime.now(timezone.utc)
    return now >= expires_at - timedelta(minutes=1)


async def _refresh_access_token(tokens: StoredTokens) -> StoredTokens:
    if not tokens.refresh_token:
        raise HTTPException(status_code=401, detail="Google 인증이 만료되었습니다. 다시 로그인해주세요.")

    data = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
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

    return token_storage.save(
        google_id=tokens.google_id,
        display_name=tokens.display_name,
        email=tokens.email,
        payload=merged_payload,
    )


async def _ensure_valid_tokens(tokens: StoredTokens) -> StoredTokens:
    if _is_token_expired(tokens):
        return await _refresh_access_token(tokens)
    return tokens


async def _drive_request(
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
                logger.error(
                    "Google Drive API %s %s failed: %s", method, path, response.text
                )
                raise HTTPException(
                    status_code=502,
                    detail="Google Drive API 요청이 실패했습니다. 잠시 후 다시 시도해주세요.",
                )

            data = response.json()
            return data, current_tokens

        if attempt == 0:
            current_tokens = await _refresh_access_token(current_tokens)
            continue

    raise HTTPException(
        status_code=401,
        detail="Google Drive 인증이 만료되었습니다. 다시 로그인해주세요.",
    )


async def _find_root_folder(
    tokens: StoredTokens, *, folder_name: str
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

    data, updated_tokens = await _drive_request(
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
    tokens: StoredTokens, *, folder_name: str
) -> Tuple[Dict[str, Any], StoredTokens]:
    body = {
        "name": folder_name,
        "mimeType": DRIVE_FOLDER_MIME_TYPE,
        "parents": ["root"],
    }
    params = {"fields": "id,name"}

    data, updated_tokens = await _drive_request(
        tokens,
        method="POST",
        path=DRIVE_FILES_ENDPOINT,
        params=params,
        json_body=body,
    )

    if not isinstance(data, dict) or "id" not in data:
        logger.error("Google Drive create folder response missing id: %s", data)
        raise HTTPException(
            status_code=502,
            detail="Google Drive 폴더를 생성하지 못했습니다. 다시 시도해주세요.",
        )

    return data, updated_tokens


async def _create_child_folder(
    tokens: StoredTokens, *, name: str, parent_id: str
) -> Tuple[Dict[str, Any], StoredTokens]:
    body = {
        "name": name,
        "mimeType": DRIVE_FOLDER_MIME_TYPE,
        "parents": [parent_id],
    }
    params = {"fields": "id,name,parents"}

    data, updated_tokens = await _drive_request(
        tokens,
        method="POST",
        path=DRIVE_FILES_ENDPOINT,
        params=params,
        json_body=body,
    )

    if not isinstance(data, dict) or "id" not in data:
        logger.error("Google Drive create child folder response missing id: %s", data)
        raise HTTPException(
            status_code=502,
            detail="Google Drive 하위 폴더를 생성하지 못했습니다. 다시 시도해주세요.",
        )

    return data, updated_tokens


async def _upload_file_to_folder(
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
            active_tokens = await _refresh_access_token(active_tokens)
            continue

        if response.is_error:
            logger.error(
                "Google Drive file upload failed for %s: %s",
                file_name,
                response.text,
            )
            raise HTTPException(
                status_code=502,
                detail="파일을 Google Drive에 업로드하지 못했습니다. 잠시 후 다시 시도해주세요.",
            )

        data = response.json()
        if not isinstance(data, dict) or "id" not in data:
            logger.error("Google Drive file upload response missing id: %s", data)
            raise HTTPException(
                status_code=502,
                detail="업로드한 파일의 ID를 확인하지 못했습니다. 다시 시도해주세요.",
            )

        return data, active_tokens

    raise HTTPException(
        status_code=401,
        detail="Google Drive 인증이 만료되었습니다. 다시 로그인해주세요.",
    )


async def _list_child_folders(
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

    data, updated_tokens = await _drive_request(
        tokens,
        method="GET",
        path=DRIVE_FILES_ENDPOINT,
        params=params,
    )

    files = data.get("files")
    if isinstance(files, Sequence):
        return files, updated_tokens

    return [], updated_tokens


async def ensure_gs_drive_setup(google_id: Optional[str]) -> Dict[str, Any]:
    stored_tokens = _load_tokens_for_drive(google_id)
    active_tokens = await _ensure_valid_tokens(stored_tokens)

    folder, active_tokens = await _find_root_folder(active_tokens, folder_name="gs")
    folder_created = False

    if folder is None:
        folder, active_tokens = await _create_root_folder(active_tokens, folder_name="gs")
        folder_created = True

    projects, active_tokens = await _list_child_folders(
        active_tokens,
        parent_id=str(folder["id"]),
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
        "projects": normalized_projects,
        "account": {
            "googleId": active_tokens.google_id,
            "displayName": active_tokens.display_name,
            "email": active_tokens.email,
        },
    }


app = FastAPI()


parsed_frontend = urlparse(FRONTEND_REDIRECT_URL)
frontend_origin = f"{parsed_frontend.scheme}://{parsed_frontend.netloc}" if parsed_frontend.scheme else "*"

app.add_middleware(
    CORSMiddleware,
    allow_origins=[frontend_origin] if frontend_origin != "" else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def read_root() -> Dict[str, str]:
    return {
        "project": "TTA-AI-Project",
        "status": "running",
    }


@app.get("/auth/google/login")
def google_login() -> RedirectResponse:
    _ensure_credentials()

    state = secrets.token_urlsafe(32)
    state_store.add(state)

    params = {
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": " ".join(GOOGLE_SCOPES),
        "access_type": "offline",
        "prompt": "consent",
        "include_granted_scopes": "true",
        "state": state,
    }

    auth_url = f"{GOOGLE_AUTH_ENDPOINT}?{urlencode(params)}"
    return RedirectResponse(auth_url)


@app.get("/auth/google/callback")
async def google_callback(request: Request) -> RedirectResponse:
    _ensure_credentials()

    params = request.query_params
    error = params.get("error")
    state = params.get("state")

    if error:
        message = params.get("error_description", "Google 인증이 취소되었습니다.")
        redirect_url = _build_frontend_redirect("error", message)
        return RedirectResponse(redirect_url)

    code = params.get("code")
    if not code or not state:
        raise HTTPException(status_code=400, detail="code 또는 state 매개변수가 누락되었습니다.")

    if state not in state_store:
        raise HTTPException(status_code=400, detail="유효하지 않은 state 값입니다.")

    state_store.discard(state)

    data = {
        "code": code,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "redirect_uri": REDIRECT_URI,
        "grant_type": "authorization_code",
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(GOOGLE_TOKEN_ENDPOINT, data=data)

    if response.is_error:
        logger.error("Google token exchange failed: %s", response.text)
        redirect_url = _build_frontend_redirect("error", "Google 토큰 발급에 실패했습니다.")
        return RedirectResponse(redirect_url)

    tokens = response.json()

    access_token = tokens.get("access_token")
    if not access_token:
        logger.error("Google token exchange response missing access_token: %s", tokens)
        redirect_url = _build_frontend_redirect("error", "Google 토큰 발급에 실패했습니다.")
        return RedirectResponse(redirect_url)

    async with httpx.AsyncClient(timeout=10.0) as client:
        userinfo_response = await client.get(
            "https://openidconnect.googleapis.com/v1/userinfo",
            headers={"Authorization": f"Bearer {access_token}"},
        )

    if userinfo_response.is_error:
        logger.error("Failed to fetch Google user info: %s", userinfo_response.text)
        redirect_url = _build_frontend_redirect(
            "error", "Google 사용자 정보를 불러오지 못했습니다. 다시 시도해주세요."
        )
        return RedirectResponse(redirect_url)

    userinfo = userinfo_response.json()
    google_id = userinfo.get("sub")
    display_name = userinfo.get("name") or userinfo.get("email") or "알 수 없는 사용자"
    email = userinfo.get("email")

    if not google_id:
        logger.error("Google user info response missing sub identifier: %s", userinfo)
        redirect_url = _build_frontend_redirect(
            "error", "Google 사용자 식별자를 확인할 수 없습니다."
        )
        return RedirectResponse(redirect_url)

    token_storage.save(
        google_id=google_id,
        display_name=display_name,
        email=email,
        payload=tokens,
    )

    redirect_url = _build_frontend_redirect(
        "success",
        message=f"{display_name} 계정의 토큰이 저장되었습니다.",
    )
    return RedirectResponse(redirect_url)


@app.get("/auth/google/tokens")
def read_tokens(
    google_id: Optional[str] = Query(None, description="조회할 Google 사용자 식별자 (sub)"),
    email: Optional[str] = Query(None, description="조회할 Google 계정 이메일"),
) -> JSONResponse:
    _ensure_credentials()

    if not google_id and not email:
        raise HTTPException(
            status_code=400,
            detail="google_id 또는 email 중 하나는 반드시 제공해야 합니다.",
        )

    stored = None
    if google_id:
        stored = token_storage.load_by_google_id(google_id)
    if stored is None and email:
        stored = token_storage.load_by_email(email)
    if not stored:
        raise HTTPException(status_code=404, detail="요청한 사용자에 대한 저장된 토큰이 없습니다.")

    payload = stored.to_dict()
    payload.pop("access_token", None)
    payload.pop("refresh_token", None)

    return JSONResponse(payload)


@app.get("/auth/google/users")
def list_users() -> JSONResponse:
    _ensure_credentials()

    accounts = [account.to_dict() for account in token_storage.list_accounts()]
    return JSONResponse(accounts)


@app.post("/drive/gs/setup")
async def ensure_gs_folder(
    google_id: Optional[str] = Query(
        None,
        description="Drive 작업에 사용할 Google 사용자 식별자 (sub)",
    )
) -> JSONResponse:
    _ensure_credentials()

    result = await ensure_gs_drive_setup(google_id)
    return JSONResponse(result)


@app.post("/drive/projects")
async def create_drive_project(
    folder_id: Optional[str] = Form(None),
    files: List[UploadFile] = File(...),
    google_id: Optional[str] = Query(
        None,
        description="Drive 작업에 사용할 Google 사용자 식별자 (sub)",
    ),
) -> Dict[str, Any]:
    _ensure_credentials()

    if not files:
        raise HTTPException(status_code=422, detail="최소 한 개의 파일을 업로드해주세요.")

    invalid_files: List[str] = []
    for upload in files:
        filename = upload.filename or "업로드된 파일"
        if not filename.lower().endswith(".pdf"):
            invalid_files.append(filename)

    if invalid_files:
        detail = ", ".join(invalid_files)
        raise HTTPException(status_code=422, detail=f"PDF 파일만 업로드할 수 있습니다: {detail}")

    stored_tokens = _load_tokens_for_drive(google_id)
    active_tokens = await _ensure_valid_tokens(stored_tokens)

    parent_folder_id = folder_id
    if not parent_folder_id:
        folder, active_tokens = await _find_root_folder(active_tokens, folder_name="gs")
        if folder is None:
            folder, active_tokens = await _create_root_folder(active_tokens, folder_name="gs")
        parent_folder_id = str(folder["id"])

    siblings, active_tokens = await _list_child_folders(
        active_tokens,
        parent_id=parent_folder_id,
    )
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

    project_folder, active_tokens = await _create_child_folder(
        active_tokens,
        name=project_name,
        parent_id=parent_folder_id,
    )
    project_id = str(project_folder["id"])

    created_subfolders: List[Dict[str, Any]] = []
    upload_target_id: Optional[str] = None

    for index, subfolder_name in enumerate(PROJECT_SUBFOLDERS):
        subfolder, active_tokens = await _create_child_folder(
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
        file_info, active_tokens = await _upload_file_to_folder(
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


@app.get("/auth/google/callback/success")
def success_page() -> HTMLResponse:
    return HTMLResponse(
        """
        <html>
            <head>
                <meta charset="utf-8" />
                <title>Google 인증 완료</title>
                <style>
                    body { font-family: sans-serif; padding: 48px; text-align: center; }
                    h1 { color: #2563eb; }
                </style>
            </head>
            <body>
                <h1>Google Drive 인증이 완료되었습니다.</h1>
                <p>이 창은 닫으셔도 됩니다.</p>
            </body>
        </html>
        """
    )
