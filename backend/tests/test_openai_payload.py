from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Ensure the backend/app package is importable when running tests from the repository root.
BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.openai_payload import OpenAIMessageBuilder


def test_text_message_appends_file_parts() -> None:
    message = OpenAIMessageBuilder.text_message(
        "user",
        "hello",
        file_ids=["file-a", "file-b"],
    )

    assert message["role"] == "user"
    assert message["content"][0] == {"type": "input_text", "text": "hello"}
    assert message["content"][1:] == [
        {"type": "input_file", "file_id": "file-a"},
        {"type": "input_file", "file_id": "file-b"},
    ]


def test_normalize_messages_allows_input_file_parts() -> None:
    raw_messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "summary"},
                {"type": "input_file", "file_id": "file-42"},
            ],
        }
    ]

    normalized = OpenAIMessageBuilder.normalize_messages(raw_messages)

    assert normalized == [
        {
            "role": "user",
            "content": [
                {"type": "input_text", "text": "summary"},
                {"type": "input_file", "file_id": "file-42"},
            ],
        }
    ]


def test_text_message_rejects_blank_file_id() -> None:
    with pytest.raises(ValueError):
        OpenAIMessageBuilder.text_message("user", "hello", file_ids=[" "])
