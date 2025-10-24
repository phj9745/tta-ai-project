from __future__ import annotations

import copy
import io
import re
import zipfile
from typing import Dict, List, Sequence
from xml.etree import ElementTree as ET

from .models import (
    ColumnSpec,
    SPREADSHEET_NS,
    XML_NS,
    XLSX_SHEET_PATH,
)
from .utils import safe_int

__all__ = [
    "column_to_index",
    "index_to_column",
    "split_cell",
    "parse_dimension",
    "parse_shared_strings",
    "cell_text_from_sheet",
    "find_sheet_row",
    "find_sheet_cell",
    "set_cell_text",
    "replace_sheet_bytes",
    "WorksheetPopulator",
]


def column_to_index(letter: str) -> int:
    result = 0
    for char in letter:
        if not char.isalpha():
            break
        result = result * 26 + (ord(char.upper()) - ord("A") + 1)
    return result


def index_to_column(index: int) -> str:
    if index <= 0:
        index = 1
    letters: List[str] = []
    while index:
        index, remainder = divmod(index - 1, 26)
        letters.append(chr(ord("A") + remainder))
    if not letters:
        return "A"
    return "".join(reversed(letters))


_CELL_REFERENCE_PATTERN = re.compile(r"([A-Z]+)(\d+)")


def split_cell(reference: str) -> tuple[str, int]:
    match = _CELL_REFERENCE_PATTERN.match(reference)
    if not match:
        raise ValueError(f"셀 참조를 해석할 수 없습니다: {reference}")
    column, row = match.groups()
    return column, int(row)


def parse_dimension(ref: str) -> tuple[str, int, str, int]:
    if ":" in ref:
        start_ref, end_ref = ref.split(":", 1)
    else:
        start_ref = end_ref = ref
    start_col, start_row = split_cell(start_ref)
    end_col, end_row = split_cell(end_ref)
    return start_col, start_row, end_col, end_row


def parse_shared_strings(data: bytes) -> List[str]:
    if not data:
        return []

    try:
        root = ET.fromstring(data)
    except ET.ParseError:
        return []

    ns = {"s": SPREADSHEET_NS}
    values: List[str] = []
    for si in root.findall("s:si", ns):
        text_segments: List[str] = []
        for text_node in si.findall(".//s:t", ns):
            if text_node.text:
                text_segments.append(text_node.text)
        values.append("".join(text_segments))
    return values


def cell_text_from_sheet(
    cell: ET.Element,
    *,
    shared_strings: Sequence[str],
) -> str:
    text_type = (cell.get("t") or "").strip().lower()
    ns = {"s": SPREADSHEET_NS}

    if text_type == "inlinestr":
        text_elem = cell.find("s:is/s:t", ns)
        return text_elem.text if text_elem is not None and text_elem.text else ""

    value_elem = cell.find("s:v", ns)
    if value_elem is None or value_elem.text is None:
        return ""

    if text_type == "s":
        try:
            index = int(value_elem.text)
        except ValueError:
            return ""
        if 0 <= index < len(shared_strings):
            return shared_strings[index] or ""
        return ""

    return value_elem.text or ""


def find_sheet_row(root: ET.Element, row_index: int) -> ET.Element | None:
    ns = {"s": SPREADSHEET_NS}
    return root.find(f"s:sheetData/s:row[@r='{row_index}']", ns)


def find_sheet_cell(row: ET.Element, column: str) -> ET.Element | None:
    ns = {"s": SPREADSHEET_NS}
    target_index = column_to_index(column)
    for cell in row.findall("s:c", ns):
        ref = (cell.get("r") or "").strip()
        if ref:
            cell_column = "".join(filter(str.isalpha, ref))
        else:
            cell_column = ""
        if cell_column and column_to_index(cell_column) == target_index:
            return cell
    return None


def _clear_cell(cell: ET.Element) -> None:
    if "t" in cell.attrib:
        del cell.attrib["t"]
    for child in list(cell):
        cell.remove(child)


def set_cell_text(cell: ET.Element, value: str) -> None:
    _clear_cell(cell)
    cleaned = value.strip()
    if not cleaned:
        return

    cell.set("t", "inlineStr")
    is_elem = ET.SubElement(cell, f"{{{SPREADSHEET_NS}}}is")
    text_elem = ET.SubElement(is_elem, f"{{{SPREADSHEET_NS}}}t")
    if cleaned != value or "\n" in value:
        text_elem.set(f"{{{XML_NS}}}space", "preserve")
        text_elem.text = value
    else:
        text_elem.text = cleaned


def replace_sheet_bytes(workbook_bytes: bytes, new_sheet_bytes: bytes) -> bytes:
    source_buffer = io.BytesIO(workbook_bytes)
    output_buffer = io.BytesIO()
    with zipfile.ZipFile(source_buffer, "r") as source_zip:
        with zipfile.ZipFile(output_buffer, "w") as target_zip:
            for info in source_zip.infolist():
                data = source_zip.read(info.filename)
                if info.filename == XLSX_SHEET_PATH:
                    data = new_sheet_bytes
                target_zip.writestr(info, data)
    return output_buffer.getvalue()


class WorksheetPopulator:
    def __init__(
        self,
        sheet_bytes: bytes,
        *,
        start_row: int,
        columns: Sequence[ColumnSpec],
    ) -> None:
        self._ns = {"s": SPREADSHEET_NS}
        self._root = ET.fromstring(sheet_bytes)
        self._sheet_data = self._root.find("s:sheetData", self._ns)
        if self._sheet_data is None:
            raise ValueError("워크시트 데이터 영역을 찾을 수 없습니다.")

        self._start_row = start_row
        self._column_specs = list(columns)
        if not self._column_specs:
            raise ValueError("채울 열 정보가 없습니다.")

        self._dimension = self._root.find("s:dimension", self._ns)
        ref = ""
        if self._dimension is not None:
            ref = (self._dimension.get("ref") or "").strip()

        if not ref:
            ref = self._infer_dimension()
            if not ref:
                raise ValueError("워크시트 범위 정보를 찾을 수 없습니다.")

            dimension_tag = f"{{{SPREADSHEET_NS}}}dimension"
            if self._dimension is None:
                self._dimension = ET.Element(dimension_tag)
                inserted = False
                for idx, child in enumerate(list(self._root)):
                    if child.tag in {dimension_tag, f"{{{SPREADSHEET_NS}}}sheetData"}:
                        self._root.insert(idx, self._dimension)
                        inserted = True
                        break
                if not inserted:
                    self._root.insert(0, self._dimension)
            self._dimension.set("ref", ref)

        (
            self._dimension_start_col,
            self._dimension_start_row,
            self._dimension_end_col,
            self._dimension_end_row,
        ) = parse_dimension(ref)

        self._row_cache: Dict[int, ET.Element] = {}
        for row in self._sheet_data.findall("s:row", self._ns):
            r_attr = row.get("r")
            if not r_attr:
                continue
            try:
                index = int(r_attr)
            except ValueError:
                continue
            self._row_cache[index] = row

        template_row = self._row_cache.get(self._start_row)
        if template_row is None:
            raise ValueError("템플릿 행을 찾을 수 없습니다.")
        self._template_row = copy.deepcopy(template_row)

    def _infer_dimension(self) -> str | None:
        min_col: int | None = None
        max_col: int | None = None
        min_row: int | None = None
        max_row: int | None = None

        for row in self._sheet_data.findall("s:row", self._ns):
            row_index = safe_int(row.get("r"))
            if row_index is not None:
                if min_row is None or row_index < min_row:
                    min_row = row_index
                if max_row is None or row_index > max_row:
                    max_row = row_index

            for cell in row.findall("s:c", self._ns):
                ref = (cell.get("r") or "").strip()
                if not ref:
                    continue
                try:
                    column, row_number = split_cell(ref)
                except ValueError:
                    if row_index is None:
                        continue
                    column = "".join(filter(str.isalpha, ref))
                    if not column:
                        continue
                    row_number = row_index

                column_index = column_to_index(column)
                if column_index:
                    if min_col is None or column_index < min_col:
                        min_col = column_index
                    if max_col is None or column_index > max_col:
                        max_col = column_index
                if row_number:
                    if min_row is None or row_number < min_row:
                        min_row = row_number
                    if max_row is None or row_number > max_row:
                        max_row = row_number

        if (min_col is None or max_col is None) and self._column_specs:
            column_indices = [
                column_to_index(spec.letter)
                for spec in self._column_specs
                if spec.letter
            ]
            if column_indices:
                if min_col is None:
                    min_col = min(column_indices)
                if max_col is None:
                    max_col = max(column_indices)

        if min_row is None:
            min_row = self._start_row
        if max_row is None:
            max_row = self._start_row

        if min_col is None or max_col is None:
            return None

        start_col = index_to_column(min_col)
        end_col = index_to_column(max_col)
        return f"{start_col}{min_row}:{end_col}{max_row}"

    def _tag(self, name: str) -> str:
        return f"{{{SPREADSHEET_NS}}}{name}"

    @staticmethod
    def _cell_column(cell: ET.Element) -> str:
        ref = cell.get("r", "")
        return "".join(filter(str.isalpha, ref))

    def _ensure_row(self, index: int) -> ET.Element:
        if index in self._row_cache:
            return self._row_cache[index]

        row = copy.deepcopy(self._template_row)
        row.set("r", str(index))
        for cell in row.findall("s:c", self._ns):
            column = self._cell_column(cell)
            cell.set("r", f"{column}{index}")
            _clear_cell(cell)
        self._sheet_data.append(row)
        self._row_cache[index] = row
        if index > self._dimension_end_row:
            self._dimension_end_row = index
        return row

    def _clear_row(self, row: ET.Element) -> None:
        for cell in row.findall("s:c", self._ns):
            _clear_cell(cell)

    def _ensure_cell(self, row: ET.Element, spec: ColumnSpec) -> ET.Element:
        column = spec.letter
        target_index = column_to_index(column)
        for cell in row.findall("s:c", self._ns):
            if self._cell_column(cell) == column:
                cell.set("r", f"{column}{row.get('r')}")
                cell.set("s", spec.style)
                return cell

        new_cell = ET.Element(self._tag("c"), {
            "r": f"{column}{row.get('r')}",
            "s": spec.style,
        })
        inserted = False
        for idx, existing in enumerate(list(row)):
            if existing.tag != self._tag("c"):
                continue
            existing_col = self._cell_column(existing)
            if column_to_index(existing_col) > target_index:
                row.insert(idx, new_cell)
                inserted = True
                break
        if not inserted:
            row.append(new_cell)
        return new_cell

    def populate(self, records: Sequence[Dict[str, str]]) -> None:
        for index, row in self._row_cache.items():
            if index >= self._start_row:
                self._clear_row(row)

        for offset, record in enumerate(records):
            row_index = self._start_row + offset
            row = self._ensure_row(row_index)
            for spec in self._column_specs:
                value = record.get(spec.key, "")
                cell = self._ensure_cell(row, spec)
                set_cell_text(cell, value)

        limit = self._start_row + len(records)
        for index in sorted(self._row_cache):
            if index >= limit:
                row = self._row_cache[index]
                self._clear_row(row)

        if records:
            last_row = self._start_row + len(records) - 1
        else:
            last_row = self._start_row
        if last_row > self._dimension_end_row:
            self._dimension_end_row = last_row
        self._dimension.set(
            "ref",
            f"{self._dimension_start_col}{self._dimension_start_row}:{self._dimension_end_col}{self._dimension_end_row}",
        )

    def to_bytes(self) -> bytes:
        return ET.tostring(self._root, encoding="utf-8", xml_declaration=True)
