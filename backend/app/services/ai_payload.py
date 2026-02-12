"""Utilities for building Anthropic Messages API payloads.
"""

from __future__ import annotations

import base64
import logging
from typing import Dict, List, Literal, MutableMapping, Sequence, TypedDict, cast

Role = Literal["system", "user", "assistant"]

class MessageSource(TypedDict):
    type: Literal["base64"]
    media_type: str
    data: str

class ContentPart(TypedDict, total=False):
    type: Literal["text", "image", "document"]
    text: str
    source: MessageSource

class Message(TypedDict):
    role: Role
    content: List[ContentPart]

logger = logging.getLogger(__name__)

class AttachmentMetadata(TypedDict, total=False):
    kind: Literal["file", "image"]
    content: bytes
    media_type: str
    name: str

class AIMessageBuilder:  # Renamed for Anthropic compatibility
    @classmethod
    def text_message(
        cls,
        role: str,
        text: str,
        *,
        attachments: Iterable[AttachmentMetadata] | None = None,
    ) -> Message:
        if role == "system":
            # Anthropic handles system prompt separately, but for compatibility 
            # we might return it as a special role or handle it in the service.
            # Here we'll just treat it as user if passed to this builder, 
            # or the service should extract it.
            pass

        parts: List[ContentPart] = []
        if text:
            parts.append({"type": "text", "text": text})

        if attachments:
            for attr in attachments:
                kind = attr.get("kind")
                content = attr.get("content")
                media_type = attr.get("media_type")
                
                if not content:
                    continue
                
                b64_data = base64.b64encode(content).decode("utf-8")
                
                if kind == "image":
                    parts.append({
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type or "image/jpeg",
                            "data": b64_data,
                        }
                    })
                elif kind == "file":
                    # Using 'document' for PDFs in Anthropic
                    parts.append({
                        "type": "document",
                        "source": {
                            "type": "base64",
                            "media_type": media_type or "application/pdf",
                            "data": b64_data,
                        }
                    })

        return {
            "role": cast(Role, role),
            "content": parts,
        }

    @classmethod
    def normalize_messages(cls, messages: Sequence[MutableMapping[str, object]]) -> List[Message]:
        # Anthropic standard: filter system roles if necessary or pass them as is 
        # but the service must extract them.
        normalized: List[Message] = []
        for msg in messages:
            role = str(msg.get("role", "user"))
            content = msg.get("content")
            
            if role == "system":
                # Skip or handle separately
                continue
                
            parts: List[ContentPart] = []
            if isinstance(content, str):
                parts.append({"type": "text", "text": content})
            elif isinstance(content, list):
                for item in content:
                    if isinstance(item, dict):
                        # Convert legacy part to standard AI part if needed
                        p_type = item.get("type")
                        if p_type in {"text", "input_text", "output_text"}:
                            parts.append({"type": "text", "text": str(item.get("text", ""))})
                        # Add more conversions as needed
                    else:
                        parts.append({"type": "text", "text": str(item)})
            
            normalized.append({
                "role": cast(Role, role),
                "content": parts
            })
        return normalized
