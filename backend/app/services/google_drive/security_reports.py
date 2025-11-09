"""Shared helpers for security report workflows."""
from __future__ import annotations

from typing import Any, Dict, Optional, Sequence, Tuple

from fastapi import HTTPException

from ...token_store import StoredTokens
from .client import GOOGLE_SHEETS_MIME_TYPE, XLSX_MIME_TYPE, GoogleDriveClient
from .templates import (
    PREFERRED_SHARED_CRITERIA_FILE_NAME,
    SHARED_CRITERIA_FILE_CANDIDATES,
    load_shared_criteria_template_bytes,
    normalize_shared_criteria_name,
)

__all__ = [
    "ensure_shared_criteria_file",
    "download_shared_security_criteria",
]


async def ensure_shared_criteria_file(
    client: GoogleDriveClient,
    tokens: StoredTokens,
    *,
    parent_id: str,
    preferred_names: Optional[Sequence[str]] = None,
) -> Tuple[Dict[str, Any], StoredTokens, bool]:
    normalized_candidates = {
        normalize_shared_criteria_name(candidate)
        for candidate in SHARED_CRITERIA_FILE_CANDIDATES
    }
    upload_name = PREFERRED_SHARED_CRITERIA_FILE_NAME
    if preferred_names:
        normalized_candidates.update(
            normalize_shared_criteria_name(name)
            for name in preferred_names
            if isinstance(name, str) and name.strip()
        )
        first_valid = next(
            (name.strip() for name in preferred_names if isinstance(name, str) and name.strip()),
            None,
        )
        if first_valid:
            upload_name = first_valid

    files, active_tokens = await client.list_child_files(tokens, parent_id=parent_id)
    for entry in files:
        if not isinstance(entry, dict):
            continue
        name = entry.get("name")
        if not isinstance(name, str):
            continue
        normalized_name = normalize_shared_criteria_name(name)
        if normalized_name not in normalized_candidates:
            continue
        mime_type = entry.get("mimeType")
        if isinstance(mime_type, str) and mime_type not in {XLSX_MIME_TYPE, GOOGLE_SHEETS_MIME_TYPE}:
            continue
        normalized_entry = dict(entry)
        normalized_entry["mimeType"] = mime_type if isinstance(mime_type, str) else None
        return normalized_entry, active_tokens, False

    content = load_shared_criteria_template_bytes()
    uploaded_entry, updated_tokens = await client.upload_file_to_folder(
        active_tokens,
        file_name=upload_name,
        parent_id=parent_id,
        content=content,
        content_type=XLSX_MIME_TYPE,
    )
    uploaded_entry = dict(uploaded_entry)
    uploaded_entry.setdefault("name", upload_name)
    uploaded_entry["mimeType"] = XLSX_MIME_TYPE
    return uploaded_entry, updated_tokens, True


async def download_shared_security_criteria(
    client: GoogleDriveClient,
    tokens: StoredTokens,
    *,
    parent_id: str,
    file_name: str,
) -> Tuple[bytes, StoredTokens]:
    file_entry, active_tokens, _ = await ensure_shared_criteria_file(
        client,
        tokens,
        parent_id=parent_id,
        preferred_names=(file_name,),
    )

    file_id = file_entry.get("id")
    if not isinstance(file_id, str):
        raise HTTPException(status_code=502, detail="결함 판단 기준표 ID를 확인할 수 없습니다.")

    content, active_tokens = await client.download_file_content(
        active_tokens,
        file_id=file_id,
        mime_type=file_entry.get("mimeType"),
    )
    return content, active_tokens
