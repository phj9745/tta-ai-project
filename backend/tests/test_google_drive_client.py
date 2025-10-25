from __future__ import annotations

import asyncio
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.config import Settings
from app.services.google_drive.client import GoogleDriveClient
from app.token_store import StoredAccount, StoredTokens


class InMemoryTokenStorage:
    def __init__(self, tokens: Dict[str, StoredTokens]) -> None:
        self._tokens = tokens

    def load_by_google_id(self, google_id: str) -> Optional[StoredTokens]:
        return self._tokens.get(google_id)

    def list_accounts(self) -> List[StoredAccount]:
        accounts: List[StoredAccount] = []
        for token in self._tokens.values():
            accounts.append(
                StoredAccount(
                    google_id=token.google_id,
                    display_name=token.display_name,
                    email=token.email,
                    saved_at=token.saved_at,
                )
            )
        return accounts

    def save(self, tokens: StoredTokens) -> StoredTokens:
        self._tokens[tokens.google_id] = tokens
        return tokens


def _settings() -> Settings:
    return Settings(
        client_id="id",
        client_secret="secret",
        redirect_uri="http://localhost",
        frontend_redirect_url="http://localhost",
        tokens_path=Path("/tmp/test.db"),
        openai_api_key="key",
        openai_model="model",
    )


def _stored_token(expires_in: int = 3600) -> StoredTokens:
    return StoredTokens(
        google_id="user",
        display_name="User",
        email="user@example.com",
        access_token="token",
        refresh_token="refresh",
        scope="scope",
        token_type="Bearer",
        expires_in=expires_in,
        saved_at=datetime.now(timezone.utc),
    )


class RefreshTrackingClient(GoogleDriveClient):
    def __init__(self, settings: Settings, storage: InMemoryTokenStorage) -> None:
        super().__init__(settings, storage)
        self.refreshed = False

    async def refresh_access_token(self, tokens: StoredTokens) -> StoredTokens:  # type: ignore[override]
        self.refreshed = True
        refreshed = StoredTokens(
            google_id=tokens.google_id,
            display_name=tokens.display_name,
            email=tokens.email,
            access_token="new-token",
            refresh_token=tokens.refresh_token,
            scope=tokens.scope,
            token_type=tokens.token_type,
            expires_in=tokens.expires_in,
            saved_at=datetime.now(timezone.utc),
        )
        self._token_storage.save(refreshed)
        return refreshed

    async def list_child_folders(self, tokens: StoredTokens, *, parent_id: str):  # type: ignore[override]
        folders = [
            {"id": "1", "name": "My Folder"},
            {"id": "2", "name": "Other"},
        ]
        return folders, tokens


def test_load_tokens_with_google_id() -> None:
    storage = InMemoryTokenStorage({"user": _stored_token()})
    client = GoogleDriveClient(_settings(), storage)
    tokens = client.load_tokens("user")
    assert tokens.google_id == "user"


def test_load_tokens_without_google_id_uses_first_account() -> None:
    storage = InMemoryTokenStorage({"user": _stored_token()})
    client = GoogleDriveClient(_settings(), storage)
    tokens = client.load_tokens(None)
    assert tokens.google_id == "user"


def test_ensure_valid_tokens_refreshes_when_expired() -> None:
    expired = _stored_token()
    expired.saved_at = datetime.now(timezone.utc) - timedelta(hours=2)
    storage = InMemoryTokenStorage({"user": expired})
    client = RefreshTrackingClient(_settings(), storage)
    refreshed = asyncio.run(client.ensure_valid_tokens(expired))
    assert client.refreshed is True
    assert refreshed.access_token == "new-token"


def test_find_child_folder_by_name_uses_variants() -> None:
    storage = InMemoryTokenStorage({"user": _stored_token()})
    client = RefreshTrackingClient(_settings(), storage)
    tokens = storage.load_by_google_id("user")
    assert tokens is not None
    folder, _ = asyncio.run(
        client.find_child_folder_by_name(
            tokens,
            parent_id="root",
            name="My-Folder",
            matcher=lambda value: (value.lower().replace("-", "").replace(" ", ""),),
        )
    )
    assert folder and folder["id"] == "1"
