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


def test_text_message_appends_image_parts_from_data_url() -> None:
    data_url = "data:image/png;base64,abc123"
    message = OpenAIMessageBuilder.text_message(
        "user",
        "see this",
        attachments=[{"image_url": data_url, "kind": "image"}],
    )

    assert message["role"] == "user"
    assert message["content"][1:] == [
        {"type": "input_image", "image_url": {"url": data_url}}
    ]

    normalized = OpenAIMessageBuilder.normalize_messages([message])
    assert normalized[0]["content"][1:] == [
        {"type": "input_image", "image_url": {"url": data_url}}
    ]


def test_text_message_appends_image_parts_from_image_url() -> None:
    message = OpenAIMessageBuilder.text_message(
        "user",
        "look at this",
        attachments=[
            {
                "image_url": "https://example.com/external.png",
                "kind": "image",
            }
        ],
    )

    assert message["content"][1:] == [
        {
            "type": "input_image",
            "image_url": {"url": "https://example.com/external.png"},
        }
    ]

    normalized = OpenAIMessageBuilder.normalize_messages([message])
    assert normalized[0]["content"][1:] == [
        {
            "type": "input_image",
            "image_url": {"url": "https://example.com/external.png"},
        }
    ]


def test_text_message_accepts_image_url_alias() -> None:
    message = OpenAIMessageBuilder.text_message(
        "user",
        "alias",
        attachments=[{"url": "https://example.com/from-alias", "kind": "image"}],
    )

    assert message["content"][1:] == [
        {
            "type": "input_image",
            "image_url": {"url": "https://example.com/from-alias"},
        }
    ]


def test_text_message_rejects_image_without_url() -> None:
    with pytest.raises(ValueError):
        OpenAIMessageBuilder.text_message(
            "user", "missing", attachments=[{"kind": "image"}]
        )


def test_attachments_to_chat_completions_converts_images() -> None:
    attachments = [
        {"image_url": "data:image/png;base64,xyz456", "kind": "image"}
    ]

    completion_parts = OpenAIMessageBuilder.attachments_to_chat_completions(attachments)

    assert completion_parts == [
        {
            "type": "input_image",
            "image_url": {"url": "data:image/png;base64,xyz456"},
        }
    ]


def test_attachments_to_chat_completions_prefers_image_url() -> None:
    attachments = [
        {
            "file_id": "file-img-3",
            "image_url": "data:image/png;base64,abc123",
            "kind": "image",
        }
    ]

    completion_parts = OpenAIMessageBuilder.attachments_to_chat_completions(attachments)

    assert completion_parts == [
        {"type": "input_image", "image_url": {"url": "data:image/png;base64,abc123"}}
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


def test_normalize_messages_rejects_legacy_image_id() -> None:
    raw_messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "check"},
                {"type": "input_image", "image_id": "file-img-legacy"},
            ],
        }
    ]

    with pytest.raises(ValueError):
        OpenAIMessageBuilder.normalize_messages(raw_messages)


def test_normalize_messages_rejects_image_mapping() -> None:
    raw_messages = [
        {
            "role": "user",
            "content": [
                {
                    "type": "input_image",
                    "image_url": "openai://file-file-img-from-url",
                }
            ],
        }
    ]

    with pytest.raises(ValueError):
        OpenAIMessageBuilder.normalize_messages(raw_messages)


def test_normalize_messages_rejects_openai_scheme() -> None:
    raw_messages = [
        {
            "role": "user",
            "content": [
                {
                    "type": "input_image",
                    "image_url": "openai://file-file-img-from-url",
                }
            ],
        }
    ]

    with pytest.raises(ValueError):
        OpenAIMessageBuilder.normalize_messages(raw_messages)


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
                    "image_url": {"url": "https://example.com/image.png"},
                },
            ],
        }
    ]


def test_normalize_messages_preserves_data_image_url() -> None:
    data_url = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAUA"
    raw_messages = [
        {
            "role": "user",
            "content": [
                {
                    "type": "input_image",
                    "image_url": data_url,
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
                    "image_url": {"url": data_url},
                },
            ],
        }
    ]
