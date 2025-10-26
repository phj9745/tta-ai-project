from __future__ import annotations

import csv
import io
import re
from typing import Dict, Iterable, List, Sequence

AI_CSV_DELIMITER = "|"

__all__ = [
    "AI_CSV_DELIMITER",
    "summarize_feature_description",
    "safe_int",
    "append_attachment_note",
    "parse_csv_records",
]


def _normalize_header_token(value: str) -> str:
    return re.sub(r"[\s()]+", "", value or "")


_FLEXIBLE_COLUMNS = {
    "결함설명",
    "업체응답",
    "비고",
}


def _rebalance_csv_row(
    row: Sequence[str],
    header: Sequence[str],
    normalized_header: Sequence[str],
) -> List[str]:
    """Ensure rows with stray commas still align with the header order."""

    if len(row) <= len(header):
        return [cell.strip() for cell in row]

    total_columns = len(header)
    total_cells = len(row)
    balanced: List[str] = []
    cell_index = 0

    for column_index, normalized_name in enumerate(normalized_header):
        remaining_columns = total_columns - column_index - 1
        remaining_cells = total_cells - cell_index

        if remaining_cells <= 0:
            balanced.append("")
            continue

        minimum_required = remaining_columns + 1
        extra_cells = max(0, remaining_cells - minimum_required)

        if remaining_columns == 0:
            consume = remaining_cells
        elif normalized_name in _FLEXIBLE_COLUMNS and extra_cells > 0:
            consume = 1 + extra_cells
        else:
            consume = 1

        segment = [cell.strip() for cell in row[cell_index : cell_index + consume]]
        if consume > 1:
            combined = f" {AI_CSV_DELIMITER} ".join(segment)
        else:
            combined = segment[0] if segment else ""
        balanced.append(combined)
        cell_index += consume

    return balanced


def summarize_feature_description(description: object, max_length: int = 120) -> str:
    """Create a compact single-line summary for a feature description."""

    if description is None:
        return ""

    try:
        text = str(description)
    except Exception:
        return ""

    cleaned = " ".join(text.split())
    if not cleaned:
        return ""

    if len(cleaned) <= max_length:
        return cleaned

    truncated = cleaned[: max(1, max_length - 1)].rstrip()
    if len(truncated) < len(cleaned):
        return f"{truncated}…"
    return truncated


def safe_int(value: object) -> int | None:
    if value is None:
        return None
    try:
        text = str(value).strip()
    except Exception:
        return None
    if not text:
        return None
    try:
        return int(text)
    except ValueError:
        return None


def append_attachment_note(value: object, names: Sequence[str]) -> str:
    cleaned_names = [str(name).strip() for name in names if str(name).strip()]
    existing = str(value or "").strip()
    if not cleaned_names:
        return existing
    if existing and all(name in existing for name in cleaned_names):
        return existing
    note = f"(첨부: {', '.join(cleaned_names)})"
    if note in existing:
        return existing
    if existing:
        return f"{existing}\n{note}"
    return note


def _normalize_header_token(value: str) -> str:
    cleaned = str(value or "").strip().lower()
    if not cleaned:
        return ""
    cleaned = cleaned.lstrip("\ufeff")
    cleaned = re.sub(r"[\s\u00a0]+", "", cleaned)
    cleaned = re.sub(r"[()\[\]{}<>]+", "", cleaned)
    cleaned = cleaned.replace("-", "").replace("_", "")
    return cleaned


def parse_csv_records(csv_text: str, expected_columns: Sequence[str]) -> List[Dict[str, str]]:
    stripped = csv_text.strip()
    if not stripped:
        return []

    reader = csv.reader(io.StringIO(stripped), delimiter=AI_CSV_DELIMITER)
    rows = [row for row in reader]
    if not rows:
        return []

    header = [cell.strip() for cell in rows[0]]
    if header:
        header[0] = header[0].lstrip("\ufeff")
    normalized_header = [_normalize_header_token(name) for name in header]
    column_index: Dict[str, int] = {}
    normalized_lookup: Dict[str, str] = {}
    for column in expected_columns:
        normalized = _normalize_header_token(column)
        if normalized and normalized not in normalized_lookup:
            normalized_lookup[normalized] = column

    for idx, name in enumerate(header):
        if not name:
            continue
        column_index.setdefault(name, idx)
        normalized = _normalize_header_token(name)
        canonical = normalized_lookup.get(normalized)
        if canonical:
            column_index.setdefault(canonical, idx)

    missing = [column for column in expected_columns if column not in column_index]
    if missing:
        raise ValueError(f"CSV에 필요한 열이 없습니다: {', '.join(missing)}")

    records: List[Dict[str, str]] = []
    for raw in rows[1:]:
        adjusted = _rebalance_csv_row(raw, header, normalized_header)
        entry: Dict[str, str] = {}
        is_empty = True
        for column in expected_columns:
            index = column_index[column]
            value = ""
            if index < len(adjusted):
                value = adjusted[index].strip()
            if value:
                is_empty = False
            entry[column] = value
        if not is_empty:
            records.append(entry)
    return records
