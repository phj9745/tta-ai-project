from __future__ import annotations

import io
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import UploadFile
from starlette.datastructures import Headers

# Ensure the backend/app package is importable when running tests from the repository root.
BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.config import Settings
from app.services.ai_generation import AIGenerationService
from app.services.openai_payload import OpenAIMessageBuilder


class _StubFiles:
    def __init__(self) -> None:
        self.created: list[dict[str, object]] = []
        self.deleted: list[str] = []

    def create(self, *, file: tuple[str, io.BytesIO], purpose: str) -> SimpleNamespace:
        name, handle = file
        # Read the content to verify what would be sent to OpenAI.
        content = handle.read()
        self.created.append({"name": name, "content": content, "purpose": purpose})
        return SimpleNamespace(id=f"file-{len(self.created)}")

    def delete(self, *, file_id: str) -> None:
        self.deleted.append(file_id)


class _StubResponses:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def create(self, **kwargs: object) -> SimpleNamespace:
        self.calls.append(kwargs)
        return SimpleNamespace(output_text="col1,col2\nvalue1,value2")


class _StubClient:
    def __init__(self) -> None:
        self.files = _StubFiles()
        self.responses = _StubResponses()


def _settings() -> Settings:
    return Settings(
        client_id="",
        client_secret="",
        redirect_uri="",
        frontend_redirect_url="http://localhost",
        tokens_path=Path("/tmp/tokens.db"),
        openai_api_key="test-key",
        openai_model="gpt-test",
    )


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
async def test_generate_csv_attaches_files_and_cleans_up() -> None:
    service = AIGenerationService(_settings())
    stub_client = _StubClient()
    service._client = stub_client  # type: ignore[attr-defined]

    uploads = [
        (
            "사용자_매뉴얼.docx",
            io.BytesIO(b"Document body 1"),
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ),
        (
            "설계_이미지.png",
            io.BytesIO(b"Image bytes"),
            "image/png",
        ),
    ]

    fastapi_uploads: list[UploadFile] = []
    for name, file, content_type in uploads:
        headers = Headers({"content-type": content_type})
        upload = UploadFile(file=file, filename=name, headers=headers)
        fastapi_uploads.append(upload)

    metadata = [
        {"role": "required", "id": "user-manual", "label": "사용자 설명서"},
        {"role": "additional", "description": "설계 참고 이미지"},
    ]

    result = await service.generate_csv(
        project_id="proj-123",
        menu_id="feature-list",
        uploads=fastapi_uploads,
        metadata=metadata,
    )

    # Ensure each upload (including the built-in template) was transmitted as a file
    # to OpenAI with the assistants purpose.
    assert [entry["purpose"] for entry in stub_client.files.created] == [
        "assistants",
        "assistants",
    ]
    assert [entry["name"] for entry in stub_client.files.created] == [
        "사용자_매뉴얼.docx",
        "GS-B-XX-XXXX 기능리스트 v1.0.pdf",
    ]

    template_upload = stub_client.files.created[1]
    assert isinstance(template_upload["content"], bytes)
    assert template_upload["content"].startswith(b"%PDF")

    # The response payload should include input_file parts for each uploaded file.
    assert len(stub_client.responses.calls) == 1
    messages = stub_client.responses.calls[0]["input"]
    assert isinstance(messages, list)
    user_message = messages[1]
    file_parts = [
        part
        for part in user_message["content"]
        if part["type"] in {"input_file", "input_image"}
    ]
    assert file_parts == [
        {"type": "input_file", "file_id": "file-1"},
        {
            "type": "input_image",
            "image_url": "data:image/png;base64,SW1hZ2UgYnl0ZXM=",
        },
        {"type": "input_file", "file_id": "file-2"},
    ]

    # The text portions should not include the raw upload bodies.
    text_parts = [part["text"] for part in user_message["content"] if part["type"] == "input_text"]
    combined_text = "\n".join(text_parts)
    assert "Document body 1" not in combined_text
    assert "Image bytes" not in combined_text

    # Temporary files should be cleaned up after the request completes.
    assert stub_client.files.deleted == ["file-1"]

    assert result.csv_text == "col1,col2\nvalue1,value2"


@pytest.mark.anyio
async def test_generate_csv_supports_modern_response_payload() -> None:
    service = AIGenerationService(_settings())
    stub_client = _StubClient()
    service._client = stub_client  # type: ignore[attr-defined]

    def _modern_response(**kwargs: object) -> SimpleNamespace:
        stub_client.responses.calls.append(kwargs)
        return SimpleNamespace(
            output=[
                SimpleNamespace(
                    content=[
                        SimpleNamespace(
                            type="output_text",
                            text={"value": "col1,col2\nvalue1,value2", "annotations": []},
                        )
                    ]
                )
            ]
        )

    stub_client.responses.create = _modern_response  # type: ignore[assignment]

    upload = UploadFile(
        file=io.BytesIO(b"Primary document"),
        filename="요구사항.docx",
        headers=Headers({"content-type": "application/msword"}),
    )

    result = await service.generate_csv(
        project_id="proj-modern",
        menu_id="feature-list",
        uploads=[upload],
        metadata=[{"role": "required", "id": "doc-1", "label": "주요 문서"}],
    )

    assert result.csv_text == "col1,col2\nvalue1,value2"


@pytest.mark.anyio
async def test_generate_csv_normalizes_image_url_content(monkeypatch: pytest.MonkeyPatch) -> None:
    service = AIGenerationService(_settings())
    stub_client = _StubClient()
    service._client = stub_client  # type: ignore[attr-defined]

    original_text_message = OpenAIMessageBuilder.text_message

    def _augmented_text_message(*args: object, **kwargs: object):
        message = original_text_message(*args, **kwargs)  # type: ignore[misc]
        if message["role"] == "user":
            message["content"].append(  # type: ignore[index]
                {
                    "type": "input_image",
                    "image_url": "data:image/png;base64,abc123",
                }
            )
            message["content"].append(  # type: ignore[index]
                {
                    "type": "input_image",
                    "image_url": "https://example.com/additional.png",
                }
            )
        return message

    monkeypatch.setattr(OpenAIMessageBuilder, "text_message", _augmented_text_message)

    upload = UploadFile(
        file=io.BytesIO(b"Primary document"),
        filename="요구사항.docx",
        headers=Headers({"content-type": "application/msword"}),
    )

    result = await service.generate_csv(
        project_id="proj-456",
        menu_id="feature-list",
        uploads=[upload],
        metadata=[{"role": "required", "id": "doc-1", "label": "주요 문서"}],
    )

    assert result.csv_text == "col1,col2\nvalue1,value2"

    assert len(stub_client.responses.calls) == 1
    user_message = stub_client.responses.calls[0]["input"][1]
    image_parts = [
        part
        for part in user_message["content"]
        if part["type"] == "input_image"
    ]
    assert {
        "type": "input_image",
        "image_url": "data:image/png;base64,abc123",
    } in image_parts
    assert {
        "type": "input_image",
        "image_url": "https://example.com/additional.png",
    } in image_parts

