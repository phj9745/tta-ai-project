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


def test_text_message_appends_image_parts() -> None:
    message = OpenAIMessageBuilder.text_message(
        "user",
        "see this",
        attachments=[{"file_id": "img-1", "kind": "image"}],
    )

    assert message["role"] == "user"
    assert message["content"][1:] == [
        {"type": "input_image", "image_url": "openai://file/img-1"}
    ]

    normalized = OpenAIMessageBuilder.normalize_messages([message])
    assert normalized[0]["content"][1:] == [
        {"type": "input_image", "image": {"file_id": "img-1"}}
    ]


def test_attachments_to_chat_completions_converts_images() -> None:
    attachments = [{"file_id": "img-2", "kind": "image"}]

    completion_parts = OpenAIMessageBuilder.attachments_to_chat_completions(attachments)

    assert completion_parts == [
        {"type": "image_url", "image_url": "openai://file/img-2"}
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


def test_normalize_messages_converts_legacy_image_id() -> None:
    raw_messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "check"},
                {"type": "input_image", "image_id": "img-legacy"},
            ],
        }
    ]

    normalized = OpenAIMessageBuilder.normalize_messages(raw_messages)

    assert normalized == [
        {
            "role": "user",
            "content": [
                {"type": "input_text", "text": "check"},
                {"type": "input_image", "image": {"file_id": "img-legacy"}},
            ],
        }
    ]


def test_text_message_rejects_blank_file_id() -> None:
    with pytest.raises(ValueError):
        OpenAIMessageBuilder.text_message("user", "hello", file_ids=[" "])


def test_normalize_messages_accepts_image_mapping() -> None:
    raw_messages = [
        {
            "role": "user",
            "content": [
                {
                    "type": "input_image",
                    "image": {"file_id": "img-direct"},
                }
            ],
        }
    ]

    normalized = OpenAIMessageBuilder.normalize_messages(raw_messages)

    assert normalized == [
        {
            "role": "user",
            "content": [
                {
                    "type": "input_image",
                    "image": {"file_id": "img-direct"},
                },
            ],
        }
    ]


def test_normalize_messages_converts_image_url_string() -> None:
    raw_messages = [
        {
            "role": "user",
            "content": [
                {
                    "type": "input_image",
                    "image_url": "openai://file/img-from-url",
                }
            ],
        }
    ]

    normalized = OpenAIMessageBuilder.normalize_messages(raw_messages)

    assert normalized == [
        {
            "role": "user",
            "content": [
                {
                    "type": "input_image",
                    "image": {"file_id": "img-from-url"},
                },
            ],
        }
    ]


def test_normalize_messages_preserves_external_image_url() -> None:
    raw_messages = [
        {
            "role": "user",
            "content": [
                {
                    "type": "input_image",
                    "image_url": "https://example.com/image.png",
                }
            ],
        }
    ]

    normalized = OpenAIMessageBuilder.normalize_messages(raw_messages)

    assert normalized == [
        {
            "role": "user",
            "content": [
                {
                    "type": "input_image",
                    "image_url": "https://example.com/image.png",
                },
            ],
        }
    ]
