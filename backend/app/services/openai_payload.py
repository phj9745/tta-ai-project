"""Utilities for building OpenAI Responses API payloads.

이 모듈은 다양한 입력 형식을 Responses API 사양에 맞게
표준화하기 위한 도우미를 제공합니다.
"""

from __future__ import annotations

from typing import Iterable, List, Literal, MutableMapping, Sequence, TypedDict

Role = Literal["system", "user", "assistant", "tool"]

_TextContentType = Literal["input_text", "output_text", "summary_text"]
_FileContentType = Literal["input_file"]


class InputFileContent(TypedDict):
    """Response API file reference content."""

    type: _FileContentType
    file_id: str


class TextContent(TypedDict):
    """Response API text 기반 콘텐츠."""

    type: _TextContentType
    text: str


ContentPart = TextContent | InputFileContent


class Message(TypedDict):
    """Responses API 메시지 구조."""

    role: Role
    content: List[ContentPart]


class OpenAIMessageBuilder:
    """Responses API용 메시지를 생성하고 정규화하는 헬퍼."""

    _ROLE_TEXT_TYPE: MutableMapping[Role, _TextContentType] = {
        "system": "input_text",
        "user": "input_text",
        "assistant": "output_text",
        "tool": "output_text",
    }

    @classmethod
    def text_message(
        cls,
        role: Role,
        text: str,
        *,
        content_type: _TextContentType | None = None,
        file_ids: Iterable[str] | None = None,
    ) -> Message:
        """주어진 역할과 텍스트로 단일 파트 메시지를 생성합니다."""

        normalized_type = content_type or cls._ROLE_TEXT_TYPE.get(role, "input_text")
        parts: List[ContentPart] = [
            {
                "type": normalized_type,
                "text": text,
            }
        ]

        if file_ids:
            for file_id in file_ids:
                if not isinstance(file_id, str) or not file_id.strip():
                    raise ValueError("file_id는 공백이 아닌 문자열이어야 합니다.")
                parts.append({"type": "input_file", "file_id": file_id})

        return {
            "role": role,
            "content": parts,
        }

    @classmethod
    def normalize_messages(cls, messages: Sequence[MutableMapping[str, object]]) -> List[Message]:
        """Responses API 입력 스펙에 맞도록 메시지 배열을 정규화합니다.

        구 버전 포맷(예: type="text" 또는 문자열 콘텐츠)을 허용하고,
        현재 스펙에 맞춰 type 값을 변환합니다.
        """

        normalized: List[Message] = []
        for raw in messages:
            role = raw.get("role")
            if role not in cls._ROLE_TEXT_TYPE:
                raise ValueError(f"알 수 없는 메시지 역할입니다: {role!r}")

            contents = raw.get("content")
            if contents is None:
                raise ValueError("메시지에 content가 없습니다.")

            normalized_contents: List[ContentPart] = []
            if isinstance(contents, str):
                normalized_contents.append(
                    {
                        "type": cls._ROLE_TEXT_TYPE[role],
                        "text": contents,
                    }
                )
            else:
                if not isinstance(contents, Iterable):
                    raise ValueError("content는 문자열 또는 Iterable 이어야 합니다.")
                for item in contents:  # type: ignore[assignment]
                    if not isinstance(item, MutableMapping):
                        raise ValueError("content 항목은 매핑이어야 합니다.")
                    part_type = item.get("type")
                    if part_type in {None, "text"}:
                        normalized_contents.append(
                            {
                                "type": cls._ROLE_TEXT_TYPE[role],
                                "text": str(item.get("text", "")),
                            }
                        )
                    elif part_type in {"input_text", "output_text", "summary_text"}:
                        normalized_contents.append(
                            {
                                "type": part_type,
                                "text": str(item.get("text", "")),
                            }
                        )
                    elif part_type == "input_file":
                        file_id = item.get("file_id")
                        if not isinstance(file_id, str) or not file_id.strip():
                            raise ValueError("input_file 항목에는 유효한 file_id가 필요합니다.")
                        normalized_contents.append(
                            {
                                "type": "input_file",
                                "file_id": file_id,
                            }
                        )
                    else:
                        raise ValueError(f"지원하지 않는 content type입니다: {part_type!r}")

            if not normalized_contents:
                raise ValueError("정규화된 content가 비어 있습니다.")

            normalized.append({"role": role, "content": normalized_contents})

        return normalized
