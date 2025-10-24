from __future__ import annotations

import csv
import io
from typing import Dict, Iterable, List, Sequence

__all__ = [
    "summarize_feature_description",
    "safe_int",
    "append_attachment_note",
    "parse_csv_records",
]


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


def parse_csv_records(csv_text: str, expected_columns: Sequence[str]) -> List[Dict[str, str]]:
    stripped = csv_text.strip()
    if not stripped:
        return []

    reader = csv.reader(io.StringIO(stripped))
    rows = [row for row in reader]
    if not rows:
        return []

    header = [cell.strip() for cell in rows[0]]
    if header:
        header[0] = header[0].lstrip("\ufeff")
    column_index: Dict[str, int] = {}
    for idx, name in enumerate(header):
        if name:
            column_index[name] = idx

    missing = [column for column in expected_columns if column not in column_index]
    if missing:
        raise ValueError(f"CSV에 필요한 열이 없습니다: {', '.join(missing)}")

    records: List[Dict[str, str]] = []
    for raw in rows[1:]:
        entry: Dict[str, str] = {}
        is_empty = True
        for column in expected_columns:
            index = column_index[column]
            value = ""
            if index < len(raw):
                value = raw[index].strip()
            if value:
                is_empty = False
            entry[column] = value
        if not is_empty:
            records.append(entry)
    return records
