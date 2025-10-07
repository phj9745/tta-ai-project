"""Utilities for building OpenAI Responses API payloads.

이 모듈은 다양한 입력 형식을 Responses API 사양에 맞게
표준화하기 위한 도우미를 제공합니다.
"""

from __future__ import annotations

import logging
from typing import Iterable, List, Literal, MutableMapping, Sequence, TypedDict, cast
from typing import NotRequired, Required
from urllib.parse import urlparse

Role = Literal["system", "user", "assistant", "tool"]

_TextContentType = Literal["input_text", "output_text", "summary_text"]
_FileContentType = Literal["input_file"]
_ImageContentType = Literal["input_image"]

_AttachmentKind = Literal["file", "image"]


class InputFileContent(TypedDict):
    """Response API file reference content."""

    type: _FileContentType
    file_id: str


class ImageFileReference(TypedDict):
    """Response API image reference backed by an uploaded file."""

    file_id: str


class InputImageFileContent(TypedDict):
    """Response API image content that references an uploaded file."""

    type: _ImageContentType
    image: ImageFileReference


class ImageURLReference(TypedDict):
    """Response API image_url payload structure."""

    url: str


class InputImageURLContent(TypedDict):
    """Response API image content that references an external URL."""

    type: _ImageContentType
    image_url: ImageURLReference


class TextContent(TypedDict):
    """Response API text 기반 콘텐츠."""

    type: _TextContentType
    text: str


ContentPart = (
    TextContent | InputFileContent | InputImageURLContent | InputImageFileContent
)


logger = logging.getLogger(__name__)


class AttachmentMetadata(TypedDict, total=False):
    """Metadata describing how an uploaded asset should be attached."""

    kind: Required[_AttachmentKind]
    file_id: NotRequired[str]
    image_url: NotRequired[str]


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
        attachments: Iterable[AttachmentMetadata] | None = None,
    ) -> Message:
        """주어진 역할과 텍스트로 단일 파트 메시지를 생성합니다."""

        normalized_type = content_type or cls._ROLE_TEXT_TYPE.get(role, "input_text")
        parts: List[ContentPart] = [
            {
                "type": normalized_type,
                "text": text,
            }
        ]

        normalized_attachments: List[AttachmentMetadata] = []
        if attachments:
            for attachment in attachments:
                if not isinstance(attachment, MutableMapping):
                    cls._log_invalid_attachment(
                        role,
                        text,
                        "attachment 항목은 매핑이어야 합니다.",
                        attachment,
                    )
                    raise ValueError("attachment 항목은 매핑이어야 합니다.")
                kind = attachment.get("kind")
                if kind not in {"file", "image"}:
                    cls._log_invalid_attachment(
                        role,
                        text,
                        f"지원하지 않는 attachment kind입니다: {kind!r}",
                        attachment,
                    )
                    raise ValueError(f"지원하지 않는 attachment kind입니다: {kind!r}")

                normalized_attachment: MutableMapping[str, object] = {"kind": kind}

                raw_file_id = attachment.get("file_id")
                if raw_file_id is not None:
                    if not isinstance(raw_file_id, str) or not raw_file_id.strip():
                        cls._log_invalid_attachment(
                            role,
                            text,
                            "attachment file_id는 공백이 아닌 문자열이어야 합니다.",
                            attachment,
                        )
                        raise ValueError(
                            "attachment file_id는 공백이 아닌 문자열이어야 합니다."
                        )
                    normalized_attachment["file_id"] = raw_file_id.strip()

                if kind == "file" and "file_id" not in normalized_attachment:
                    cls._log_invalid_attachment(
                        role,
                        text,
                        "file 첨부에는 file_id가 필요합니다.",
                        attachment,
                    )
                    raise ValueError(
                        "file 첨부에는 file_id가 필요합니다."
                    )

                if kind == "image":
                    raw_image_url = attachment.get("image_url")
                    if raw_image_url is None and "url" in attachment:
                        raw_image_url = attachment.get("url")
                    if raw_image_url is not None:
                        if isinstance(raw_image_url, MutableMapping):
                            candidate = raw_image_url.get("url")
                            if not isinstance(candidate, str) or not candidate.strip():
                                cls._log_invalid_attachment(
                                    role,
                                    text,
                                    "image 첨부의 image_url.url은 공백이 아닌 문자열이어야 합니다.",
                                    attachment,
                                )
                                raise ValueError(
                                    "image 첨부의 image_url.url은 공백이 아닌 문자열이어야 합니다."
                                )
                            normalized_attachment["image_url"] = candidate.strip()
                        elif isinstance(raw_image_url, str):
                            if not raw_image_url.strip():
                                cls._log_invalid_attachment(
                                    role,
                                    text,
                                    "image 첨부의 image_url은 공백이 아닌 문자열이어야 합니다.",
                                    attachment,
                                )
                                raise ValueError(
                                    "image 첨부의 image_url은 공백이 아닌 문자열이어야 합니다."
                                )
                            normalized_attachment["image_url"] = raw_image_url.strip()
                        else:
                            cls._log_invalid_attachment(
                                role,
                                text,
                                "image 첨부의 image_url은 문자열 또는 매핑이어야 합니다.",
                                attachment,
                            )
                            raise ValueError(
                                "image 첨부의 image_url은 문자열 또는 매핑이어야 합니다."
                            )

                if (
                    "image_url" not in normalized_attachment
                    and "file_id" not in normalized_attachment
                ):
                    cls._log_invalid_attachment(
                        role,
                        text,
                        "image 첨부에는 image_url 또는 file_id 중 하나가 필요합니다.",
                        attachment,
                    )
                    raise ValueError(
                        "image 첨부에는 image_url 또는 file_id 중 하나가 필요합니다."
                    )

                normalized_attachments.append(
                    cast(AttachmentMetadata, normalized_attachment)
                )

        if file_ids:
            for file_id in file_ids:
                if not isinstance(file_id, str) or not file_id.strip():
                    raise ValueError("file_id는 공백이 아닌 문자열이어야 합니다.")
                normalized_attachments.append(
                    {"file_id": file_id, "kind": "file"}  # type: ignore[typeddict-item]
                )

        for attachment in normalized_attachments:
            kind = attachment["kind"]
            if kind == "file":
                file_id = attachment.get("file_id")
                if not isinstance(file_id, str) or not file_id.strip():
                    cls._log_invalid_attachment(
                        role,
                        text,
                        "file 첨부에는 유효한 file_id가 필요합니다.",
                        attachment,
                    )
                    raise ValueError("file 첨부에는 유효한 file_id가 필요합니다.")
                parts.append({"type": "input_file", "file_id": file_id})
            elif kind == "image":
                image_url = attachment.get("image_url")
                if isinstance(image_url, str) and image_url.strip():
                    parts.append(
                        {
                            "type": "input_image",
                            "image_url": image_url.strip(),
                        }
                    )
                    continue

                cls._log_invalid_attachment(
                    role,
                    text,
                    "image 첨부에는 image_url이 필요합니다.",
                    attachment,
                )
                raise ValueError("image 첨부에는 image_url이 필요합니다.")
            else:  # pragma: no cover - typing guard
                cls._log_invalid_attachment(
                    role,
                    text,
                    f"지원하지 않는 attachment kind입니다: {kind!r}",
                    attachment,
                )
                raise ValueError(f"지원하지 않는 attachment kind입니다: {kind!r}")

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
                    elif part_type == "input_image":
                        normalized_contents.append(cls._normalize_image_part(item))
                    else:
                        raise ValueError(f"지원하지 않는 content type입니다: {part_type!r}")

            if not normalized_contents:
                raise ValueError("정규화된 content가 비어 있습니다.")

            normalized.append({"role": role, "content": normalized_contents})

        return normalized

    @classmethod
    def _normalize_image_part(
        cls, item: MutableMapping[str, object]
    ) -> InputImageURLContent | InputImageFileContent:
        image: object | None = item.get("image")
        image_url: object | None = item.get("image_url")
        image_id: object | None = item.get("image_id")

        if image is not None:
            cls._log_invalid_image_part(
                "input_image 항목의 image 필드는 더 이상 지원되지 않습니다.",
                item,
            )
            raise ValueError("input_image 항목의 image 필드는 더 이상 지원되지 않습니다.")

        if isinstance(image_id, str) and image_id.strip():
            cls._log_invalid_image_part(
                "input_image 항목의 image_id는 더 이상 지원되지 않습니다.",
                item,
            )
            raise ValueError("input_image 항목의 image_id는 더 이상 지원되지 않습니다.")

        if image_url is not None:
            external_url = cls._normalize_external_image_url(
                image_url, context=item
            )
            return {"type": "input_image", "image_url": {"url": external_url}}

        cls._log_invalid_image_part(
            "input_image 항목에는 image_url이 필요합니다.",
            item,
        )
        raise ValueError("input_image 항목에는 image_url이 필요합니다.")

    @classmethod
    def _normalize_external_image_url(
        cls, value: object, *, context: MutableMapping[str, object] | None = None
    ) -> str:
        raw: object
        if isinstance(value, MutableMapping):
            raw = value.get("url")
        else:
            raw = value

        if not isinstance(raw, str):
            cls._log_invalid_image_part(
                "input_image 항목의 image_url 필드는 문자열 또는 매핑이어야 합니다.",
                context,
            )
            raise ValueError(
                "input_image 항목의 image_url 필드는 문자열 또는 매핑이어야 합니다."
            )

        candidate = raw.strip()
        if not candidate:
            cls._log_invalid_image_part(
                "input_image 항목의 image_url는 공백이 아닌 문자열이어야 합니다.",
                context,
            )
            raise ValueError(
                "input_image 항목의 image_url는 공백이 아닌 문자열이어야 합니다."
            )

        parsed = urlparse(candidate)
        if parsed.scheme in {"http", "https", "data"}:
            if cls._is_valid_external_url(candidate):
                return candidate
            cls._log_invalid_image_part(
                "input_image 항목의 image_url는 유효한 외부 URL이어야 합니다.",
                context,
            )
            raise ValueError(
                "input_image 항목의 image_url는 유효한 외부 URL이어야 합니다."
            )

        cls._log_invalid_image_part(
            "input_image 항목의 image_url는 지원되는 스킴을 사용해야 합니다.",
            context,
        )
        raise ValueError(
            "input_image 항목의 image_url는 지원되는 스킴을 사용해야 합니다."
        )

    @staticmethod
    def _is_valid_external_url(value: str) -> bool:
        parsed = urlparse(value)
        if parsed.scheme in {"http", "https"} and parsed.netloc:
            return True
        if parsed.scheme == "data" and value.count(":") >= 1:
            return True
        return False

    @staticmethod
    def attachments_to_chat_completions(
        attachments: Iterable[AttachmentMetadata],
    ) -> List[MutableMapping[str, object]]:
        """Responses 첨부 정보를 Chat Completions 포맷으로 변환합니다."""

        completion_parts: List[MutableMapping[str, object]] = []
        for attachment in attachments:
            kind = attachment.get("kind")
            if kind != "image":
                continue

            image_url = attachment.get("image_url")
            if isinstance(image_url, MutableMapping):
                raw_url = image_url.get("url")
                if isinstance(raw_url, str) and raw_url.strip():
                    completion_parts.append(
                        {
                            "type": "input_image",
                            "image_url": {"url": raw_url.strip()},
                        }
                    )
                    continue

            if isinstance(image_url, str) and image_url.strip():
                completion_parts.append(
                    {
                        "type": "input_image",
                        "image_url": {"url": image_url},
                    }
                )
                continue
        return completion_parts

    @staticmethod
    def _preview_text(text: str, *, limit: int = 120) -> str:
        sanitized = text.replace("\n", "\\n")
        if len(sanitized) <= limit:
            return sanitized
        return sanitized[: limit - 1] + "…"

    @classmethod
    def _log_invalid_attachment(
        cls,
        role: Role,
        text: str,
        reason: str,
        attachment: object,
    ) -> None:
        try:
            attachment_repr = repr(attachment)
        except Exception:  # pragma: no cover - best effort logging
            attachment_repr = "<unrepresentable attachment>"
        logger.error(
            "잘못된 첨부가 감지되었습니다. role=%s, text_preview=%s, reason=%s, attachment=%s",
            role,
            cls._preview_text(text),
            reason,
            attachment_repr,
        )

    @staticmethod
    def _log_invalid_image_part(
        reason: str,
        part: MutableMapping[str, object] | None,
    ) -> None:
        if part is None:
            logger.error("잘못된 input_image 항목이 감지되었습니다. reason=%s", reason)
            return
        try:
            part_repr = repr(part)
        except Exception:  # pragma: no cover - best effort logging
            part_repr = "<unrepresentable input_image part>"
        logger.error(
            "잘못된 input_image 항목이 감지되었습니다. reason=%s, part=%s",
            reason,
            part_repr,
        )
