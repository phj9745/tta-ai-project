"""Utilities for extracting project metadata from 시험 합의서 문서."""
from __future__ import annotations

import io
import re
from typing import Dict, Iterable, Optional, Sequence, Tuple

from docx import Document
from fastapi import HTTPException
from pypdf import PdfReader

EXAM_NUMBER_PATTERN = re.compile(r"GS-[A-Z]-\d{2}-\d{4}")

__all__ = [
    "normalize_label",
    "extract_project_metadata",
    "build_project_folder_name",
]


def normalize_label(value: str) -> str:
    return re.sub(r"\s+", "", value or "")


REQUIRED_LABEL_PREFIXES = (
    normalize_label("시험신청번호"),
    normalize_label("제조자"),
    normalize_label("제품명및버전"),
)

PRODUCT_LABEL_PATTERN = re.compile(r"^\s*제품명\s*및\s*버전\s*[:：]?\s*", re.IGNORECASE)
HANGUL_PATTERN = re.compile(r"[\uAC00-\uD7A3]")


def extract_project_metadata(file_bytes: bytes, *, file_extension: Optional[str] = None) -> Dict[str, str]:
    """Extract metadata required for project creation from DOCX or PDF files."""

    normalized_extension = (file_extension or "").lower().lstrip(".")

    if normalized_extension == "pdf":
        return _extract_project_metadata_from_pdf(file_bytes)

    try:
        return _extract_project_metadata_from_docx(file_bytes)
    except HTTPException as exc:
        # If the caller did not provide a reliable extension, attempt PDF parsing
        # as a graceful fallback before surfacing the DOCX error.
        if not file_extension:
            try:
                return _extract_project_metadata_from_pdf(file_bytes)
            except HTTPException:
                pass
        raise exc


def build_project_folder_name(metadata: Dict[str, str]) -> str:
    exam_number = metadata.get("exam_number", "").strip()
    company_name = metadata.get("company_name", "").strip()
    product_name = metadata.get("product_name", "").strip()
    return f"[{exam_number}] {company_name} - {product_name}"


def _extract_project_metadata_from_docx(file_bytes: bytes) -> Dict[str, str]:
    try:
        document = Document(io.BytesIO(file_bytes))
    except Exception as exc:  # pragma: no cover - library level validation
        raise HTTPException(status_code=422, detail="시험 합의서 파일을 읽지 못했습니다.") from exc

    exam_number: Optional[str] = None
    company_name: Optional[str] = None
    product_name: Optional[str] = None
    collected_lines: list[str] = []

    def _extract_from_cells(cells: Iterable[str]) -> None:
        nonlocal exam_number, company_name, product_name
        cell_iter = iter(cells)
        for label, value in zip(cell_iter, cell_iter):
            collected_lines.append(label)
            collected_lines.append(value)
            normalized_label = normalize_label(label)
            stripped_value = value.strip()
            if not stripped_value:
                continue
            if normalized_label == "시험신청번호":
                match = EXAM_NUMBER_PATTERN.search(stripped_value)
                if match:
                    exam_number = match.group(0)
            elif normalized_label == "제조자":
                company_name = stripped_value
            elif normalized_label.startswith("제품명및버전"):
                candidate = _extract_product_name(stripped_value)
                if candidate:
                    product_name = candidate

    for table in document.tables:
        cells: list[str] = []
        for row in table.rows:
            if len(row.cells) >= 2:
                left_label = row.cells[0].text.strip()
                left_value = row.cells[1].text.strip()
                if left_label and left_value:
                    cells.append(left_label)
                    cells.append(left_value)
            if len(row.cells) >= 4:
                right_label = row.cells[2].text.strip()
                right_value = row.cells[3].text.strip()
                if right_label and right_value:
                    cells.append(right_label)
                    cells.append(right_value)

        if cells:
            _extract_from_cells(cells)

    paragraph_lines = [
        paragraph.text.strip()
        for paragraph in document.paragraphs
        if paragraph.text and paragraph.text.strip()
    ]
    collected_lines.extend(paragraph_lines)

    metadata = _finalize_metadata_from_lines(collected_lines, exam_number, company_name, product_name)
    return metadata


def _extract_project_metadata_from_pdf(file_bytes: bytes) -> Dict[str, str]:
    try:
        reader = PdfReader(io.BytesIO(file_bytes))
    except Exception as exc:  # pragma: no cover - library level validation
        raise HTTPException(status_code=422, detail="시험 합의서 파일을 읽지 못했습니다.") from exc

    lines: list[str] = []
    for page in reader.pages:
        try:
            text = page.extract_text() or ""
        except Exception as exc:  # pragma: no cover - library level validation
            raise HTTPException(status_code=422, detail="시험 합의서 파일을 읽지 못했습니다.") from exc
        if text:
            lines.extend(text.splitlines())

    metadata = _finalize_metadata_from_lines(lines, None, None, None)
    return metadata


def _finalize_metadata_from_lines(
    lines: Iterable[str],
    exam_number: Optional[str],
    company_name: Optional[str],
    product_name: Optional[str],
) -> Dict[str, str]:
    meaningful_lines = [line.strip() for line in lines if line and line.strip()]
    combined_text = "\n".join(meaningful_lines)

    if not exam_number:
        match = EXAM_NUMBER_PATTERN.search(combined_text)
        if match:
            exam_number = match.group(0)

    if not company_name:
        company_name = _extract_labeled_value(meaningful_lines, ("제조자",))

    if not product_name:
        product_name = _extract_labeled_value(meaningful_lines, ("제품명및버전",))
        if product_name:
            product_name = _extract_product_name(product_name)

    if not exam_number:
        raise HTTPException(status_code=422, detail="시험신청 번호를 찾을 수 없습니다.")

    if not company_name:
        raise HTTPException(status_code=422, detail="제조자(업체명)를 찾을 수 없습니다.")

    if not product_name:
        raise HTTPException(status_code=422, detail="제품명 및 버전을 찾을 수 없습니다.")

    return {
        "exam_number": exam_number.strip(),
        "company_name": company_name.strip(),
        "product_name": product_name.strip(),
    }


def _extract_labeled_value(lines: Sequence[str], target_labels: Sequence[str]) -> Optional[str]:
    normalized_targets = tuple(normalize_label(label) for label in target_labels)

    def _is_target(label: str) -> bool:
        return any(label.startswith(target) for target in normalized_targets)

    for index, line in enumerate(lines):
        label, inline_value = _split_label_and_value(line)
        if not _is_target(label):
            continue

        values: list[str] = []
        inline_candidate = inline_value.strip()
        next_index = index + 1

        if inline_candidate:
            values.append(inline_candidate)
        else:
            candidate_index, candidate_value = _next_value(lines, index + 1, normalized_targets)
            if not candidate_value:
                continue
            values.append(candidate_value)
            next_index = candidate_index + 1

        continuation_index = next_index
        while continuation_index < len(lines):
            next_line = lines[continuation_index].strip()
            if not next_line:
                continuation_index += 1
                continue

            next_label, _ = _split_label_and_value(next_line)
            if _is_known_label(next_label):
                break

            values.append(next_line)
            continuation_index += 1

        candidate = " ".join(values)
        candidate = _strip_leading_label(candidate, normalized_targets)
        if candidate:
            return candidate.strip()

    return None


def _split_label_and_value(line: str) -> tuple[str, str]:
    for separator in (":", "："):
        if separator in line:
            left, right = line.split(separator, 1)
            return normalize_label(left), right
    return normalize_label(line), ""


def _is_known_label(label: str) -> bool:
    return any(label.startswith(candidate) for candidate in REQUIRED_LABEL_PREFIXES)


def _next_value(
    lines: Sequence[str],
    start: int,
    normalized_targets: Sequence[str],
) -> Tuple[int, str]:
    for index in range(start, len(lines)):
        candidate = lines[index].strip()
        if not candidate:
            continue
        candidate_label, _ = _split_label_and_value(candidate)
        if any(candidate_label.startswith(target) for target in normalized_targets):
            continue
        if _is_known_label(candidate_label):
            return index, ""
        return index, candidate
    return len(lines), ""


def _strip_leading_label(value: str, normalized_targets: Sequence[str]) -> str:
    stripped = value.strip()
    if not stripped:
        return stripped

    for separator in (":", "："):
        if separator in stripped:
            potential_label, remainder = stripped.split(separator, 1)
            normalized = normalize_label(potential_label)
            if any(normalized.startswith(target) for target in normalized_targets):
                return remainder.strip()
    return stripped


def _extract_product_name(raw_value: str) -> Optional[str]:
    cleaned = PRODUCT_LABEL_PATTERN.sub("", raw_value or "")
    lines = [line.strip() for line in re.split(r"[\r\n]+", cleaned) if line.strip()]
    if not lines:
        return None

    hangul_segments: list[str] = []
    for line in lines:
        if HANGUL_PATTERN.search(line):
            match = re.search(r"[\uAC00-\uD7A3].*$", line)
            if match:
                hangul_segments.append(match.group(0).strip())
            else:
                hangul_segments.append(line)

    if hangul_segments:
        return hangul_segments[-1]

    combined = " ".join(lines).strip()
    return combined or None
