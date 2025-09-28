"""Helpers for extracting readable text previews from uploads."""

from __future__ import annotations

import io
import os
import re
from dataclasses import dataclass
from html import unescape
from html.parser import HTMLParser
from typing import Callable, Optional


@dataclass
class ExtractedUploadPreview:
    """Structured preview for an uploaded file."""

    header: str
    body: str


class _HTMLTextParser(HTMLParser):
    _BLOCK_TAGS = {
        "address",
        "article",
        "aside",
        "blockquote",
        "br",
        "div",
        "dl",
        "fieldset",
        "figcaption",
        "figure",
        "footer",
        "form",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "header",
        "hr",
        "li",
        "main",
        "nav",
        "ol",
        "p",
        "pre",
        "section",
        "table",
        "td",
        "th",
        "tr",
        "ul",
    }

    def __init__(self) -> None:
        super().__init__()
        self._chunks: list[str] = []

    def handle_starttag(self, tag: str, attrs):  # type: ignore[override]
        if tag in self._BLOCK_TAGS:
            self._chunks.append("\n")

    def handle_endtag(self, tag: str):  # type: ignore[override]
        if tag in self._BLOCK_TAGS:
            self._chunks.append("\n")

    def handle_data(self, data: str):  # type: ignore[override]
        if data:
            self._chunks.append(data)

    def get_text(self) -> str:
        text = "".join(self._chunks)
        text = unescape(text)
        text = re.sub(r"[\r\t]", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = re.sub(r"\s{2,}", " ", text)
        return text.strip()


def _decode_text(raw: bytes, *, errors: str = "strict") -> str:
    for encoding in ("utf-8", "cp949"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors=errors)


def _decode_text_lenient(raw: bytes) -> str:
    return _decode_text(raw, errors="ignore")


def _extract_pdf(raw: bytes) -> str:
    texts: list[str] = []

    try:  # pragma: no cover - optional dependency path
        from PyPDF2 import PdfReader  # type: ignore

        try:
            reader = PdfReader(io.BytesIO(raw))
        except Exception:
            reader = None
        if reader is not None:
            for page in getattr(reader, "pages", []):
                try:
                    value = page.extract_text()  # type: ignore[attr-defined]
                except Exception:  # pragma: no cover - PyPDF2 internal errors
                    value = None
                if value:
                    texts.append(value)
    except Exception:
        pass

    if texts:
        return "\n".join(texts).strip()

    decoded = raw.decode("latin-1", errors="ignore")
    candidate_segments: list[str] = []

    # Match both (text) Tj and [(text1) (text2)] TJ patterns
    for match in re.findall(r"\(([^()]*)\)\s*T[jJ]", decoded):
        candidate_segments.append(match)

    for array in re.findall(r"\[((?:\([^\)]*\)\s*)+)\]\s*TJ", decoded):
        for match in re.findall(r"\(([^()]*)\)", array):
            candidate_segments.append(match)

    if not candidate_segments:
        return ""

    def _unescape(segment: str) -> str:
        replacements = {
            r"\\n": "\n",
            r"\\r": "\n",
            r"\\t": "\t",
            r"\\b": "",
            r"\\f": "",
            r"\\(": "(",
            r"\\)": ")",
            r"\\\\": "\\",
        }
        for pattern, replacement in replacements.items():
            segment = segment.replace(pattern, replacement)
        return segment

    cleaned = [_unescape(seg) for seg in candidate_segments]
    return "\n".join(s for s in cleaned if s).strip()


def _extract_html(raw: bytes) -> str:
    parser = _HTMLTextParser()
    try:
        parser.feed(_decode_text(raw, errors="ignore"))
        parser.close()
    except Exception:
        return ""
    return parser.get_text()

def _default_message(filename: str) -> str:
    return (
        "텍스트를 추출하지 못했습니다. 파일 내용을 직접 확인해 주세요. "
        f"(파일명: {filename})"
    )


def _extract_text_by_strategy(raw: bytes, strategy: Callable[[bytes], str]) -> str:
    try:
        text = strategy(raw)
    except Exception:
        text = ""
    return text.strip()


def _normalize_whitespace(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"\u3000", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_text_preview(
    *,
    filename: str,
    raw: bytes,
    content_type: Optional[str],
    max_chars: int,
) -> ExtractedUploadPreview:
    extension = os.path.splitext(filename)[1].lower()

    strategies: list[Callable[[bytes], str]] = []

    if extension in {".txt", ".csv"} or (content_type or "").startswith("text/"):
        strategies.extend([_decode_text, _decode_text_lenient])
    elif extension in {".html", ".htm"} or (content_type == "text/html"):
        strategies.append(_extract_html)
    elif extension == ".pdf" or content_type == "application/pdf":
        strategies.append(_extract_pdf)
    else:
        # Attempt generic text decode as a fallback before giving up
        strategies.append(_decode_text_lenient)

    text = ""
    for strategy in strategies:
        text = _extract_text_by_strategy(raw, strategy)
        if text:
            break

    if not text:
        if extension == ".pdf" or (content_type == "application/pdf"):
            text = _default_message(filename)
        elif (content_type or "").startswith("image/"):
            text = (
                "이미지에서 텍스트를 추출할 수 없습니다. 필요하다면 OCR 결과를 제공해 주세요."
            )
        else:
            text = _default_message(filename)

    normalized = _normalize_whitespace(text)
    if not normalized:
        normalized = _default_message(filename)

    if len(normalized) > max_chars:
        normalized = normalized[:max_chars].rstrip() + "\n... (이후 내용 생략)"

    header = f"### 파일: {filename}"
    return ExtractedUploadPreview(header=header, body=normalized)
