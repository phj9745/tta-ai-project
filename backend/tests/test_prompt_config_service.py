from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

# Ensure the backend/app package is importable when running tests from the repository root.
BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.prompt_config import PromptConfigService


@pytest.fixture
def prompt_storage(tmp_path):
    return tmp_path / "prompt_configs.json"


def test_update_config_overrides_are_used_at_runtime(prompt_storage):
    service = PromptConfigService(prompt_storage)

    default_prompt = service.get_runtime_prompt("testcase-generation")
    assert default_prompt.label == "테스트케이스 생성"

    updated_text = "테스트 시나리오만 출력하세요."
    service.update_config("testcase-generation", {"userPrompt": updated_text})

    runtime_prompt = service.get_runtime_prompt("testcase-generation")
    assert runtime_prompt.user_prompt == updated_text

    stored_payload = json.loads(prompt_storage.read_text(encoding="utf-8"))
    assert stored_payload["testcase-generation"]["userPrompt"] == updated_text

    reloaded_service = PromptConfigService(prompt_storage)
    reloaded_prompt = reloaded_service.get_runtime_prompt("testcase-generation")
    assert reloaded_prompt.user_prompt == updated_text
