from __future__ import annotations

import io
import json
import sys
from pathlib import Path
from types import MethodType, SimpleNamespace
from typing import Any

import pytest
from fastapi import HTTPException, UploadFile
from starlette.datastructures import Headers
import httpx

# Ensure the backend/app package is importable when running tests from the repository root.
BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.config import Settings
from app.services.ai_generation import AIGenerationService
from app.services.openai_payload import OpenAIMessageBuilder
from openai import BadRequestError, OpenAIError, RateLimitError


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
        self.output_text = "col1,col2\nvalue1,value2"

    def create(self, **kwargs: object) -> SimpleNamespace:
        self.calls.append(kwargs)
        return SimpleNamespace(output_text=self.output_text)


class _StubClient:
    def __init__(self) -> None:
        self.files = _StubFiles()
        self.responses = _StubResponses()


class _SpyRequestLogService:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def record_request(
        self,
        *,
        project_id: str,
        menu_id: str,
        system_prompt: str,
        user_prompt: str,
        context_summary: str | None = None,
        response_text: str | None = None,
    ) -> SimpleNamespace:
        self.calls.append(
            {
                "project_id": project_id,
                "menu_id": menu_id,
                "system_prompt": system_prompt,
                "user_prompt": user_prompt,
                "context_summary": context_summary,
                "response_text": response_text,
            }
        )
        return SimpleNamespace()


def _build_rate_limit_error(message: str = "quota exceeded") -> RateLimitError:
    request = httpx.Request("POST", "https://api.openai.com/v1/responses")
    response = httpx.Response(
        429,
        request=request,
        json={"error": {"message": message, "code": "insufficient_quota"}},
    )
    return RateLimitError(message=message, response=response, body=response.json())


def _build_bad_request_error(message: str) -> BadRequestError:
    request = httpx.Request("POST", "https://api.openai.com/v1/responses")
    response = httpx.Response(
        400,
        request=request,
        json={"error": {"message": message, "code": "invalid_prompt"}},
    )
    return BadRequestError(message=message, response=response, body=response.json())


def _settings(**overrides: Any) -> Settings:
    params: dict[str, Any] = {
        "client_id": "",
        "client_secret": "",
        "redirect_uri": "",
        "frontend_redirect_url": "http://localhost",
        "tokens_path": Path("/tmp/tokens.db"),
        "openai_api_key": "test-key",
        "openai_model": "gpt-test",
        "builtin_template_root": None,
    }
    params.update(overrides)
    return Settings(**params)


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def test_locate_builtin_source_uses_override_directory(tmp_path: Path) -> None:
    template_root = tmp_path / "builtin"
    target_dir = template_root / "가.계획"
    target_dir.mkdir(parents=True)
    target_file = target_dir / "override-only.xlsx"
    target_file.write_bytes(b"dummy")

    service = AIGenerationService(_settings(builtin_template_root=template_root))

    resolved, attempted = service._locate_builtin_source(
        "template/가.계획/override-only.xlsx"
    )

    assert resolved == target_file
    assert str(target_file) in {str(path) for path in attempted}


def test_locate_builtin_source_accepts_direct_file_override(tmp_path: Path) -> None:
    target_file = tmp_path / "override-only.xlsx"
    target_file.write_bytes(b"dummy")

    service = AIGenerationService(_settings(builtin_template_root=target_file))

    resolved, attempted = service._locate_builtin_source("template/override-only.xlsx")

    assert resolved == target_file
    assert str(target_file) in {str(path) for path in attempted}


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
        "사용자_매뉴얼.pdf",
        "GS-B-XX-XXXX 기능리스트 v1.0.pdf",
    ]

    template_upload = stub_client.files.created[1]
    assert isinstance(template_upload["content"], bytes)
    assert template_upload["content"].startswith(b"%PDF")

    # The response payload should include input_file parts for each uploaded file.
    assert len(stub_client.responses.calls) == 1
    response_payload = stub_client.responses.calls[0]
    # Ensure the payload we send to OpenAI is JSON serialisable, mirroring the
    # client-side validation performed by the OpenAI SDK.
    json.dumps(response_payload)

    assert "presence_penalty" not in response_payload
    assert "frequency_penalty" not in response_payload

    messages = response_payload["input"]
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
    assert result.project_overview == (
        "이 프로그램은 value1 관련 프로그램이다.\n기능은\n- value2"
    )


@pytest.mark.anyio
async def test_generate_csv_extracts_project_overview_from_csv_row() -> None:
    service = AIGenerationService(_settings())
    stub_client = _StubClient()
    service._client = stub_client  # type: ignore[attr-defined]

    stub_client.responses.output_text = (
        "프로젝트 개요,이 프로젝트는 테스트입니다.\n"
        "대분류,중분류,소분류,기능 설명\n"
        "대1,중1,소1,기능 상세"
    )

    upload = UploadFile(
        file=io.BytesIO(b"Document body"),
        filename="요구사항.docx",
        headers=Headers({"content-type": "application/msword"}),
    )

    result = await service.generate_csv(
        project_id="proj-overview",
        menu_id="feature-list",
        uploads=[upload],
        metadata=[{"role": "required", "id": "user-manual", "label": "설명서"}],
    )

    assert result.project_overview == (
        "이 프로그램은 테스트 프로그램이다.\n기능은\n- 기능 상세"
    )
    assert result.csv_text == (
        "대분류,중분류,소분류,기능 설명\n대1,중1,소1,기능 상세"
    )


@pytest.mark.anyio
async def test_generate_csv_extracts_project_overview_with_colon_notation() -> None:
    service = AIGenerationService(_settings())
    stub_client = _StubClient()
    service._client = stub_client  # type: ignore[attr-defined]

    stub_client.responses.output_text = (
        "프로젝트 개요:이 프로젝트는 콜론 형식을 따릅니다.\n"
        "대분류,중분류,소분류,기능 설명\n"
        "대1,중1,소1,상세"
    )

    upload = UploadFile(
        file=io.BytesIO(b"Document body"),
        filename="요구사항.docx",
        headers=Headers({"content-type": "application/msword"}),
    )

    result = await service.generate_csv(
        project_id="proj-overview-colon",
        menu_id="feature-list",
        uploads=[upload],
        metadata=[{"role": "required", "id": "user-manual", "label": "설명서"}],
    )

    assert result.project_overview == (
        "이 프로그램은 콜론 형식을 따르는 프로그램이다.\n기능은\n- 상세"
    )
    assert result.csv_text == (
        "대분류,중분류,소분류,기능 설명\n대1,중1,소1,상세"
    )


@pytest.mark.anyio
async def test_generate_csv_extracts_project_overview_from_followup_row() -> None:
    service = AIGenerationService(_settings())
    stub_client = _StubClient()
    service._client = stub_client  # type: ignore[attr-defined]

    stub_client.responses.output_text = (
        "프로젝트 개요\n"
        "이 프로젝트는 행이 나뉘어 제공됩니다.\n"
        "대분류,중분류,소분류,기능 설명\n"
        "대1,중1,소1,상세"
    )

    upload = UploadFile(
        file=io.BytesIO(b"Document body"),
        filename="요구사항.docx",
        headers=Headers({"content-type": "application/msword"}),
    )

    result = await service.generate_csv(
        project_id="proj-overview-followup",
        menu_id="feature-list",
        uploads=[upload],
        metadata=[{"role": "required", "id": "user-manual", "label": "설명서"}],
    )

    assert result.project_overview == (
        "이 프로그램은 행이 나뉘어 제공되는 프로그램이다.\n기능은\n- 상세"
    )
    assert result.csv_text == (
        "대분류,중분류,소분류,기능 설명\n대1,중1,소1,상세"
    )


@pytest.mark.anyio
async def test_generate_csv_converts_required_csv_documents_to_pdf() -> None:
    service = AIGenerationService(_settings())
    stub_client = _StubClient()
    service._client = stub_client  # type: ignore[attr-defined]

    upload = UploadFile(
        file=io.BytesIO("제목,내용\n항목1,값1".encode("utf-8")),
        filename="사용자_매뉴얼.csv",
        headers=Headers({"content-type": "text/csv"}),
    )

    metadata = [{"role": "required", "id": "user-manual", "label": "사용자 설명서"}]

    result = await service.generate_csv(
        project_id="proj-csv",
        menu_id="feature-list",
        uploads=[upload],
        metadata=metadata,
    )

    assert result.csv_text == "col1,col2\nvalue1,value2"

    assert [entry["name"] for entry in stub_client.files.created] == [
        "사용자_매뉴얼.pdf",
        "GS-B-XX-XXXX 기능리스트 v1.0.pdf",
    ]
    assert stub_client.files.created[0]["content"].startswith(b"%PDF")



@pytest.mark.anyio
async def test_generate_csv_includes_testcase_template() -> None:
    service = AIGenerationService(_settings())
    stub_client = _StubClient()
    service._client = stub_client  # type: ignore[attr-defined]

    upload = UploadFile(
        file=io.BytesIO(b"Requirement body"),
        filename="요구사항.docx",
        headers=Headers({"content-type": "application/msword"}),
    )

    result = await service.generate_csv(
        project_id="proj-testcase",
        menu_id="testcase-generation",
        uploads=[upload],
        metadata=[{"role": "required", "id": "user-manual", "label": "사용자 설명서"}],
    )

    assert [entry["name"] for entry in stub_client.files.created] == [
        "요구사항.pdf",
        "GS-B-XX-XXXX 테스트케이스.pdf",
    ]

    template_upload = stub_client.files.created[1]
    assert isinstance(template_upload["content"], bytes)
    assert template_upload["content"].startswith(b"%PDF")

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
                    "image_url": {"url": "data:image/png;base64,abc123"},
                }
            )
            message["content"].append(  # type: ignore[index]
                {
                    "type": "input_image",
                    "image_url": {"url": "https://example.com/additional.png"},
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


@pytest.mark.anyio
async def test_generate_csv_surfaces_openai_response_error() -> None:
    service = AIGenerationService(_settings())
    stub_client = _StubClient()
    service._client = stub_client  # type: ignore[attr-defined]

    def _raise_response_error(**kwargs: object) -> None:
        raise OpenAIError("temporary overload")

    stub_client.responses.create = _raise_response_error  # type: ignore[assignment]

    upload = UploadFile(
        file=io.BytesIO(b"Primary document"),
        filename="요구사항.docx",
        headers=Headers({"content-type": "application/msword"}),
    )

    with pytest.raises(HTTPException) as excinfo:
        await service.generate_csv(
            project_id="proj-error",
            menu_id="feature-list",
            uploads=[upload],
            metadata=[{"role": "required", "id": "doc-1", "label": "주요 문서"}],
        )

    assert excinfo.value.status_code == 502
    assert "OpenAI 호출 중 오류가 발생했습니다" in excinfo.value.detail
    assert "temporary overload" in excinfo.value.detail


@pytest.mark.anyio
async def test_generate_csv_surfaces_rate_limit_error() -> None:
    service = AIGenerationService(_settings())
    stub_client = _StubClient()
    service._client = stub_client  # type: ignore[attr-defined]

    def _raise_rate_limit(**kwargs: object) -> None:
        raise _build_rate_limit_error(
            "You exceeded your current quota, please check your plan and billing details."
        )

    stub_client.responses.create = _raise_rate_limit  # type: ignore[assignment]

    upload = UploadFile(
        file=io.BytesIO(b"Primary document"),
        filename="요구사항.docx",
        headers=Headers({"content-type": "application/msword"}),
    )

    with pytest.raises(HTTPException) as excinfo:
        await service.generate_csv(
            project_id="proj-rate-limit",
            menu_id="feature-list",
            uploads=[upload],
            metadata=[{"role": "required", "id": "doc-1", "label": "주요 문서"}],
        )

    assert excinfo.value.status_code == 429
    assert "OpenAI 사용량 한도를 초과했습니다" in excinfo.value.detail
    assert "You exceeded your current quota" in excinfo.value.detail


@pytest.mark.anyio
async def test_generate_csv_includes_message_for_unexpected_error() -> None:
    service = AIGenerationService(_settings())
    stub_client = _StubClient()
    service._client = stub_client  # type: ignore[attr-defined]

    def _raise_type_error(**kwargs: object) -> None:
        raise TypeError("Object of type bytes is not JSON serializable")

    stub_client.responses.create = _raise_type_error  # type: ignore[assignment]

    upload = UploadFile(
        file=io.BytesIO(b"Primary document"),
        filename="요구사항.docx",
        headers=Headers({"content-type": "application/msword"}),
    )

    with pytest.raises(HTTPException) as excinfo:
        await service.generate_csv(
            project_id="proj-type-error",
            menu_id="feature-list",
            uploads=[upload],
            metadata=[{"role": "required", "id": "doc-1", "label": "주요 문서"}],
        )

    assert excinfo.value.status_code == 502
    assert "예기치 않은 오류" in excinfo.value.detail
    assert "Object of type bytes is not JSON serializable" in excinfo.value.detail


@pytest.mark.anyio
async def test_generate_csv_surfaces_bad_request_error_detail() -> None:
    service = AIGenerationService(_settings())
    stub_client = _StubClient()
    service._client = stub_client  # type: ignore[attr-defined]

    def _raise_bad_request(**kwargs: object) -> None:
        raise _build_bad_request_error("Invalid prompt format")

    stub_client.responses.create = _raise_bad_request  # type: ignore[assignment]

    upload = UploadFile(
        file=io.BytesIO(b"Primary document"),
        filename="요구사항.docx",
        headers=Headers({"content-type": "application/msword"}),
    )

    with pytest.raises(HTTPException) as excinfo:
        await service.generate_csv(
            project_id="proj-bad-request",
            menu_id="feature-list",
            uploads=[upload],
            metadata=[{"role": "required", "id": "doc-1", "label": "주요 문서"}],
        )

    assert excinfo.value.status_code == 502
    assert "Invalid prompt format" in excinfo.value.detail


@pytest.mark.anyio
async def test_generate_csv_logs_response_when_csv_invalid() -> None:
    service = AIGenerationService(_settings())
    stub_client = _StubClient()
    service._client = stub_client  # type: ignore[attr-defined]

    def _empty_csv_response(**kwargs: object) -> SimpleNamespace:
        stub_client.responses.calls.append(kwargs)
        return SimpleNamespace(output_text="```csv\n\n```")

    stub_client.responses.create = _empty_csv_response  # type: ignore[assignment]

    spy_log = _SpyRequestLogService()
    service._request_log_service = spy_log  # type: ignore[attr-defined]

    upload = UploadFile(
        file=io.BytesIO(b"Primary document"),
        filename="요구사항.docx",
        headers=Headers({"content-type": "application/msword"}),
    )

    with pytest.raises(HTTPException) as excinfo:
        await service.generate_csv(
            project_id="proj-error",
            menu_id="feature-list",
            uploads=[upload],
            metadata=[{"role": "required", "id": "doc-1", "label": "주요 문서"}],
        )

    assert excinfo.value.status_code == 502
    assert "생성된 CSV 내용이 비어 있습니다." in str(excinfo.value.detail)
    assert spy_log.calls
    last_call = spy_log.calls[-1]
    assert last_call["project_id"] == "proj-error"
    assert last_call["menu_id"] == "feature-list"
    assert last_call["response_text"] == "```csv\n\n```"


@pytest.mark.anyio
async def test_generate_csv_surfaces_openai_file_upload_error() -> None:
    service = AIGenerationService(_settings())
    stub_client = _StubClient()
    service._client = stub_client  # type: ignore[attr-defined]

    def _raise_file_error(
        self, *, file: tuple[str, io.BytesIO], purpose: str
    ) -> SimpleNamespace:
        raise OpenAIError("file quota reached")

    stub_client.files.create = MethodType(_raise_file_error, stub_client.files)

    upload = UploadFile(
        file=io.BytesIO(b"Primary document"),
        filename="요구사항.docx",
        headers=Headers({"content-type": "application/msword"}),
    )

    with pytest.raises(HTTPException) as excinfo:
        await service.generate_csv(
            project_id="proj-file-error",
            menu_id="feature-list",
            uploads=[upload],
            metadata=[{"role": "required", "id": "doc-1", "label": "주요 문서"}],
        )

    assert excinfo.value.status_code == 502
    assert "OpenAI 파일 업로드 중 오류가 발생했습니다" in excinfo.value.detail
    assert "file quota reached" in excinfo.value.detail

