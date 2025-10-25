from __future__ import annotations

import io
from datetime import datetime, timezone
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Sequence, Tuple

import asyncio
import pytest

pytest.importorskip("openpyxl")
from openpyxl import Workbook

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.config import Settings
from app.services.google_drive.service import GoogleDriveService
from app.token_store import StoredAccount, StoredTokens


class StubOAuthService:
    def ensure_credentials(self) -> None:  # pragma: no cover - simple stub
        return None


class StubTokenStorage:
    def __init__(self, tokens: StoredTokens) -> None:
        self.tokens = tokens

    def load_by_google_id(self, google_id: str) -> Optional[StoredTokens]:
        if google_id == self.tokens.google_id:
            return self.tokens
        return None

    def list_accounts(self) -> Sequence[StoredAccount]:
        return [
            StoredAccount(
                google_id=self.tokens.google_id,
                display_name=self.tokens.display_name,
                email=self.tokens.email,
                saved_at=self.tokens.saved_at,
            )
        ]

    def save(self, tokens: StoredTokens) -> StoredTokens:
        self.tokens = tokens
        return tokens


class StubClient:
    def __init__(self, workbook_bytes: bytes, tokens: StoredTokens) -> None:
        self.workbook_bytes = workbook_bytes
        self.tokens = tokens
        self.updated_payload: Optional[Dict[str, Any]] = None

    def load_tokens(self, google_id: Optional[str]) -> StoredTokens:
        return self.tokens

    async def ensure_valid_tokens(self, tokens: StoredTokens) -> StoredTokens:
        return tokens

    async def find_child_folder_by_name(
        self,
        tokens: StoredTokens,
        *,
        parent_id: str,
        name: str,
        matcher,
    ) -> Tuple[Dict[str, Any], StoredTokens]:
        return {"id": "folder", "name": name}, tokens

    async def find_file_by_suffix(
        self,
        tokens: StoredTokens,
        *,
        parent_id: str,
        suffix: str,
        matcher,
        mime_type: Optional[str] = None,
    ) -> Tuple[Dict[str, Any], StoredTokens]:
        return {"id": "file", "name": suffix, "mimeType": mime_type}, tokens

    async def download_file_content(
        self,
        tokens: StoredTokens,
        *,
        file_id: str,
        mime_type: Optional[str] = None,
    ) -> Tuple[bytes, StoredTokens]:
        return self.workbook_bytes, tokens

    async def update_file_content(
        self,
        tokens: StoredTokens,
        *,
        file_id: str,
        file_name: str,
        content: bytes,
        content_type: str,
    ) -> Tuple[Dict[str, Any], StoredTokens]:
        self.updated_payload = {
            "file_id": file_id,
            "file_name": file_name,
            "content_length": len(content),
            "content_type": content_type,
        }
        return {"modifiedTime": "2024-01-01T00:00:00Z"}, tokens

    async def drive_request(self, tokens: StoredTokens, *, method: str, path: str, params: Dict[str, Any]):
        return {"name": "[GS-B-12-3456] Project"}, tokens

    async def find_root_folder(self, tokens: StoredTokens, *, folder_name: str):
        return {"id": "gs", "name": folder_name}, tokens

    async def create_root_folder(self, tokens: StoredTokens, *, folder_name: str):
        return {"id": "gs", "name": folder_name}, tokens

    async def list_child_folders(self, tokens: StoredTokens, *, parent_id: str):
        return ([{"id": "p1", "name": "Proj"}], tokens)


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


def _stored_tokens() -> StoredTokens:
    return StoredTokens(
        google_id="user",
        display_name="User",
        email="user@example.com",
        access_token="token",
        refresh_token="refresh",
        scope="scope",
        token_type="Bearer",
        expires_in=3600,
        saved_at=datetime.now(timezone.utc),
    )


def _feature_workbook() -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "기능리스트"
    sheet.append(["대분류", "중분류", "소분류", "기능 설명"])
    sheet.append(["A", "B", "C", "설명"])
    buffer = io.BytesIO()
    workbook.save(buffer)
    workbook.close()
    return buffer.getvalue()


def test_get_feature_list_rows_uses_parsers(monkeypatch) -> None:
    tokens = _stored_tokens()
    storage = StubTokenStorage(tokens)
    service = GoogleDriveService(_settings(), storage, StubOAuthService())
    stub_client = StubClient(_feature_workbook(), tokens)
    service._client = stub_client  # type: ignore[attr-defined]

    result = asyncio.run(service.get_feature_list_rows(project_id="proj", google_id="user"))
    assert result["rows"][0]["featureDescription"] == "설명"


def test_update_feature_list_rows_updates_workbook(monkeypatch) -> None:
    tokens = _stored_tokens()
    storage = StubTokenStorage(tokens)
    service = GoogleDriveService(_settings(), storage, StubOAuthService())
    stub_client = StubClient(_feature_workbook(), tokens)
    service._client = stub_client  # type: ignore[attr-defined]

    asyncio.run(
        service.update_feature_list_rows(
            project_id="proj",
            rows=[{"majorCategory": "A", "middleCategory": "B", "minorCategory": "C", "featureDescription": "설명"}],
            project_overview="",
            google_id="user",
        )
    )
    assert stub_client.updated_payload is not None
    assert stub_client.updated_payload["content_type"].endswith("spreadsheetml.sheet")


def test_get_project_exam_number_reads_name() -> None:
    tokens = _stored_tokens()
    storage = StubTokenStorage(tokens)
    service = GoogleDriveService(_settings(), storage, StubOAuthService())
    stub_client = StubClient(_feature_workbook(), tokens)
    service._client = stub_client  # type: ignore[attr-defined]
    exam = asyncio.run(service.get_project_exam_number(project_id="proj", google_id="user"))
    assert exam == "GS-B-12-3456"
