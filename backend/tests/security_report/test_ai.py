from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict

import pytest

pytest.importorskip("pandas")

BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.prompt_config import PromptConfig, _DEFAULT_PROMPTS
from app.services.security_report.ai import SecurityReportAI
from app.services.security_report.models import InvictiFinding


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
    def __init__(self, payload: Dict[str, Any] | None = None) -> None:
        self.payload = payload or {}
        self.calls: list[Dict[str, Any]] = []

    def create(self, **kwargs: Any) -> SimpleNamespace:
        self.calls.append(kwargs)
        return SimpleNamespace(output_text=json.dumps(self.payload))


class _StubOpenAI:
    def __init__(self, payload: Dict[str, Any] | None = None) -> None:
        self.responses = _StubResponses(payload)


@pytest.fixture()
def sample_finding() -> InvictiFinding:
    return InvictiFinding(
        name="SQL Injection",
        severity="High",
        severity_rank=3,
        path="/login",
        anchor_id="finding-1",
        description_html="<div>detail</div>",
        description_text="detail",
        evidence_text="evidence",
    )


@pytest.mark.anyio
async def test_fill_template_field_replaces_known_placeholders(sample_finding: InvictiFinding) -> None:
    openai_client = _StubOpenAI()
    ai = SecurityReportAI(
        prompt_config_service=_StubPromptConfigService(),
        prompt_request_log_service=_StubPromptRequestLogService(),
        openai_client=openai_client,
    )

    template = "경로는 [URL] 입니다."
    result = await ai.fill_template_field(
        template,
        sample_finding,
        project_id="proj-1",
        placeholder_values={"URL": sample_finding.path},
    )

    assert result == "경로는 /login 입니다."
    assert openai_client.responses.calls == []


@pytest.mark.anyio
async def test_fill_template_field_invokes_openai_for_missing(sample_finding: InvictiFinding) -> None:
    payload = {"summary": "요약"}
    openai_client = _StubOpenAI(payload)
    log_service = _StubPromptRequestLogService()
    ai = SecurityReportAI(
        prompt_config_service=_StubPromptConfigService(),
        prompt_request_log_service=log_service,
        openai_client=openai_client,
    )

    template = "요약: [summary]"
    result = await ai.fill_template_field(
        template,
        sample_finding,
        project_id="proj-1",
        placeholder_values={},
    )

    assert result == "요약: 요약"
    assert openai_client.responses.calls
    assert log_service.records


@pytest.mark.anyio
async def test_generate_new_finding_payload_returns_json(sample_finding: InvictiFinding) -> None:
    payload = {"summary": "요약", "description": "설명", "recommendation": "가이드"}
    ai = SecurityReportAI(
        prompt_config_service=_StubPromptConfigService(),
        prompt_request_log_service=_StubPromptRequestLogService(),
        openai_client=_StubOpenAI(payload),
    )

    response = await ai.generate_new_finding_payload(
        sample_finding,
        project_id="proj-1",
        placeholder_values={"URL": "/login"},
    )

    assert response["summary"] == "요약"
    assert response["description"] == "설명"
