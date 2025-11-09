from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


@dataclass
class StoredTokens:
    """Representation of the Google OAuth tokens saved in the database."""

    google_id: str
    display_name: str
    email: Optional[str]
    access_token: str
    refresh_token: Optional[str]
    scope: str
    token_type: str
    expires_in: int
    saved_at: datetime
    id_token: Optional[str] = None

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "StoredTokens":
        return cls(
            google_id=row["google_id"],
            display_name=row["display_name"],
            email=row["email"],
            access_token=row["access_token"],
            refresh_token=row["refresh_token"],
            scope=row["scope"],
            token_type=row["token_type"],
            expires_in=int(row["expires_in"]),
            saved_at=datetime.fromisoformat(row["saved_at"]),
            id_token=row["id_token"] if "id_token" in row.keys() else None,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "google_id": self.google_id,
            "display_name": self.display_name,
            "email": self.email,
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "id_token": self.id_token,
            "scope": self.scope,
            "token_type": self.token_type,
            "expires_in": self.expires_in,
            "saved_at": self.saved_at.isoformat(),
        }


@dataclass
class StoredAccount:
    google_id: str
    display_name: str
    email: Optional[str]
    saved_at: datetime

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "StoredAccount":
        return cls(
            google_id=row["google_id"],
            display_name=row["display_name"],
            email=row["email"],
            saved_at=datetime.fromisoformat(row["saved_at"]),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "google_id": self.google_id,
            "display_name": self.display_name,
            "email": self.email,
            "saved_at": self.saved_at.isoformat(),
        }


class TokenStorage:
    """Persist Google OAuth tokens to a SQLite database."""

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()
        self._migrate_legacy_json_if_needed()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _initialize(self) -> None:
        with self._get_connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS google_tokens (
                    google_id TEXT PRIMARY KEY,
                    display_name TEXT NOT NULL,
                    email TEXT,
                    access_token TEXT NOT NULL,
                    refresh_token TEXT,
                    id_token TEXT,
                    scope TEXT,
                    token_type TEXT,
                    expires_in INTEGER,
                    saved_at TEXT NOT NULL
                )
                """
            )
            try:
                conn.execute("ALTER TABLE google_tokens ADD COLUMN id_token TEXT")
            except sqlite3.OperationalError:
                # Column already exists in upgraded databases.
                pass
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_google_tokens_email
                ON google_tokens(email)
                """
            )

    def _migrate_legacy_json_if_needed(self) -> None:
        legacy_json = self._db_path.with_suffix(".json")
        if not legacy_json.exists():
            return

        try:
            with legacy_json.open("r", encoding="utf-8") as fp:
                raw = json.load(fp)
        except (OSError, json.JSONDecodeError):
            return

        if not isinstance(raw, dict):
            return

        rows: List[Dict[str, Any]] = []
        if "users" in raw and isinstance(raw["users"], dict):
            iterable: Iterable[Any] = raw["users"].items()
        else:
            iterable = [("legacy", raw)]

        for user_id, payload in iterable:
            if not isinstance(payload, dict):
                continue
            try:
                saved_at = payload.get("saved_at")
                saved_at_dt = (
                    datetime.fromisoformat(saved_at)
                    if isinstance(saved_at, str)
                    else datetime.now(timezone.utc)
                )
                rows.append(
                    {
                        "google_id": str(user_id),
                        "display_name": str(payload.get("display_name") or user_id),
                        "email": payload.get("email"),
                        "access_token": payload["access_token"],
                        "refresh_token": payload.get("refresh_token"),
                        "id_token": payload.get("id_token"),
                        "scope": payload.get("scope", ""),
                        "token_type": payload.get("token_type", "Bearer"),
                        "expires_in": int(payload.get("expires_in", 0)),
                        "saved_at": saved_at_dt.isoformat(),
                    }
                )
            except (KeyError, TypeError, ValueError):
                continue

        if not rows:
            return

        with self._get_connection() as conn:
            conn.executemany(
                """
                INSERT INTO google_tokens (
                    google_id, display_name, email, access_token, refresh_token, id_token,
                    scope, token_type, expires_in, saved_at
                ) VALUES (:google_id, :display_name, :email, :access_token, :refresh_token, :id_token,
                          :scope, :token_type, :expires_in, :saved_at)
                ON CONFLICT(google_id) DO UPDATE SET
                    display_name=excluded.display_name,
                    email=excluded.email,
                    access_token=excluded.access_token,
                    refresh_token=excluded.refresh_token,
                    id_token=excluded.id_token,
                    scope=excluded.scope,
                    token_type=excluded.token_type,
                    expires_in=excluded.expires_in,
                    saved_at=excluded.saved_at
                """,
                rows,
            )

        try:
            legacy_json.rename(legacy_json.with_suffix(".json.bak"))
        except OSError:
            pass

    def save(
        self,
        *,
        google_id: str,
        display_name: str,
        email: Optional[str],
        payload: Dict[str, Any],
    ) -> StoredTokens:
        normalized_google_id = google_id.strip()
        if not normalized_google_id:
            raise ValueError("google_id must be a non-empty string")

        saved_at = datetime.now(timezone.utc)
        tokens = StoredTokens(
            google_id=normalized_google_id,
            display_name=display_name.strip() or normalized_google_id,
            email=email.strip() if isinstance(email, str) else None,
            access_token=payload["access_token"],
            refresh_token=payload.get("refresh_token"),
            id_token=payload.get("id_token"),
            scope=payload.get("scope", ""),
            token_type=payload.get("token_type", "Bearer"),
            expires_in=int(payload.get("expires_in", 0)),
            saved_at=saved_at,
        )

        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO google_tokens (
                    google_id, display_name, email, access_token, refresh_token, id_token,
                    scope, token_type, expires_in, saved_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(google_id) DO UPDATE SET
                    display_name=excluded.display_name,
                    email=excluded.email,
                    access_token=excluded.access_token,
                    refresh_token=excluded.refresh_token,
                    id_token=excluded.id_token,
                    scope=excluded.scope,
                    token_type=excluded.token_type,
                    expires_in=excluded.expires_in,
                    saved_at=excluded.saved_at
                """,
                (
                    tokens.google_id,
                    tokens.display_name,
                    tokens.email,
                    tokens.access_token,
                    tokens.refresh_token,
                    tokens.id_token,
                    tokens.scope,
                    tokens.token_type,
                    tokens.expires_in,
                    tokens.saved_at.isoformat(),
                ),
            )

        return tokens

    def load_by_google_id(self, google_id: str) -> Optional[StoredTokens]:
        normalized_google_id = google_id.strip()
        if not normalized_google_id:
            return None

        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM google_tokens WHERE google_id = ?",
                (normalized_google_id,),
            )
            row = cursor.fetchone()

        return StoredTokens.from_row(row) if row else None

    def load_by_email(self, email: str) -> Optional[StoredTokens]:
        normalized_email = email.strip()
        if not normalized_email:
            return None

        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM google_tokens WHERE email = ?",
                (normalized_email,),
            )
            row = cursor.fetchone()

        return StoredTokens.from_row(row) if row else None

    def list_accounts(self) -> List[StoredAccount]:
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT google_id, display_name, email, saved_at FROM google_tokens ORDER BY saved_at DESC"
            )
            rows = cursor.fetchall()

        return [StoredAccount.from_row(row) for row in rows]
