from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Iterable, List

from fastapi import HTTPException, UploadFile
from openai import APIError, OpenAI

from ..config import Settings
from .openai_payload import OpenAIMessageBuilder
from .text_extraction import ExtractedUploadPreview, extract_text_preview

_MAX_PREVIEW_CHARS = 6000


@dataclass
class BufferedUpload:
    name: str
    content: bytes
    content_type: str | None


@dataclass
class GeneratedCsv:
    filename: str
    content: bytes


_PROMPT_TEMPLATES: Dict[str, Dict[str, str]] = {
    "feature-tc": {
        "system": "당신은 소프트웨어 QA 리드입니다. 업로드된 요구사항을 읽고 기능 정의와 테스트 케이스를 구조화된 CSV로 제안하세요.",
        "instruction": (
            "요구사항 자료를 참고하여 기능과 테스트 케이스 개요를 작성하세요. "
            "다음 열을 포함한 CSV를 생성합니다: 기능명, 테스트 케이스 ID, 목적, 우선순위, 비고. "
            "ID는 FC-001과 같은 형식을 따르도록 합니다."
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
    def _preview_from_uploads(
        uploads: Iterable[BufferedUpload],
    ) -> str:
        sections: List[str] = []
        for upload in uploads:
            preview: ExtractedUploadPreview = extract_text_preview(
                filename=upload.name,
                raw=upload.content,
                content_type=upload.content_type,
                max_chars=_MAX_PREVIEW_CHARS,
            )
            sections.append(
                "\n".join(
                    part for part in (preview.header, preview.body) if part.strip()
                )
            )

        return "\n\n".join(sections)

    @staticmethod
    def _sanitize_csv(text: str) -> str:
        cleaned = text.strip()
        fence_match = re.search(r"```(?:csv)?\s*(.*?)```", cleaned, re.DOTALL | re.IGNORECASE)
        if fence_match:
            cleaned = fence_match.group(1).strip()
        return cleaned

    async def generate_csv(self, project_id: str, menu_id: str, uploads: List[UploadFile]) -> GeneratedCsv:
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

        preview = self._preview_from_uploads(buffered)

        user_prompt = (
            f"{prompt['instruction']}\n\n"
            "다음은 업로드된 자료의 요약입니다. 이를 참고하여 CSV를 생성하세요.\n"
            f"{preview}\n\n"
            "CSV 이외의 다른 형식이나 설명 문장은 포함하지 마세요."
        )

        client = self._get_client()
        messages = [
            OpenAIMessageBuilder.text_message("system", prompt["system"]),
            OpenAIMessageBuilder.text_message("user", user_prompt),
        ]

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

        return GeneratedCsv(filename=filename, content=encoded)
