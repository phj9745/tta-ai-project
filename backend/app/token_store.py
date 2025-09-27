from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional


@dataclass
class StoredTokens:
    """Representation of the Google OAuth tokens saved on disk."""

    access_token: str
    refresh_token: Optional[str]
    scope: str
    token_type: str
    expires_in: int
    saved_at: datetime

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StoredTokens":
        return cls(
            access_token=data["access_token"],
            refresh_token=data.get("refresh_token"),
            scope=data["scope"],
            token_type=data["token_type"],
            expires_in=int(data["expires_in"]),
            saved_at=datetime.fromisoformat(data["saved_at"]),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "scope": self.scope,
            "token_type": self.token_type,
            "expires_in": self.expires_in,
            "saved_at": self.saved_at.isoformat(),
        }


class TokenStorage:
    """Persist Google OAuth tokens to a JSON file on disk."""

    def __init__(self, file_path: Path) -> None:
        self._file_path = file_path
        self._file_path.parent.mkdir(parents=True, exist_ok=True)

    def save(self, payload: Dict[str, Any]) -> StoredTokens:
        tokens = StoredTokens(
            access_token=payload["access_token"],
            refresh_token=payload.get("refresh_token"),
            scope=payload.get("scope", ""),
            token_type=payload.get("token_type", "Bearer"),
            expires_in=int(payload.get("expires_in", 0)),
            saved_at=datetime.now(timezone.utc),
        )

        with self._file_path.open("w", encoding="utf-8") as fp:
            json.dump(tokens.to_dict(), fp, ensure_ascii=False, indent=2)

        return tokens

    def load(self) -> Optional[StoredTokens]:
        if not self._file_path.exists():
            return None

        with self._file_path.open("r", encoding="utf-8") as fp:
            data = json.load(fp)

        return StoredTokens.from_dict(data)
