from __future__ import annotations

import io
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict

import pytest

pytest.importorskip("pandas")
pytest.importorskip("openpyxl")
from fastapi import UploadFile
from openpyxl import Workbook
from starlette.datastructures import Headers

BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.prompt_config import PromptConfig, _DEFAULT_PROMPTS
from app.services.security_report import CRITERIA_REQUIRED_COLUMNS, SecurityReportService


class _StubDriveService:
    def __init__(self, payload: bytes, exam_number: str = "GS-B-12-3456") -> None:
        self._payload = payload
        self.criteria_calls: list[Dict[str, Any]] = []
        self.project_calls: list[Dict[str, Any]] = []
        self.exam_number = exam_number

    async def download_shared_security_criteria(self, *, google_id: str | None, file_name: str) -> bytes:
        self.criteria_calls.append({"google_id": google_id, "file_name": file_name})
        return self._payload

    async def get_project_exam_number(self, *, project_id: str, google_id: str | None) -> str:
        self.project_calls.append({"project_id": project_id, "google_id": google_id})
        return self.exam_number


class _StubPromptConfigService:
    def __init__(self, config: PromptConfig | None = None) -> None:
        self._config = config or _DEFAULT_PROMPTS["security-report"].model_copy(deep=True)

    def get_runtime_prompt(self, menu_id: str) -> PromptConfig:
        if menu_id != "security-report":
            raise KeyError(menu_id)
        return self._config


class _StubPromptRequestLogService:
    def __init__(self) -> None:
        self.records: list[Dict[str, str]] = []

    def record_request(
        self,
        *,
        project_id: str,
        menu_id: str,
        system_prompt: str,
        user_prompt: str,
        context_summary: str | None = None,
    ) -> SimpleNamespace:
        entry = {
            "project_id": project_id,
            "menu_id": menu_id,
            "system_prompt": system_prompt,
            "user_prompt": user_prompt,
            "context_summary": context_summary or "",
        }
        self.records.append(entry)
        return SimpleNamespace(**entry)


class _StubResponses:
    def __init__(self) -> None:
        self.calls: list[Dict[str, Any]] = []

    def create(self, **kwargs: Any) -> None:
        self.calls.append(kwargs)
        raise AssertionError("Unexpected OpenAI call during test")


class _StubOpenAI:
    def __init__(self) -> None:
        self.responses = _StubResponses()


def _criteria_workbook_bytes() -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(list(CRITERIA_REQUIRED_COLUMNS))
    sheet.append(
        [
            "SQL Injection",
            "SQL Injection 위험",
            "High",
            "A",
            "보안성",
            "SQL Injection에 대한 설명",
            "0",
        ]
    )
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def _build_upload(html: str) -> UploadFile:
    return UploadFile(
        file=io.BytesIO(html.encode("utf-8")),
        filename="invicti.html",
        headers=Headers({"content-type": "text/html"}),
    )


@pytest.mark.anyio
async def test_generate_csv_report_builds_expected_rows() -> None:
    criteria_bytes = _criteria_workbook_bytes()
    drive = _StubDriveService(criteria_bytes)
    prompt_service = _StubPromptConfigService()
    log_service = _StubPromptRequestLogService()
    service = SecurityReportService(
        drive_service=drive,
        prompt_config_service=prompt_service,
        prompt_request_log_service=log_service,
        openai_client=_StubOpenAI(),
    )

    html_report = """
    <html>
      <body>
        <table class="detailed-scan">
          <tbody>
            <tr class="high-severity">
              <td>High</td>
              <td><a href="#finding-1">SQL Injection</a></td>
              <td>detail</td>
              <td>/login</td>
              <td>param</td>
            </tr>
          </tbody>
        </table>
        <div id="finding-1">
          <h2>Finding Description</h2>
          <p>SQL injection details</p>
          <h3>Evidence</h3>
          <p>Proof details</p>
        </div>
      </body>
    </html>
    """

    upload = _build_upload(html_report)

    result = await service.generate_csv_report(
        invicti_upload=upload,
        project_id="proj-001",
        google_id="user-123",
    )

    assert drive.criteria_calls == [{"google_id": "user-123", "file_name": "보안성 결함판단기준표 v1.0.xlsx"}]
    assert drive.project_calls == [{"project_id": "proj-001", "google_id": "user-123"}]
    assert log_service.records
    header = result.csv_text.splitlines()[0]
    assert header.startswith("순번,시험환경 OS")
    assert header.split(",")[-1] == "매핑 유형"
    assert "SQL Injection" in result.csv_text
    assert "High" in result.csv_text
    assert "기준표 매칭" in result.csv_text
    assert result.filename == "GS-B-12-3456 보안성 결함리포트 v1.0.csv"
