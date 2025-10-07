from __future__ import annotations

from pathlib import Path
import sys

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.prompt_request_log import (
    PromptRequestLogEntry,
    PromptRequestLogService,
)


def test_record_and_list_recent(tmp_path: Path) -> None:
    log_path = tmp_path / "prompt_requests.log"
    service = PromptRequestLogService(log_path)

    service.record_request(
        project_id="project-1",
        menu_id="feature-list",
        system_prompt="system",
        user_prompt="user",
        context_summary="summary",
    )
    second = service.record_request(
        project_id="project-2",
        menu_id="defect-report",
        system_prompt="system-2",
        user_prompt="user-2",
        context_summary="",
    )

    entries = service.list_recent()
    assert len(entries) == 2
    assert entries[0].request_id == second.request_id
    assert entries[0].context_summary == ""
    assert entries[1].project_id == "project-1"


def test_list_recent_ignores_invalid_rows(tmp_path: Path) -> None:
    log_path = tmp_path / "prompt_requests.log"
    log_path.write_text("not json\n{}\n", encoding="utf-8")

    service = PromptRequestLogService(log_path)
    service.record_request(
        project_id="project",
        menu_id="feature-list",
        system_prompt="system",
        user_prompt="user",
    )

    entries = service.list_recent(limit=5)
    assert len(entries) == 1
    assert isinstance(entries[0], PromptRequestLogEntry)
