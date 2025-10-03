from __future__ import annotations

import asyncio
import io
import logging
import os
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Iterable, List, Literal

from fastapi import HTTPException, UploadFile
from openai import APIError, OpenAI

from ..config import Settings
from .openai_payload import AttachmentMetadata, OpenAIMessageBuilder


@dataclass
class BufferedUpload:
    name: str
    content: bytes
    content_type: str | None


@dataclass
class GeneratedCsv:
    filename: str
    content: bytes
    csv_text: str


@dataclass
class UploadContext:
    upload: BufferedUpload
    metadata: Dict[str, Any] | None


@dataclass
class PromptContextPreview:
    descriptor: str
    doc_id: str | None

_PROMPT_TEMPLATES: Dict[str, Dict[str, str]] = {
    "feature-list": {
        "system": "당신은 소프트웨어 기획 QA 리드입니다. 업로드된 요구사항을 기반으로 기능 정의서를 작성합니다.",
        "instruction": (
            "요구사항 자료에서 주요 기능을 발췌하여 CSV로 정리하세요. "
            "다음 열을 포함해야 합니다: 대분류, 중분류, 소분류. "
            "각 열은 템플릿의 계층 구조에 맞춰 핵심 기능을 요약해야 합니다."
        ),
    },
    "testcase-generation": {
        "system": "당신은 소프트웨어 QA 테스터입니다. 업로드된 요구사항을 읽고 테스트 케이스 초안을 설계합니다.",
        "instruction": (
            "요구사항을 분석하여 테스트 케이스를 CSV로 작성하세요. "
            "다음 열을 포함합니다: 대분류, 중분류, 소분류, 테스트 케이스 ID, 테스트 시나리오, 입력(사전조건 포함), 기대 출력(사후조건 포함), 테스트 결과, 상세 테스트 결과, 비고. "
            "테스트 케이스 ID는 TC-001과 같이 순차적으로 부여하고, 테스트 결과는 기본값으로 '미실행'을 사용하세요."
        ),
    },
    "defect-report": {
        "system": "당신은 QA 분석가입니다. 업로드된 테스트 로그와 증적 자료를 바탕으로 결함 요약을 작성합니다.",
        "instruction": (
            "자료를 분석해 주요 결함을 요약한 CSV를 작성하세요. 열은 결함 ID, 심각도, 발생 모듈, 현상 요약, 제안 조치입니다. "
            "결함 ID는 BUG-001 형식을 사용하고, 심각도는 치명/중대/보통/경미 중 하나로 표기합니다."
        ),
    },
    "security-report": {
        "system": "당신은 보안 컨설턴트입니다. 업로드된 보안 점검 결과를 요약한 리포트를 만듭니다.",
        "instruction": (
            "자료를 바탕으로 취약점을 정리한 CSV를 작성하세요. 열은 취약점 ID, 위험도, 영향 영역, 발견 내용, 권장 조치입니다. "
            "위험도는 높음/중간/낮음 중 하나를 사용합니다."
        ),
    },
    "performance-report": {
        "system": "당신은 성능 엔지니어입니다. 업로드된 성능 측정 자료를 분석하여 결과를 요약합니다.",
        "instruction": (
            "자료를 분석하여 주요 시나리오의 성능을 정리한 CSV를 작성하세요. 열은 시나리오, 평균 응답(ms), 처리량(TPS), 자원 사용 요약, 개선 제안입니다."
        ),
    },
}

logger = logging.getLogger(__name__)


class AIGenerationService:
    def __init__(self, settings: Settings):
        self._settings = settings
        self._client: OpenAI | None = None

    def _get_client(self) -> OpenAI:
        if self._client is None:
            api_key = self._settings.openai_api_key
            if not api_key:
                raise HTTPException(status_code=500, detail="OpenAI API 키가 설정되어 있지 않습니다.")
            self._client = OpenAI(api_key=api_key)
        return self._client

    @staticmethod
    def _descriptor_from_context(context: UploadContext) -> tuple[str, str | None]:
        metadata = context.metadata or {}
        role = str(metadata.get("role") or "").strip()
        label = str(
            metadata.get("label") or metadata.get("description") or ""
        ).strip()

        extension = AIGenerationService._extension(context.upload)

        if role == "additional":
            base_label = label or "추가 문서"
            descriptor = f"추가 문서: {base_label}"
        elif label:
            descriptor = label
        else:
            descriptor = context.upload.name

        if extension:
            descriptor = f"{descriptor} ({extension})"

        doc_id = (
            str(metadata.get("id")) if role == "required" and metadata.get("id") else None
        )
        return descriptor, doc_id

    @staticmethod
    def _extension(upload: BufferedUpload) -> str:
        extension = os.path.splitext(upload.name)[1].lstrip(".")
        if extension:
            extension = extension.upper()
        elif upload.content_type:
            subtype = upload.content_type.split("/")[-1]
            extension = subtype.upper()
        mapping = {"JPEG": "JPG"}
        return mapping.get(extension, extension)

    @staticmethod
    def _attachment_kind(upload: BufferedUpload) -> Literal["file", "image"]:
        content_type = (upload.content_type or "").split(";")[0].strip().lower()
        if content_type.startswith("image/"):
            return "image"

        extension = os.path.splitext(upload.name)[1].lower()
        if extension in {
            ".png",
            ".jpg",
            ".jpeg",
            ".gif",
            ".bmp",
            ".webp",
            ".tiff",
            ".tif",
            ".heic",
        }:
            return "image"

        return "file"

    @staticmethod
    def _closing_note(menu_id: str, contexts: List[PromptContextPreview]) -> str | None:
        if not contexts:
            return None

        def describe(preferred_ids: List[str]) -> str:
            ordered: List[str] = []
            for doc_id in preferred_ids:
                match = next(
                    (context.descriptor for context in contexts if context.doc_id == doc_id),
                    None,
                )
                if match:
                    ordered.append(match)
            if len(ordered) == len(preferred_ids):
                return ", ".join(ordered)
            return ", ".join(context.descriptor for context in contexts)

        if menu_id == "feature-list":
            description = describe(["user-manual", "configuration", "vendor-feature-list"])
            return (
                f"위 자료는 {description}입니다. 이 자료를 활용하여 기능리스트를 작성해 주세요."
            )

        if menu_id == "testcase-generation":
            description = describe(["user-manual", "configuration", "vendor-feature-list"])
            return (
                f"위 자료는 {description}입니다. 이 자료를 바탕으로 테스트케이스를 작성해 주세요."
            )

        return None

    @staticmethod
    def _build_context_previews(
        contexts: Iterable[UploadContext],
    ) -> List[PromptContextPreview]:
        previews: List[PromptContextPreview] = []
        for context in contexts:
            descriptor, doc_id = AIGenerationService._descriptor_from_context(context)
            cleaned = descriptor.strip() or context.upload.name
            previews.append(PromptContextPreview(descriptor=cleaned, doc_id=doc_id))
        return previews

    async def _upload_openai_file(self, client: OpenAI, context: UploadContext) -> str:
        upload = context.upload
        stream = io.BytesIO(upload.content)
        try:
            created = await asyncio.to_thread(
                client.files.create,
                file=(upload.name, stream),
                purpose="assistants",
            )
        except APIError as exc:
            raise HTTPException(
                status_code=502,
                detail=f"OpenAI 파일 업로드 중 오류가 발생했습니다: {exc}",
            ) from exc
        except Exception as exc:  # pragma: no cover - 안전망
            raise HTTPException(
                status_code=502,
                detail="OpenAI 파일 업로드 중 예기치 않은 오류가 발생했습니다.",
            ) from exc

        file_id = getattr(created, "id", None)
        if not file_id and hasattr(created, "get"):
            try:
                file_id = created.get("id")  # type: ignore[call-arg]
            except Exception:  # pragma: no cover - dict-like guard
                file_id = None

        if not isinstance(file_id, str) or not file_id:
            raise HTTPException(
                status_code=502,
                detail="OpenAI 파일 업로드 응답에 file_id가 없습니다.",
            )

        return file_id

    async def _cleanup_openai_files(
        self, client: OpenAI, file_ids: Iterable[str]
    ) -> None:
        for file_id in file_ids:
            try:
                await asyncio.to_thread(client.files.delete, file_id=file_id)
            except Exception as exc:  # pragma: no cover - 로그 목적
                logger.warning(
                    "Failed to delete temporary OpenAI file",
                    extra={"file_id": file_id, "error": str(exc)},
                )

    @staticmethod
    def _sanitize_csv(text: str) -> str:
        cleaned = text.strip()
        fence_match = re.search(r"```(?:csv)?\s*(.*?)```", cleaned, re.DOTALL | re.IGNORECASE)
        if fence_match:
            cleaned = fence_match.group(1).strip()
        return cleaned

    async def generate_csv(
        self,
        project_id: str,
        menu_id: str,
        uploads: List[UploadFile],
        metadata: List[Dict[str, Any]] | None = None,
    ) -> GeneratedCsv:
        prompt = _PROMPT_TEMPLATES.get(menu_id)
        if not prompt:
            raise HTTPException(status_code=404, detail="지원하지 않는 생성 메뉴입니다.")

        if not uploads:
            raise HTTPException(status_code=422, detail="업로드된 자료가 없습니다. 파일을 추가해 주세요.")

        buffered: List[BufferedUpload] = []
        for upload in uploads:
            try:
                data = await upload.read()
                name = upload.filename or "업로드된_파일"
                buffered.append(
                    BufferedUpload(
                        name=name,
                        content=data,
                        content_type=upload.content_type,
                    )
                )
            finally:
                await upload.close()

        contexts: List[UploadContext] = []
        metadata = metadata or []
        for index, upload in enumerate(buffered):
            entry = metadata[index] if index < len(metadata) else None
            contexts.append(UploadContext(upload=upload, metadata=entry))

        client = self._get_client()
        uploaded_file_ids: List[str] = []
        uploaded_attachments: List[AttachmentMetadata] = []

        try:
            context_previews = self._build_context_previews(contexts)
            closing_note = self._closing_note(menu_id, context_previews)

            descriptor_lines = [
                f"{index}. {preview.descriptor}"
                for index, preview in enumerate(context_previews, start=1)
                if preview.descriptor.strip()
            ]
            descriptor_section = "\n".join(descriptor_lines)

            for context in contexts:
                file_id = await self._upload_openai_file(client, context)
                uploaded_file_ids.append(file_id)
                uploaded_attachments.append(
                    {"file_id": file_id, "kind": self._attachment_kind(context.upload)}
                )

            user_prompt_parts = [
                prompt["instruction"],
                (
                    "다음 첨부 파일을 참고하여 요구사항을 분석하고 지침에 맞는 CSV를 작성하세요."
                ),
                "각 파일은 업로드된 순서대로 첨부되어 있습니다.",
            ]
            if descriptor_section:
                user_prompt_parts.append("첨부 파일 목록:")
                user_prompt_parts.append(descriptor_section)
            if closing_note:
                user_prompt_parts.append(closing_note)
            user_prompt_parts.append("CSV 이외의 다른 형식이나 설명 문장은 포함하지 마세요.")

            user_prompt = "\n\n".join(part for part in user_prompt_parts if part.strip())

            messages = [
                OpenAIMessageBuilder.text_message("system", prompt["system"]),
                OpenAIMessageBuilder.text_message(
                    "user",
                    user_prompt,
                    attachments=uploaded_attachments,
                ),
            ]

            logger.info(
                "AI generation prompt assembled",
                extra={
                    "project_id": project_id,
                    "menu_id": menu_id,
                    "system_prompt": prompt["system"],
                    "user_prompt": user_prompt,
                },
            )

            try:
                response = await asyncio.to_thread(
                    client.responses.create,
                    model=self._settings.openai_model,
                    input=messages,
                    temperature=0.2,
                    max_output_tokens=1500,
                )
            except APIError as exc:
                raise HTTPException(status_code=502, detail=f"OpenAI 호출 중 오류가 발생했습니다: {exc}") from exc
            except Exception as exc:  # pragma: no cover - 안전망
                raise HTTPException(status_code=502, detail="OpenAI 응답을 가져오는 중 예기치 않은 오류가 발생했습니다.") from exc

            csv_text = getattr(response, "output_text", None)
            if not csv_text:
                raise HTTPException(status_code=502, detail="OpenAI 응답에서 CSV를 찾을 수 없습니다.")

            sanitized = self._sanitize_csv(csv_text)
            if not sanitized:
                raise HTTPException(status_code=502, detail="생성된 CSV 내용이 비어 있습니다.")

            encoded = sanitized.encode("utf-8-sig")
            timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
            safe_project = re.sub(r"[^A-Za-z0-9_-]+", "_", project_id)
            filename = f"{safe_project}_{menu_id}_{timestamp}.csv"

            return GeneratedCsv(filename=filename, content=encoded, csv_text=sanitized)
        finally:
            if uploaded_file_ids:
                await self._cleanup_openai_files(client, uploaded_file_ids)
