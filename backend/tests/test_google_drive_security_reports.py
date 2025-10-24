from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.google_drive.security_reports import (  # noqa: E402
    download_shared_security_criteria,
    ensure_shared_criteria_file,
)
from app.token_store import StoredTokens


class StubClient:
    def __init__(self, files: Sequence[Dict[str, Any]] | None = None) -> None:
        self.files = list(files or [])
        self.uploads: List[Tuple[str, bytes]] = []

    async def list_child_files(self, tokens: StoredTokens, *, parent_id: str, mime_type: Optional[str] = None):
        return self.files, tokens

    async def upload_file_to_folder(
        self,
        tokens: StoredTokens,
        *,
        file_name: str,
        parent_id: str,
        content: bytes,
        content_type: Optional[str],
    ):
        self.uploads.append((file_name, content))
        entry = {"id": f"id-{file_name}", "name": file_name, "mimeType": content_type}
        return entry, tokens

    async def download_file_content(self, tokens: StoredTokens, *, file_id: str, mime_type: Optional[str] = None):
        return b"content", tokens


def _stored_tokens() -> StoredTokens:
    from datetime import datetime, timezone

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


def test_ensure_shared_criteria_file_returns_existing_entry() -> None:
    client = StubClient([
        {"id": "123", "name": "결함판단기준표 v1.0.xlsx", "mimeType": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}
    ])
    entry, tokens, created = asyncio.run(
        ensure_shared_criteria_file(client, _stored_tokens(), parent_id="root")
    )
    assert entry["id"] == "123"
    assert created is False


def test_download_shared_security_criteria_uploads_when_missing() -> None:
    client = StubClient([])
    content, _ = asyncio.run(
        download_shared_security_criteria(
            client,
            _stored_tokens(),
            parent_id="root",
            file_name="보안성 결함판단기준표 v1.0.xlsx",
        )
    )
    assert content == b"content"
    assert client.uploads, "Expected upload to occur when file missing"
