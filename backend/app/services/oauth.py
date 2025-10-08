from __future__ import annotations

import logging
import secrets
from typing import Dict, Optional
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import httpx
from fastapi import HTTPException

from ..config import Settings
from ..token_store import TokenStorage

logger = logging.getLogger(__name__)

GOOGLE_AUTH_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
GOOGLE_SCOPES = (
    "openid",
    "https://www.googleapis.com/auth/userinfo.profile",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/drive.file",
)


class GoogleOAuthService:
    """Encapsulate Google OAuth flow helpers."""

    def __init__(self, settings: Settings, token_storage: TokenStorage) -> None:
        self._settings = settings
        self._token_storage = token_storage
        self._state_store: set[str] = set()

    def ensure_credentials(self) -> None:
        if not self._settings.has_oauth_credentials:
            raise HTTPException(
                status_code=500,
                detail="Google OAuth 환경 변수가 올바르게 설정되지 않았습니다.",
            )

    def build_frontend_redirect(self, status: str, message: Optional[str] = None) -> str:
        parsed = list(urlparse(self._settings.frontend_redirect_url))
        query: Dict[str, str] = dict(parse_qsl(parsed[4]))
        query["auth"] = status
        if message:
            query["message"] = message
        parsed[4] = urlencode(query, doseq=True)
        return urlunparse(parsed)

    def create_state(self) -> str:
        state = secrets.token_urlsafe(32)
        self._state_store.add(state)
        return state

    def validate_state(self, state: Optional[str]) -> None:
        if not state or state not in self._state_store:
            raise HTTPException(status_code=400, detail="유효하지 않은 state 값입니다.")
        self._state_store.discard(state)

    async def exchange_code_for_tokens(self, code: str) -> Dict[str, str]:
        data = {
            "code": code,
            "client_id": self._settings.client_id,
            "client_secret": self._settings.client_secret,
            "redirect_uri": self._settings.redirect_uri,
            "grant_type": "authorization_code",
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(GOOGLE_TOKEN_ENDPOINT, data=data)

        if response.is_error:
            logger.error("Google token exchange failed: %s", response.text)
            raise HTTPException(status_code=502, detail="Google 토큰 발급에 실패했습니다.")

        payload = response.json()
        access_token = payload.get("access_token")
        if not isinstance(access_token, str) or not access_token:
            logger.error("Google token exchange response missing access_token: %s", payload)
            raise HTTPException(status_code=502, detail="Google 토큰 발급에 실패했습니다.")

        return payload

    async def fetch_userinfo(self, access_token: str) -> Dict[str, str]:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                "https://openidconnect.googleapis.com/v1/userinfo",
                headers={"Authorization": f"Bearer {access_token}"},
            )

        if response.is_error:
            logger.error("Failed to fetch Google user info: %s", response.text)
            raise HTTPException(
                status_code=502,
                detail="Google 사용자 정보를 불러오지 못했습니다. 다시 시도해주세요.",
            )

        data = response.json()
        if not isinstance(data, dict):
            raise HTTPException(status_code=502, detail="Google 사용자 정보를 확인할 수 없습니다.")
        return data

    def save_tokens(self, userinfo: Dict[str, str], payload: Dict[str, str]) -> Dict[str, str]:
        google_id = userinfo.get("sub")
        display_name = userinfo.get("name") or userinfo.get("email") or "알 수 없는 사용자"
        email = userinfo.get("email")

        if not isinstance(google_id, str) or not google_id:
            logger.error("Google user info response missing sub identifier: %s", userinfo)
            raise HTTPException(status_code=502, detail="Google 사용자 식별자를 확인할 수 없습니다.")

        stored = self._token_storage.save(
            google_id=google_id,
            display_name=display_name,
            email=email,
            payload=payload,
        )

        return {
            "google_id": stored.google_id,
            "display_name": stored.display_name,
        }

    @property
    def settings(self) -> Settings:
        return self._settings

    @property
    def token_storage(self) -> TokenStorage:
        return self._token_storage
