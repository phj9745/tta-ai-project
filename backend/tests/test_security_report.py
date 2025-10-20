from __future__ import annotations

import io
import sys
import json
from pathlib import Path
from typing import Any, Dict
from types import SimpleNamespace

import pytest
from fastapi import UploadFile
from openpyxl import Workbook
from starlette.datastructures import Headers

# Ensure the backend/app package is importable when running tests from the repository root.
BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.prompt_config import PromptConfig, _DEFAULT_PROMPTS
from app.services.security_report import (
    SecurityReportService,
    _CRITERIA_REQUIRED_COLUMNS,
)


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
        self.requests: list[str] = []

    def get_runtime_prompt(self, menu_id: str) -> PromptConfig:
        self.requests.append(menu_id)
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


class _SuccessfulOpenAI:
    def __init__(self, payload: Dict[str, Any]) -> None:
        self.responses = _AIResponsesSuccess(payload)


class _AIResponsesSuccess:
    def __init__(self, payload: Dict[str, Any]) -> None:
        self.payload = payload
        self.calls: list[Dict[str, Any]] = []

    def create(self, **kwargs: Any) -> SimpleNamespace:
        self.calls.append(kwargs)
        return SimpleNamespace(output_text=json.dumps(self.payload))


def _criteria_workbook_bytes() -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(list(_CRITERIA_REQUIRED_COLUMNS))
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
        <table class=\"detailed-scan\">
          <thead>
            <tr><th>Severity</th><th>Name</th><th>Path</th><th>Status</th><th>Parameter</th></tr>
          </thead>
          <tbody>
            <tr class=\"high-severity\">
              <td>High</td>
              <td><a href=\"#finding-1\">SQL Injection</a></td>
              <td>/login</td>
              <td>Confirmed</td>
              <td>id</td>
            </tr>
            <tr class=\"low-severity\">
              <td>Low</td>
              <td><a href=\"#finding-2\">Low Risk</a></td>
              <td>/health</td>
              <td>Info</td>
              <td></td>
            </tr>
          </tbody>
        </table>
        <div id=\"finding-1\">
          <h2>Finding Description</h2>
          <p>SQL injection details</p>
          <h3>Evidence</h3>
          <p>Proof details</p>
        </div>
        <div id=\"finding-2\"><p>Ignored finding</p></div>
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
    assert log_service.records and log_service.records[0]["menu_id"] == "security-report"
    header = result.csv_text.splitlines()[0]
    assert header.startswith("순번,시험환경 OS")
    assert header.split(",")[-1] == "매핑 유형"
    assert "SQL Injection" in result.csv_text
    assert "High" in result.csv_text
    assert "기준표 매칭" in result.csv_text
    assert result.filename == "[GS-B-12-3456] 보안성 결함리포트 v1.0.csv"
    assert "A,보안성" in result.csv_text


@pytest.mark.anyio
async def test_generate_csv_report_uses_ai_when_no_match() -> None:
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(list(_CRITERIA_REQUIRED_COLUMNS))
    buffer = io.BytesIO()
    workbook.save(buffer)

    ai_payload = {
        "summary": "약한 암호 취약점",
        "description": "약한 암호가 사용되고 있습니다.",
        "recommendation": "강한 암호를 사용하세요",
        "category": "보안성",
        "occurrence": "A",
    }

    drive = _StubDriveService(buffer.getvalue(), exam_number="GS-B-98-7654")
    ai_client = _SuccessfulOpenAI(ai_payload)
    prompt_service = _StubPromptConfigService()
    log_service = _StubPromptRequestLogService()
    service = SecurityReportService(  # type: ignore[arg-type]
        drive_service=drive,
        prompt_config_service=prompt_service,
        prompt_request_log_service=log_service,
        openai_client=ai_client,
    )

    html_report = """
    <html>
      <body>
        <table class=\"detailed-scan\">
          <thead>
            <tr><th>Severity</th><th>Name</th><th>Path</th><th>Status</th><th>Parameter</th></tr>
          </thead>
          <tbody>
            <tr class=\"high-severity\">
              <td>High</td>
              <td><a href=\"#WeakCipherSuite\">Weak Cipher Suite Supported</a></td>
              <td>/secure</td>
              <td>Confirmed</td>
              <td></td>
            </tr>
          </tbody>
        </table>
        <div id=\"WeakCipherSuite\">
          <h2>Details</h2>
          <p>Weak cipher list.</p>
        </div>
      </body>
    </html>
    """

    upload = _build_upload(html_report)

    result = await service.generate_csv_report(
        invicti_upload=upload,
        project_id="proj-002",
        google_id="user-456",
    )

    assert "약한 암호 활성화" in result.csv_text
    assert "AI 생성" in result.csv_text
    assert "A,보안성" in result.csv_text
    assert result.filename == "[GS-B-98-7654] 보안성 결함리포트 v1.0.csv"
    assert prompt_service.requests  # ensure 프롬프트 구성을 조회했다
    assert log_service.records and log_service.records[0]["project_id"] == "proj-002"
