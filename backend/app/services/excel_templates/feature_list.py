from __future__ import annotations

import csv
import io
import re
import zipfile
from typing import Dict, List, Mapping, Sequence, Tuple
from xml.etree import ElementTree as ET

from .models import (
    FEATURE_LIST_COLUMNS,
    FEATURE_LIST_EXPECTED_HEADERS,
    FEATURE_LIST_START_ROW,
    SPREADSHEET_NS,
    XLSX_SHEET_PATH,
)
from .utils import summarize_feature_description
from .workbook import (
    WorksheetPopulator,
    cell_text_from_sheet,
    column_to_index,
    find_sheet_cell,
    find_sheet_row,
    index_to_column,
    parse_dimension,
    parse_shared_strings,
    replace_sheet_bytes,
    set_cell_text,
    split_cell,
)

__all__ = [
    "FEATURE_LIST_COLUMNS",
    "FEATURE_LIST_EXPECTED_HEADERS",
    "FEATURE_LIST_START_ROW",
    "summarize_feature_description",
    "match_feature_list_header",
    "normalize_feature_list_records",
    "extract_feature_list_overview",
    "populate_feature_list",
]


_FEATURE_LIST_HEADER_ALIASES: Mapping[str, Tuple[str, ...]] = {
    "대분류": ("대분류", "대 분류", "상위 기능", "상위기능"),
    "중분류": ("중분류", "중 분류", "중간 기능", "중간기능"),
    "소분류": ("소분류", "소 분류", "세부 기능", "세부기능"),
    "기능 설명": (
        "기능 설명",
        "상세 설명",
        "상세 내용",
        "기능 상세",
        "상세내용",
        "상세설명",
        "기능상세",
        "내용",
    ),
    "기능 개요": ("기능 개요", "개요", "요약", "기능 요약", "요약 설명", "개요 설명"),
}


def _normalize_feature_header_token(value: str) -> str:
    cleaned = value.strip().lower()
    if not cleaned:
        return ""
    cleaned = re.sub(r"[\s\u00a0]+", "", cleaned)
    cleaned = re.sub(r"[()\[\]{}<>]+", "", cleaned)
    cleaned = cleaned.replace("-", "").replace("_", "")
    return cleaned


_FEATURE_LIST_NORMALIZED_HEADERS: Dict[str, str] = {}
for canonical, variants in _FEATURE_LIST_HEADER_ALIASES.items():
    for variant in variants:
        normalized = _normalize_feature_header_token(variant)
        if normalized and normalized not in _FEATURE_LIST_NORMALIZED_HEADERS:
            _FEATURE_LIST_NORMALIZED_HEADERS[normalized] = canonical


def match_feature_list_header(value: str) -> str | None:
    normalized = _normalize_feature_header_token(value)
    if not normalized:
        return None
    return _FEATURE_LIST_NORMALIZED_HEADERS.get(normalized)


def _normalize_feature_list_records(csv_text: str) -> List[Dict[str, str]]:
    stripped = csv_text.strip()
    if not stripped:
        return []

    reader = csv.reader(io.StringIO(stripped))
    rows = [row for row in reader if any(cell.strip() for cell in row)]
    if not rows:
        return []

    header = [cell.strip() for cell in rows[0]]
    if header:
        header[0] = header[0].lstrip("\ufeff")

    column_map: Dict[str, int] = {}
    overview_index: int | None = None
    for idx, name in enumerate(header):
        if not name:
            continue
        matched = match_feature_list_header(name)
        if matched == "기능 개요":
            overview_index = idx
            continue
        if matched and matched not in column_map:
            column_map[matched] = idx

    if "기능 설명" not in column_map and overview_index is not None:
        column_map["기능 설명"] = overview_index

    for fallback_index, column_name in enumerate(FEATURE_LIST_EXPECTED_HEADERS):
        column_map.setdefault(column_name, fallback_index)

    normalized_records: List[Dict[str, str]] = []
    for raw in rows[1:]:
        entry: Dict[str, str] = {}
        has_value = False
        for column_name in FEATURE_LIST_EXPECTED_HEADERS:
            index = column_map.get(column_name)
            value = ""
            if index is not None and index < len(raw):
                value = raw[index].strip()
            if value:
                has_value = True
            entry[column_name] = value
        if not has_value:
            continue

        normalized_records.append(entry)

    return normalized_records


def normalize_feature_list_records(csv_text: str) -> List[Dict[str, str]]:
    """Public wrapper for feature-list CSV normalisation."""

    return _normalize_feature_list_records(csv_text)


def _locate_feature_list_overview(
    sheet_bytes: bytes,
    shared_strings: Sequence[str],
) -> Tuple[str | None, str]:
    feature_start_row = FEATURE_LIST_START_ROW
    try:
        root = ET.fromstring(sheet_bytes)
    except ET.ParseError:
        return None, ""

    ns = {"s": SPREADSHEET_NS}
    sheet_data = root.find("s:sheetData", ns)
    if sheet_data is None:
        return None, ""

    merges: List[Tuple[str, int, str, int]] = []
    merge_container = root.find("s:mergeCells", ns)
    if merge_container is not None:
        for merge in merge_container.findall("s:mergeCell", ns):
            ref = (merge.get("ref") or "").strip()
            if not ref:
                continue
            try:
                if ":" in ref:
                    start_ref, end_ref = ref.split(":", 1)
                else:
                    start_ref = end_ref = ref
                start_col, start_row = split_cell(start_ref)
                end_col, end_row = split_cell(end_ref)
            except ValueError:
                continue
            merges.append((start_col, start_row, end_col, end_row))

    cell_map: Dict[str, ET.Element] = {}
    for row in sheet_data.findall("s:row", ns):
        for cell in row.findall("s:c", ns):
            ref = (cell.get("r") or "").strip()
            if ref:
                cell_map[ref] = cell

    for ref, cell in cell_map.items():
        try:
            column, row_index = split_cell(ref)
        except ValueError:
            continue

        if row_index >= feature_start_row:
            continue

        raw_text = cell_text_from_sheet(cell, shared_strings=shared_strings).strip()
        if not raw_text:
            continue

        normalized = match_feature_list_header(raw_text) or ""
        normalized_token = _normalize_feature_header_token(raw_text)
        if normalized_token not in {"개요", "프로젝트개요"} and normalized != "기능 개요":
            continue

        column_index = column_to_index(column)
        header_span: Tuple[str, int, str, int] | None = None
        for start_col, start_row, end_col, end_row in merges:
            start_index = column_to_index(start_col)
            end_index = column_to_index(end_col)
            if start_row <= row_index <= end_row and start_index <= column_index <= end_index:
                header_span = (start_col, start_row, end_col, end_row)
                break

        candidate_ref: str | None = None
        candidate_ranges: List[Tuple[str, int, str, int]] = []
        if header_span is not None:
            header_end_row = header_span[3]
            for start_col, start_row, end_col, end_row in merges:
                if start_col == header_span[0] and end_col == header_span[2]:
                    if start_row > header_end_row and start_row <= header_end_row + 6:
                        candidate_ranges.append((start_col, start_row, end_col, end_row))
            if candidate_ranges:
                start_col, start_row, _, _ = min(
                    candidate_ranges, key=lambda item: (item[1], column_to_index(item[0]))
                )
                candidate_ref = f"{start_col}{start_row}"

        if candidate_ref is None:
            next_row = row_index + 1
            for start_col, start_row, end_col, end_row in merges:
                start_index = column_to_index(start_col)
                end_index = column_to_index(end_col)
                if start_row <= next_row <= end_row and start_index <= column_index <= end_index:
                    candidate_ref = f"{start_col}{start_row}"
                    break

        if candidate_ref is None:
            candidate_ref = f"{column}{row_index + 1}"

        cell_elem = cell_map.get(candidate_ref)
        value = ""
        if cell_elem is not None:
            value = cell_text_from_sheet(cell_elem, shared_strings=shared_strings).strip()

        return candidate_ref, value

    return None, ""


def _apply_project_overview_to_sheet(sheet_bytes: bytes, cell_ref: str, value: str) -> bytes:
    try:
        root = ET.fromstring(sheet_bytes)
    except ET.ParseError:
        return sheet_bytes

    try:
        column, row_index = split_cell(cell_ref)
    except ValueError:
        return sheet_bytes

    ns = {"s": SPREADSHEET_NS}
    sheet_data = root.find("s:sheetData", ns)
    if sheet_data is None:
        return sheet_bytes

    row = find_sheet_row(root, row_index)
    if row is None:
        row_tag = f"{{{SPREADSHEET_NS}}}row"
        row = ET.Element(row_tag, {"r": str(row_index)})
        inserted = False
        for idx, existing in enumerate(sheet_data.findall("s:row", ns)):
            existing_r = existing.get("r") or ""
            try:
                existing_index = int(existing_r)
            except ValueError:
                continue
            if existing_index > row_index:
                sheet_data.insert(idx, row)
                inserted = True
                break
        if not inserted:
            sheet_data.append(row)

    cell = find_sheet_cell(row, column)
    if cell is None:
        cell_tag = f"{{{SPREADSHEET_NS}}}c"
        cell = ET.Element(cell_tag, {"r": f"{column}{row_index}"})

        style_candidate = None
        for existing in row.findall("s:c", ns):
            style_attr = existing.get("s")
            if style_attr:
                style_candidate = style_attr
                break
        if style_candidate:
            cell.set("s", style_candidate)

        target_index = column_to_index(column)
        inserted = False
        for idx, existing in enumerate(row.findall("s:c", ns)):
            existing_ref = existing.get("r") or ""
            existing_col = "".join(filter(str.isalpha, existing_ref))
            if not existing_col:
                continue
            if column_to_index(existing_col) > target_index:
                row.insert(idx, cell)
                inserted = True
                break
        if not inserted:
            row.append(cell)

    set_cell_text(cell, value)

    dimension = root.find("s:dimension", ns)
    if dimension is None:
        dimension_tag = f"{{{SPREADSHEET_NS}}}dimension"
        dimension = ET.Element(dimension_tag)
        inserted = False
        for idx, child in enumerate(list(root)):
            if child.tag in {dimension_tag, f"{{{SPREADSHEET_NS}}}sheetData"}:
                root.insert(idx, dimension)
                inserted = True
                break
        if not inserted:
            root.insert(0, dimension)

    ref = (dimension.get("ref") or "").strip()
    current_col_index = column_to_index(column)
    if ref:
        start_col, start_row, end_col, end_row = parse_dimension(ref)
        start_col_index = column_to_index(start_col)
        end_col_index = column_to_index(end_col)
    else:
        start_row = end_row = row_index
        start_col_index = end_col_index = current_col_index

    updated = False
    if row_index < start_row:
        start_row = row_index
        updated = True
    if row_index > end_row:
        end_row = row_index
        updated = True
    if current_col_index < start_col_index:
        start_col_index = current_col_index
        updated = True
    if current_col_index > end_col_index:
        end_col_index = current_col_index
        updated = True

    if updated or not ref:
        dimension.set(
            "ref",
            f"{index_to_column(start_col_index)}{start_row}:{index_to_column(end_col_index)}{end_row}",
        )

    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def extract_feature_list_overview(workbook_bytes: bytes) -> Tuple[str | None, str]:
    with zipfile.ZipFile(io.BytesIO(workbook_bytes), "r") as source:
        sheet_bytes = source.read(XLSX_SHEET_PATH)
        try:
            shared_strings_bytes = source.read("xl/sharedStrings.xml")
        except KeyError:
            shared_strings_bytes = b""

    shared_strings = parse_shared_strings(shared_strings_bytes)
    return _locate_feature_list_overview(sheet_bytes, shared_strings)


def populate_feature_list(
    workbook_bytes: bytes,
    csv_text: str,
    project_overview: str | None = None,
) -> bytes:
    records = _normalize_feature_list_records(csv_text)
    with zipfile.ZipFile(io.BytesIO(workbook_bytes), "r") as source:
        sheet_bytes = source.read(XLSX_SHEET_PATH)
        try:
            shared_strings_bytes = source.read("xl/sharedStrings.xml")
        except KeyError:
            shared_strings_bytes = b""

    shared_strings = parse_shared_strings(shared_strings_bytes)
    overview_ref, _ = _locate_feature_list_overview(sheet_bytes, shared_strings)

    populator = WorksheetPopulator(sheet_bytes, start_row=FEATURE_LIST_START_ROW, columns=FEATURE_LIST_COLUMNS)
    populator.populate(records)

    updated_sheet = populator.to_bytes()
    if overview_ref and project_overview is not None:
        updated_sheet = _apply_project_overview_to_sheet(updated_sheet, overview_ref, project_overview)

    return replace_sheet_bytes(workbook_bytes, updated_sheet)
