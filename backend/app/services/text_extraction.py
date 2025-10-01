"""Helpers for extracting readable text previews from uploads."""

from __future__ import annotations

import io
import os
import re
import zipfile
from dataclasses import dataclass
from html import unescape
from html.parser import HTMLParser
from typing import Callable, Optional
from xml.etree import ElementTree as ET


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


def _extract_xlsx(raw: bytes) -> str:
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            shared_strings: list[str] = []
            main_ns = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
            rel_ns = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
            pkg_rel_ns = "http://schemas.openxmlformats.org/package/2006/relationships"

            if "xl/sharedStrings.xml" in archive.namelist():
                try:
                    shared_root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
                except Exception:
                    shared_root = None
                if shared_root is not None:
                    for si in shared_root.findall(f".//{{{main_ns}}}si"):
                        text_parts = [
                            (node.text or "")
                            for node in si.findall(f".//{{{main_ns}}}t")
                        ]
                        if text_parts:
                            shared_strings.append("".join(text_parts))

            sheet_targets: dict[str, str] = {}
            if "xl/_rels/workbook.xml.rels" in archive.namelist():
                try:
                    rel_root = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
                except Exception:
                    rel_root = None
                if rel_root is not None:
                    for rel in rel_root.findall(
                        f".//{{{pkg_rel_ns}}}Relationship"
                    ):
                        rel_id = rel.get("Id")
                        target = rel.get("Target")
                        if rel_id and target:
                            sheet_targets[rel_id] = target

            sheets: list[tuple[str, str]] = []
            rel_attr = f"{{{rel_ns}}}id"
            if "xl/workbook.xml" in archive.namelist():
                try:
                    workbook_root = ET.fromstring(archive.read("xl/workbook.xml"))
                except Exception:
                    workbook_root = None
                if workbook_root is not None:
                    for sheet in workbook_root.findall(f".//{{{main_ns}}}sheet"):
                        name = sheet.get("name", "Sheet")
                        rel_id = sheet.get(rel_attr)
                        sheet_path: Optional[str] = None
                        if rel_id and rel_id in sheet_targets:
                            target = sheet_targets[rel_id]
                            if target.startswith("/"):
                                sheet_path = target.lstrip("/")
                            else:
                                sheet_path = f"xl/{target}" if not target.startswith("xl/") else target
                        else:
                            sheet_id = sheet.get("sheetId")
                            candidate = f"xl/worksheets/sheet{sheet_id}.xml"
                            if sheet_id and candidate in archive.namelist():
                                sheet_path = candidate

                        if sheet_path and sheet_path in archive.namelist():
                            sheets.append((name, sheet_path))

            if not sheets:
                sheets = [
                    (member.rsplit("/", 1)[-1], member)
                    for member in archive.namelist()
                    if member.startswith("xl/worksheets/") and member.endswith(".xml")
                ]

            lines: list[str] = []
            row_tag = f"{{{main_ns}}}row"
            cell_tag = f"{{{main_ns}}}c"
            value_tag = f"{{{main_ns}}}v"
            inline_tag = f"{{{main_ns}}}is"
            text_tag = f"{{{main_ns}}}t"

            for sheet_name, path in sheets:
                try:
                    sheet_root = ET.fromstring(archive.read(path))
                except Exception:
                    continue

                lines.append(f"[시트] {sheet_name}")
                for row in sheet_root.findall(f".//{row_tag}"):
                    cells: list[str] = []
                    for cell in row.findall(cell_tag):
                        cell_type = cell.get("t")
                        text = ""
                        if cell_type == "s":
                            value_node = cell.find(value_tag)
                            if value_node is not None and value_node.text is not None:
                                try:
                                    index = int(value_node.text)
                                except ValueError:
                                    index = -1
                                if 0 <= index < len(shared_strings):
                                    text = shared_strings[index]
                        elif cell_type == "inlineStr":
                            inline = cell.find(f"{inline_tag}/{text_tag}")
                            if inline is not None and inline.text:
                                text = inline.text
                        else:
                            value_node = cell.find(value_tag)
                            if value_node is not None and value_node.text:
                                text = value_node.text
                        cells.append(text.strip())
                    if cells:
                        lines.append(" | ".join(cells).strip())
                lines.append("")

            return "\n".join(line for line in lines if line).strip()
    except Exception:
        return ""

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
    elif extension in {".xlsx"} or (
        content_type
        == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    ):
        strategies.append(_extract_xlsx)
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
        elif extension == ".xlsx" or (
            content_type
            == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ):
            text = _default_message(filename)
        else:
            text = _default_message(filename)

    normalized = _normalize_whitespace(text)
    if not normalized:
        normalized = _default_message(filename)

    if len(normalized) > max_chars:
        normalized = normalized[:max_chars].rstrip() + "\n... (이후 내용 생략)"

    header = f"### 파일: {filename}"
    return ExtractedUploadPreview(header=header, body=normalized)
