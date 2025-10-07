from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import List


@dataclass(frozen=True)
class PromptRequestLogEntry:
    """Recorded information about a generated prompt request."""

    request_id: str
    timestamp: str
    project_id: str
    menu_id: str
    system_prompt: str
    user_prompt: str
    context_summary: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)

    @staticmethod
    def from_dict(payload: dict[str, object]) -> PromptRequestLogEntry | None:
        try:
            request_id = str(payload["request_id"])
            timestamp = str(payload["timestamp"])
            project_id = str(payload["project_id"])
            menu_id = str(payload["menu_id"])
            system_prompt = str(payload.get("system_prompt", ""))
            user_prompt = str(payload.get("user_prompt", ""))
            context_summary = str(payload.get("context_summary", ""))
        except (KeyError, TypeError, ValueError):
            return None

        return PromptRequestLogEntry(
            request_id=request_id,
            timestamp=timestamp,
            project_id=project_id,
            menu_id=menu_id,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            context_summary=context_summary,
        )


class PromptRequestLogService:
    """Persist and retrieve prompt request log entries."""

    def __init__(self, storage_path: Path) -> None:
        self._storage_path = storage_path
        self._lock = Lock()
        storage_path.parent.mkdir(parents=True, exist_ok=True)
        storage_path.touch(exist_ok=True)

    def record_request(
        self,
        *,
        project_id: str,
        menu_id: str,
        system_prompt: str,
        user_prompt: str,
        context_summary: str | None = None,
    ) -> PromptRequestLogEntry:
        entry = PromptRequestLogEntry(
            request_id=uuid.uuid4().hex,
            timestamp=datetime.now(timezone.utc).isoformat(),
            project_id=project_id,
            menu_id=menu_id,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            context_summary=context_summary or "",
        )
        payload = json.dumps(entry.to_dict(), ensure_ascii=False)
        with self._lock:
            with self._storage_path.open("a", encoding="utf-8") as file:
                file.write(payload + "\n")
        return entry

    def list_recent(self, limit: int = 50) -> List[PromptRequestLogEntry]:
        if limit <= 0:
            return []

        with self._lock:
            try:
                lines = self._storage_path.read_text(encoding="utf-8").splitlines()
            except FileNotFoundError:
                return []

        entries: List[PromptRequestLogEntry] = []
        for raw in lines[-limit:]:
            if not raw.strip():
                continue
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                continue
            entry = PromptRequestLogEntry.from_dict(payload if isinstance(payload, dict) else {})
            if entry is not None:
                entries.append(entry)

        entries.reverse()
        return entries

    def purge(self) -> None:
        """Delete all recorded entries."""

        with self._lock:
            self._storage_path.write_text("", encoding="utf-8")
