from __future__ import annotations

import sys
from pathlib import Path

# Ensure the backend/app package is importable when running tests from the repository root.
BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.ai_generation import AIGenerationService, DefectPromptResources
from app.services.prompt_config import PromptResourcesConfig


def test_merge_defect_prompt_resources_prefers_parsed_values():
    parsed = DefectPromptResources(
        judgement_criteria="Parsed judgement",
        output_example="",
        conversation=[],
    )
    config = PromptResourcesConfig(
        judgement_criteria="Config judgement",
        output_example="Config example",
    )

    merged = AIGenerationService._merge_defect_prompt_resources(parsed, config)

    assert merged is not None
    assert merged.judgement_criteria == "Parsed judgement"
    assert merged.output_example == "Config example"
    assert merged.conversation == []


def test_merge_defect_prompt_resources_falls_back_to_config():
    config = PromptResourcesConfig(
        judgement_criteria="Config judgement",
        output_example="Config example",
    )

    merged = AIGenerationService._merge_defect_prompt_resources(None, config)

    assert merged is not None
    assert merged.judgement_criteria == "Config judgement"
    assert merged.output_example == "Config example"
    assert merged.conversation == []


def test_merge_defect_prompt_resources_handles_absence():
    merged = AIGenerationService._merge_defect_prompt_resources(None, None)
    assert merged is None
