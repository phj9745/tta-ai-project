from __future__ import annotations

import logging
import os
import secrets
from pathlib import Path
from typing import Dict, Optional
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from .token_store import TokenStorage

logger = logging.getLogger(__name__)

load_dotenv()

GOOGLE_AUTH_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
GOOGLE_SCOPES = (
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/drive.file",
)

CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI")

FRONTEND_REDIRECT_URL = os.getenv("FRONTEND_REDIRECT_URL", "http://localhost:5173/")

TOKENS_PATH = Path(os.getenv("GOOGLE_TOKEN_PATH", Path(__file__).resolve().parent / "google_tokens.json"))
token_storage = TokenStorage(Path(TOKENS_PATH))

state_store: set[str] = set()


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

    state_store.remove(state)

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
    token_storage.save(tokens)

    redirect_url = _build_frontend_redirect("success")
    return RedirectResponse(redirect_url)


@app.get("/auth/google/tokens")
def read_tokens() -> JSONResponse:
    _ensure_credentials()

    stored = token_storage.load()
    if not stored:
        raise HTTPException(status_code=404, detail="저장된 토큰이 없습니다.")

    payload = stored.to_dict()
    payload.pop("access_token", None)
    payload.pop("refresh_token", None)

    return JSONResponse(payload)


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
