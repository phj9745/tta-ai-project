from __future__ import annotations

import csv
import io
import re
import copy
from dataclasses import dataclass
from typing import Dict, Iterable, List, Mapping, Sequence, Tuple
from xml.etree import ElementTree as ET
import zipfile
from copy import copy as clone_style

_SPREADSHEET_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
_XML_NS = "http://www.w3.org/XML/1998/namespace"
_XLSX_SHEET_PATH = "xl/worksheets/sheet1.xml"
_DRAWING_NS = "http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing"
_DRAWING_A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
_REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
_CONTENT_TYPES_NS = "http://schemas.openxmlformats.org/package/2006/content-types"
_EMU_PER_PIXEL = 9525
_IMAGE_VERTICAL_GAP_PX = 4


@dataclass(frozen=True)
class ColumnSpec:
    key: str
    letter: str
    style: str


@dataclass(frozen=True)
class DefectReportImage:
    file_name: str
    content: bytes
    content_type: str | None = None


def _safe_int(value: object) -> int | None:
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


def _append_attachment_note(value: object, names: Sequence[str]) -> str:
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


def _column_width_to_pixels(width: float) -> int:
    if width <= 0:
        return 64
    return max(1, int(round(width * 7.0 + 5)))


def _row_height_to_pixels(height_points: float) -> float:
    if height_points <= 0:
        height_points = 15.0
    return height_points * 96.0 / 72.0


def _pixels_to_emu(pixels: float) -> int:
    if pixels <= 0:
        pixels = 1
    return int(round(pixels * _EMU_PER_PIXEL))


def _image_dimensions(content: bytes) -> Tuple[int, int]:
    if len(content) >= 24 and content.startswith(b"\x89PNG\r\n\x1a\n"):
        width = int.from_bytes(content[16:20], "big")
        height = int.from_bytes(content[20:24], "big")
        return width, height

    if len(content) > 4 and content.startswith(b"\xff\xd8"):
        index = 2
        length = len(content)
        while index + 9 < length:
            if content[index] != 0xFF:
                break
            marker = content[index + 1]
            if marker == 0xD9:
                break
            if marker in {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}:
                block_length = int.from_bytes(content[index + 2 : index + 4], "big")
                start = index + 4
                if start + 5 < length:
                    height = int.from_bytes(content[start + 1 : start + 3], "big")
                    width = int.from_bytes(content[start + 3 : start + 5], "big")
                    return width, height
                break
            block_length = int.from_bytes(content[index + 2 : index + 4], "big")
            if block_length <= 0:
                break
            index += 2 + block_length

    return 0, 0


def _scale_image_dimensions(content: bytes, max_width_px: int) -> Tuple[int, int]:
    width, height = _image_dimensions(content)
    if width <= 0 or height <= 0:
        width = max_width_px
        height = int(round(max_width_px * 0.75))
    scale = 1.0
    if width > max_width_px > 0:
        scale = max_width_px / float(width)
    scaled_width = max(1, int(round(width * scale)))
    scaled_height = max(1, int(round(height * scale)))
    return scaled_width, scaled_height


def _normalized_image_filename(name: str, used: Dict[str, int]) -> str:
    base = (name or "defect-image").strip()
    base = re.sub(r"[^A-Za-z0-9._-]", "_", base) or "defect-image"
    if "." not in base:
        base = f"{base}.png"
    root, dot, ext = base.rpartition(".")
    if not root:
        root = ext
        ext = "png"
    ext = ext.lower()
    key = f"{root}.{ext}" if dot else f"{root}.{ext}"
    count = used.get(key, 0)
    if count:
        key = f"{root}_{count}.{ext}"
    used[f"{root}.{ext}"] = count + 1
    return key

def _column_to_index(letter: str) -> int:
    result = 0
    for char in letter:
        if not char.isalpha():
            break
        result = result * 26 + (ord(char.upper()) - ord("A") + 1)
    return result


def _index_to_column(index: int) -> str:
    if index <= 0:
        index = 1
    letters: List[str] = []
    while index:
        index, remainder = divmod(index - 1, 26)
        letters.append(chr(ord("A") + remainder))
    if not letters:
        return "A"
    return "".join(reversed(letters))


def _split_cell(reference: str) -> tuple[str, int]:
    match = re.match(r"([A-Z]+)(\d+)", reference)
    if not match:
        raise ValueError(f"셀 참조를 해석할 수 없습니다: {reference}")
    column, row = match.groups()
    return column, int(row)


def _parse_dimension(ref: str) -> tuple[str, int, str, int]:
    if ":" in ref:
        start_ref, end_ref = ref.split(":", 1)
    else:
        start_ref = end_ref = ref
    start_col, start_row = _split_cell(start_ref)
    end_col, end_row = _split_cell(end_ref)
    return start_col, start_row, end_col, end_row


def _parse_shared_strings(data: bytes) -> List[str]:
    if not data:
        return []

    try:
        root = ET.fromstring(data)
    except ET.ParseError:
        return []

    ns = {"s": _SPREADSHEET_NS}
    values: List[str] = []
    for si in root.findall("s:si", ns):
        text_segments: List[str] = []
        for text_node in si.findall(".//s:t", ns):
            if text_node.text:
                text_segments.append(text_node.text)
        values.append("".join(text_segments))
    return values


def _cell_text_from_sheet(
    cell: ET.Element,
    *,
    shared_strings: Sequence[str],
) -> str:
    text_type = (cell.get("t") or "").strip().lower()
    ns = {"s": _SPREADSHEET_NS}

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


def _find_sheet_row(root: ET.Element, row_index: int) -> ET.Element | None:
    ns = {"s": _SPREADSHEET_NS}
    return root.find(f"s:sheetData/s:row[@r='{row_index}']", ns)


def _find_sheet_cell(row: ET.Element, column: str) -> ET.Element | None:
    ns = {"s": _SPREADSHEET_NS}
    target_index = _column_to_index(column)
    for cell in row.findall("s:c", ns):
        ref = (cell.get("r") or "").strip()
        if ref:
            cell_column = "".join(filter(str.isalpha, ref))
        else:
            cell_column = ""
        if cell_column and _column_to_index(cell_column) == target_index:
            return cell
    return None


def _clear_cell(cell: ET.Element) -> None:
    if "t" in cell.attrib:
        del cell.attrib["t"]
    for child in list(cell):
        cell.remove(child)


def _set_cell_text(cell: ET.Element, value: str) -> None:
    _clear_cell(cell)
    cleaned = value.strip()
    if not cleaned:
        return

    cell.set("t", "inlineStr")
    is_elem = ET.SubElement(cell, f"{{{_SPREADSHEET_NS}}}is")
    text_elem = ET.SubElement(is_elem, f"{{{_SPREADSHEET_NS}}}t")
    if cleaned != value or "\n" in value:
        text_elem.set(f"{{{_XML_NS}}}space", "preserve")
        text_elem.text = value
    else:
        text_elem.text = cleaned


def _locate_feature_list_overview(
    sheet_bytes: bytes,
    shared_strings: Sequence[str],
) -> Tuple[str | None, str]:
    try:
        root = ET.fromstring(sheet_bytes)
    except ET.ParseError:
        return None, ""

    ns = {"s": _SPREADSHEET_NS}
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
                start_col, start_row = _split_cell(start_ref)
                end_col, end_row = _split_cell(end_ref)
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
            column, row_index = _split_cell(ref)
        except ValueError:
            continue

        if row_index >= _FEATURE_LIST_START_ROW:
            continue

        raw_text = _cell_text_from_sheet(cell, shared_strings=shared_strings).strip()
        if not raw_text:
            continue

        normalized = match_feature_list_header(raw_text) or ""
        normalized_token = _normalize_feature_header_token(raw_text)
        if normalized_token not in {"개요", "프로젝트개요"} and normalized != "기능 개요":
            continue

        column_index = _column_to_index(column)
        header_span: Tuple[str, int, str, int] | None = None
        for start_col, start_row, end_col, end_row in merges:
            start_index = _column_to_index(start_col)
            end_index = _column_to_index(end_col)
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
                    candidate_ranges, key=lambda item: (item[1], _column_to_index(item[0]))
                )
                candidate_ref = f"{start_col}{start_row}"

        if candidate_ref is None:
            next_row = row_index + 1
            for start_col, start_row, end_col, end_row in merges:
                start_index = _column_to_index(start_col)
                end_index = _column_to_index(end_col)
                if start_row <= next_row <= end_row and start_index <= column_index <= end_index:
                    candidate_ref = f"{start_col}{start_row}"
                    break

        if candidate_ref is None:
            candidate_ref = f"{column}{row_index + 1}"

        cell_elem = cell_map.get(candidate_ref)
        value = ""
        if cell_elem is not None:
            value = _cell_text_from_sheet(cell_elem, shared_strings=shared_strings).strip()

        return candidate_ref, value

    return None, ""


def _apply_project_overview_to_sheet(sheet_bytes: bytes, cell_ref: str, value: str) -> bytes:
    try:
        root = ET.fromstring(sheet_bytes)
    except ET.ParseError:
        return sheet_bytes

    try:
        column, row_index = _split_cell(cell_ref)
    except ValueError:
        return sheet_bytes

    ns = {"s": _SPREADSHEET_NS}
    sheet_data = root.find("s:sheetData", ns)
    if sheet_data is None:
        return sheet_bytes

    row = _find_sheet_row(root, row_index)
    if row is None:
        row_tag = f"{{{_SPREADSHEET_NS}}}row"
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

    cell = _find_sheet_cell(row, column)
    if cell is None:
        cell_tag = f"{{{_SPREADSHEET_NS}}}c"
        cell = ET.Element(cell_tag, {"r": f"{column}{row_index}"})

        style_candidate = None
        for existing in row.findall("s:c", ns):
            style_attr = existing.get("s")
            if style_attr:
                style_candidate = style_attr
                break
        if style_candidate:
            cell.set("s", style_candidate)

        target_index = _column_to_index(column)
        inserted = False
        for idx, existing in enumerate(row.findall("s:c", ns)):
            existing_ref = existing.get("r") or ""
            existing_col = "".join(filter(str.isalpha, existing_ref))
            if not existing_col:
                continue
            if _column_to_index(existing_col) > target_index:
                row.insert(idx, cell)
                inserted = True
                break
        if not inserted:
            row.append(cell)

    _set_cell_text(cell, value)

    dimension = root.find("s:dimension", ns)
    if dimension is None:
        dimension_tag = f"{{{_SPREADSHEET_NS}}}dimension"
        dimension = ET.Element(dimension_tag)
        inserted = False
        for idx, child in enumerate(list(root)):
            if child.tag in {dimension_tag, f"{{{_SPREADSHEET_NS}}}sheetData"}:
                root.insert(idx, dimension)
                inserted = True
                break
        if not inserted:
            root.insert(0, dimension)

    ref = (dimension.get("ref") or "").strip()
    current_col_index = _column_to_index(column)
    if ref:
        start_col, start_row, end_col, end_row = _parse_dimension(ref)
        start_col_index = _column_to_index(start_col)
        end_col_index = _column_to_index(end_col)
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
            f"{_index_to_column(start_col_index)}{start_row}:{_index_to_column(end_col_index)}{end_row}",
        )

    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


class WorksheetPopulator:
    def __init__(
        self,
        sheet_bytes: bytes,
        *,
        start_row: int,
        columns: Sequence[ColumnSpec],
    ) -> None:
        self._ns = {"s": _SPREADSHEET_NS}
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

            dimension_tag = f"{{{_SPREADSHEET_NS}}}dimension"
            if self._dimension is None:
                self._dimension = ET.Element(dimension_tag)
                inserted = False
                for idx, child in enumerate(list(self._root)):
                    if child.tag in {dimension_tag, f"{{{_SPREADSHEET_NS}}}sheetData"}:
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
        ) = _parse_dimension(ref)

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
            row_index = _safe_int(row.get("r"))
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
                    column, row_number = _split_cell(ref)
                except ValueError:
                    if row_index is None:
                        continue
                    column = "".join(filter(str.isalpha, ref))
                    if not column:
                        continue
                    row_number = row_index

                column_index = _column_to_index(column)
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
                _column_to_index(spec.letter)
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

        start_col = _index_to_column(min_col)
        end_col = _index_to_column(max_col)
        return f"{start_col}{min_row}:{end_col}{max_row}"

    def _tag(self, name: str) -> str:
        return f"{{{_SPREADSHEET_NS}}}{name}"

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
            self._clear_cell(cell)
        self._sheet_data.append(row)
        self._row_cache[index] = row
        if index > self._dimension_end_row:
            self._dimension_end_row = index
        return row

    def _clear_cell(self, cell: ET.Element) -> None:
        if "t" in cell.attrib:
            del cell.attrib["t"]
        for child in list(cell):
            cell.remove(child)

    def _clear_row(self, row: ET.Element) -> None:
        for cell in row.findall("s:c", self._ns):
            self._clear_cell(cell)

    def _ensure_cell(self, row: ET.Element, spec: ColumnSpec) -> ET.Element:
        column = spec.letter
        target_index = _column_to_index(column)
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
            if _column_to_index(existing_col) > target_index:
                row.insert(idx, new_cell)
                inserted = True
                break
        if not inserted:
            row.append(new_cell)
        return new_cell

    def _set_cell_value(self, cell: ET.Element, value: str) -> None:
        self._clear_cell(cell)
        cleaned = value.strip()
        if not cleaned:
            return

        cell.set("t", "inlineStr")
        is_elem = ET.SubElement(cell, self._tag("is"))
        t_elem = ET.SubElement(is_elem, self._tag("t"))
        if cleaned != value or "\n" in value:
            t_elem.set(f"{{{_XML_NS}}}space", "preserve")
            t_elem.text = value
        else:
            t_elem.text = cleaned

    def populate(self, records: Sequence[Dict[str, str]]) -> None:
        # 우선 기존 데이터를 비웁니다.
        for index, row in self._row_cache.items():
            if index >= self._start_row:
                self._clear_row(row)

        for offset, record in enumerate(records):
            row_index = self._start_row + offset
            row = self._ensure_row(row_index)
            for spec in self._column_specs:
                value = record.get(spec.key, "")
                cell = self._ensure_cell(row, spec)
                self._set_cell_value(cell, value)

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


def _replace_sheet_bytes(workbook_bytes: bytes, new_sheet_bytes: bytes) -> bytes:
    source_buffer = io.BytesIO(workbook_bytes)
    output_buffer = io.BytesIO()
    with zipfile.ZipFile(source_buffer, "r") as source_zip:
        with zipfile.ZipFile(output_buffer, "w") as target_zip:
            for info in source_zip.infolist():
                data = source_zip.read(info.filename)
                if info.filename == _XLSX_SHEET_PATH:
                    data = new_sheet_bytes
                target_zip.writestr(info, data)
    return output_buffer.getvalue()


def _parse_csv_records(csv_text: str, expected_columns: Sequence[str]) -> List[Dict[str, str]]:
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
            idx = column_index[column]
            value = raw[idx].strip() if idx < len(raw) else ""
            if value:
                is_empty = False
            entry[column] = value
        if not is_empty:
            records.append(entry)
    return records


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


FEATURE_LIST_COLUMNS: Sequence[ColumnSpec] = (
    ColumnSpec(key="대분류", letter="A", style="12"),
    ColumnSpec(key="중분류", letter="B", style="8"),
    ColumnSpec(key="소분류", letter="C", style="15"),
    ColumnSpec(key="기능 설명", letter="D", style="7"),
    ColumnSpec(key="기능 개요", letter="E", style="9"),
)

FEATURE_LIST_EXPECTED_HEADERS: Sequence[str] = [
    "대분류",
    "중분류",
    "소분류",
    "기능 설명",
    "기능 개요",
]


def summarize_feature_description(value: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        return ""

    segments = re.split(r"[\r\n]+|(?<=[.!?])\s+", cleaned)
    for segment in segments:
        candidate = segment.strip(" \u2022-•·")
        if candidate:
            if len(candidate) > 160:
                return candidate[:157].rstrip() + "…"
            return candidate

    if len(cleaned) > 160:
        return cleaned[:157].rstrip() + "…"
    return cleaned


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
    for idx, name in enumerate(header):
        if not name:
            continue
        matched = match_feature_list_header(name)
        if matched and matched not in column_map:
            column_map[matched] = idx

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

        overview = entry.get("기능 개요", "")
        description = entry.get("기능 설명", "")
        if not overview and description:
            entry["기능 개요"] = summarize_feature_description(description)
        elif overview and not description:
            entry["기능 설명"] = overview

        normalized_records.append(entry)

    return normalized_records

    segments = re.split(r"[\r\n]+|(?<=[.!?])\s+", cleaned)
    for segment in segments:
        candidate = segment.strip(" \u2022-•·")
        if candidate:
            if len(candidate) > 160:
                return candidate[:157].rstrip() + "…"
            return candidate

def populate_feature_list(workbook_bytes: bytes, csv_text: str) -> bytes:
    records = _normalize_feature_list_records(csv_text)
    with zipfile.ZipFile(io.BytesIO(workbook_bytes), "r") as source:
        sheet_bytes = source.read(_XLSX_SHEET_PATH)
        try:
            shared_strings_bytes = source.read("xl/sharedStrings.xml")
        except KeyError:
            shared_strings_bytes = b""

    shared_strings = _parse_shared_strings(shared_strings_bytes)
    return _locate_feature_list_overview(sheet_bytes, shared_strings)


def populate_feature_list(
    workbook_bytes: bytes,
    csv_text: str,
    project_overview: str | None = None,
) -> bytes:
    records = _normalize_feature_list_records(csv_text)
    with zipfile.ZipFile(io.BytesIO(workbook_bytes), "r") as source:
        sheet_bytes = source.read(_XLSX_SHEET_PATH)
        try:
            shared_strings_bytes = source.read("xl/sharedStrings.xml")
        except KeyError:
            shared_strings_bytes = b""

    shared_strings = _parse_shared_strings(shared_strings_bytes)
    overview_ref, _ = _locate_feature_list_overview(sheet_bytes, shared_strings)

    populator = WorksheetPopulator(sheet_bytes, start_row=8, columns=FEATURE_LIST_COLUMNS)
    populator.populate(records)

    updated_sheet = populator.to_bytes()
    if overview_ref and project_overview is not None:
        updated_sheet = _apply_project_overview_to_sheet(updated_sheet, overview_ref, project_overview)

    return _replace_sheet_bytes(workbook_bytes, updated_sheet)


TESTCASE_COLUMNS: Sequence[ColumnSpec] = (
    ColumnSpec(key="대분류", letter="A", style="31"),
    ColumnSpec(key="중분류", letter="B", style="31"),
    ColumnSpec(key="소분류", letter="C", style="18"),
    ColumnSpec(key="테스트 케이스 ID", letter="D", style="24"),
    ColumnSpec(key="테스트 시나리오", letter="E", style="18"),
    ColumnSpec(key="입력(사전조건 포함)", letter="F", style="18"),
    ColumnSpec(key="기대 출력(사후조건 포함)", letter="G", style="18"),
    ColumnSpec(key="테스트 결과", letter="H", style="19"),
    ColumnSpec(key="상세 테스트 결과", letter="I", style="7"),
    ColumnSpec(key="비고", letter="J", style="6"),
)

TESTCASE_EXPECTED_HEADERS: Sequence[str] = [
    "대분류",
    "중분류",
    "소분류",
    "테스트 케이스 ID",
    "테스트 시나리오",
    "입력(사전조건 포함)",
    "기대 출력(사후조건 포함)",
    "테스트 결과",
    "상세 테스트 결과",
    "비고",
]


def populate_testcase_list(workbook_bytes: bytes, csv_text: str) -> bytes:
    records = _parse_csv_records(csv_text, TESTCASE_EXPECTED_HEADERS)
    with zipfile.ZipFile(io.BytesIO(workbook_bytes), "r") as source:
        sheet_bytes = source.read(_XLSX_SHEET_PATH)
    populator = WorksheetPopulator(sheet_bytes, start_row=6, columns=TESTCASE_COLUMNS)
    populator.populate(records)
    return _replace_sheet_bytes(workbook_bytes, populator.to_bytes())


DEFECT_REPORT_COLUMNS: Sequence[ColumnSpec] = (
    ColumnSpec(key="순번", letter="A", style="24"),
    ColumnSpec(key="시험환경(OS)", letter="B", style="25"),
    ColumnSpec(key="결함요약", letter="C", style="10"),
    ColumnSpec(key="결함정도", letter="D", style="26"),
    ColumnSpec(key="발생빈도", letter="E", style="26"),
    ColumnSpec(key="품질특성", letter="F", style="25"),
    ColumnSpec(key="결함 설명", letter="G", style="23"),
    ColumnSpec(key="업체 응답", letter="H", style="10"),
    ColumnSpec(key="수정여부", letter="I", style="10"),
    ColumnSpec(key="비고", letter="J", style="11"),
)

DEFECT_REPORT_EXPECTED_HEADERS: Sequence[str] = [
    "순번",
    "시험환경(OS)",
    "결함요약",
    "결함정도",
    "발생빈도",
    "품질특성",
    "결함 설명",
    "업체 응답",
    "수정여부",
    "비고",
]

SECURITY_REPORT_EXPECTED_HEADERS: Sequence[str] = [
    "순번",
    "시험환경 OS",
    "결함 요약",
    "결함 정도",
    "발생 빈도",
    "품질 특성",
    "결함 설명",
    "업체 응답",
    "수정여부",
    "비고",
    "매핑 유형",
]


def populate_defect_report(
    workbook_bytes: bytes,
    csv_text: str,
    *,
    images: Mapping[int, Sequence[DefectReportImage]] | None = None,
    attachment_notes: Mapping[int, Sequence[str]] | None = None,
) -> bytes:
    records = _parse_csv_records(csv_text, DEFECT_REPORT_EXPECTED_HEADERS)

    with zipfile.ZipFile(io.BytesIO(workbook_bytes), "r") as source:
        sheet_bytes = source.read(_XLSX_SHEET_PATH)

    start_row = 6
    notes_map = attachment_notes or {}
    row_positions: Dict[int, int] = {}
    normalized_records: List[Dict[str, str]] = []

    for offset, record in enumerate(records):
        entry = dict(record)
        index_value = _safe_int(entry.get("순번"))
        if index_value is not None:
            row_positions[index_value] = start_row + offset
            note_names = notes_map.get(index_value)
            if note_names:
                entry["비고"] = _append_attachment_note(entry.get("비고"), note_names)
        normalized_records.append(entry)

    populator = WorksheetPopulator(
        sheet_bytes, start_row=start_row, columns=DEFECT_REPORT_COLUMNS
    )
    populator.populate(normalized_records)
    populated_sheet = populator.to_bytes()

    image_map = images or {}
    if not image_map:
        return _replace_sheet_bytes(workbook_bytes, populated_sheet)

    return _inject_defect_images(
        workbook_bytes,
        populated_sheet,
        row_positions,
        image_map,
        column_letter="J",
    )


def populate_security_report(workbook_bytes: bytes, csv_text: str) -> bytes:
    records = _parse_csv_records(csv_text, SECURITY_REPORT_EXPECTED_HEADERS)

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(DEFECT_REPORT_EXPECTED_HEADERS)
    for record in records:
        writer.writerow(
            [
                record.get("순번", ""),
                record.get("시험환경 OS", ""),
                record.get("결함 요약", ""),
                record.get("결함 정도", ""),
                record.get("발생 빈도", ""),
                record.get("품질 특성", ""),
                record.get("결함 설명", ""),
                record.get("업체 응답", ""),
                record.get("수정여부", ""),
                record.get("비고", ""),
            ]
        )

    converted_csv = buffer.getvalue()
    return populate_defect_report(workbook_bytes, converted_csv)


def _locate_column_width(root: ET.Element, column_index: int) -> float | None:
    namespace = {"main": _SPREADSHEET_NS}
    cols = root.find("main:cols", namespace)
    if cols is None:
        return None
    for col in cols.findall("main:col", namespace):
        try:
            min_idx = int(col.get("min", "0"))
            max_idx = int(col.get("max", "0"))
        except ValueError:
            continue
        if min_idx <= column_index <= max_idx:
            width_attr = col.get("width")
            if width_attr:
                try:
                    return float(width_attr)
                except ValueError:
                    continue
    return None


def _prepare_defect_image_anchors(
    sheet_root: ET.Element,
    row_positions: Dict[int, int],
    images_map: Mapping[int, Sequence[DefectReportImage]],
    column_letter: str,
) -> Tuple[ET.Element, List[Dict[str, object]], float]:
    namespace = {"main": _SPREADSHEET_NS}
    sheet_data = sheet_root.find("main:sheetData", namespace)
    if sheet_data is None:
        raise ValueError("워크시트 데이터 영역을 찾을 수 없습니다.")

    sheet_format = sheet_root.find("main:sheetFormatPr", namespace)
    default_row_height = 15.0
    if sheet_format is not None:
        try:
            default_row_height = float(sheet_format.get("defaultRowHeight", default_row_height))
        except (TypeError, ValueError):
            default_row_height = 15.0

    column_index = _column_to_index(column_letter)
    column_width = _locate_column_width(sheet_root, column_index) or 8.43
    column_width_px = max(1, _column_width_to_pixels(column_width))

    row_elements: Dict[int, ET.Element] = {}
    for row in sheet_data.findall("main:row", namespace):
        r_attr = row.get("r")
        if not r_attr:
            continue
        try:
            row_elements[int(r_attr)] = row
        except ValueError:
            continue

    anchors: List[Dict[str, object]] = []
    for defect_index, attachments in images_map.items():
        if not attachments:
            continue
        row_index = row_positions.get(defect_index)
        if row_index is None:
            continue
        row_elem = row_elements.get(row_index)
        if row_elem is None:
            continue

        try:
            current_height_points = float(row_elem.get("ht", default_row_height))
        except ValueError:
            current_height_points = default_row_height
        existing_height_px = _row_height_to_pixels(current_height_points)

        offset_px = 0.0
        required_height_px = existing_height_px
        for attachment_index, attachment in enumerate(attachments):
            width_px, height_px = _scale_image_dimensions(attachment.content, column_width_px)
            anchors.append(
                {
                    "row": row_index - 1,
                    "col": column_index - 1,
                    "row_offset_px": offset_px,
                    "width_px": width_px,
                    "height_px": height_px,
                    "attachment": attachment,
                }
            )
            offset_px += height_px
            required_height_px = max(required_height_px, offset_px)
            if attachment_index < len(attachments) - 1:
                offset_px += _IMAGE_VERTICAL_GAP_PX

        target_height_points = required_height_px * 72.0 / 96.0
        row_elem.set("ht", f"{target_height_points:.2f}")
        row_elem.set("customHeight", "1")

    return sheet_root, anchors, float(column_width_px)


def _update_content_types(
    xml_bytes: bytes, image_extensions: Iterable[str]
) -> bytes:
    root = ET.fromstring(xml_bytes)
    namespace = {"ct": _CONTENT_TYPES_NS}

    drawing_part = "/xl/drawings/drawing2.xml"
    found_drawing = False
    for override in root.findall("ct:Override", namespace):
        if override.get("PartName") == drawing_part:
            found_drawing = True
            break
    if not found_drawing:
        ET.SubElement(
            root,
            f"{{{_CONTENT_TYPES_NS}}}Override",
            {
                "PartName": drawing_part,
                "ContentType": "application/vnd.openxmlformats-officedocument.drawing+xml",
            },
        )

    existing_defaults = {
        default.get("Extension", "").lower(): default
        for default in root.findall("ct:Default", namespace)
    }

    for extension in image_extensions:
        if not extension:
            continue
        ext = extension.lower()
        if ext in existing_defaults:
            continue
        content_type = "image/png" if ext == "png" else "image/jpeg"
        ET.SubElement(
            root,
            f"{{{_CONTENT_TYPES_NS}}}Default",
            {"Extension": ext, "ContentType": content_type},
        )

    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def _inject_defect_images(
    workbook_bytes: bytes,
    sheet_bytes: bytes,
    row_positions: Dict[int, int],
    images_map: Mapping[int, Sequence[DefectReportImage]],
    column_letter: str,
) -> bytes:
    sheet_root = ET.fromstring(sheet_bytes)
    sheet_root, anchors, _ = _prepare_defect_image_anchors(
        sheet_root, row_positions, images_map, column_letter
    )

    if not anchors:
        updated_sheet = ET.tostring(sheet_root, encoding="utf-8", xml_declaration=True)
        return _replace_sheet_bytes(workbook_bytes, updated_sheet)

    updated_sheet = ET.tostring(sheet_root, encoding="utf-8", xml_declaration=True)

    source_buffer = io.BytesIO(workbook_bytes)
    with zipfile.ZipFile(source_buffer, "r") as source:
        sheet_rels_bytes = source.read("xl/worksheets/_rels/sheet1.xml.rels")
        content_types_bytes = source.read("[Content_Types].xml")

    rels_root = ET.fromstring(sheet_rels_bytes)
    existing_ids = []
    for rel in rels_root.findall(f"{{{_REL_NS}}}Relationship"):
        rel_id = rel.get("Id")
        if rel_id:
            existing_ids.append(rel_id)
    max_id = 0
    for rel_id in existing_ids:
        if rel_id.startswith("rId"):
            try:
                max_id = max(max_id, int(rel_id[3:]))
            except ValueError:
                continue
    sheet_rel_id = f"rId{max_id + 1}"
    ET.SubElement(
        rels_root,
        f"{{{_REL_NS}}}Relationship",
        {
            "Id": sheet_rel_id,
            "Type": "http://schemas.openxmlformats.org/officeDocument/2006/relationships/drawing",
            "Target": "../drawings/drawing2.xml",
        },
    )
    updated_rels = ET.tostring(rels_root, encoding="utf-8", xml_declaration=True)

    drawing_root = ET.Element(
        f"{{{_DRAWING_NS}}}wsDr",
        {"xmlns:xdr": _DRAWING_NS, "xmlns:a": _DRAWING_A_NS},
    )
    drawing_rels_root = ET.Element(f"{{{_REL_NS}}}Relationships")
    used_names: Dict[str, int] = {}
    image_entries: List[Tuple[str, bytes]] = []

    for index, anchor in enumerate(anchors, start=1):
        attachment = anchor["attachment"]
        filename = _normalized_image_filename(getattr(attachment, "file_name", ""), used_names)
        rel_id = f"rId{index}"
        image_entries.append((filename, attachment.content))

        anchor_elem = ET.SubElement(drawing_root, f"{{{_DRAWING_NS}}}oneCellAnchor")
        from_elem = ET.SubElement(anchor_elem, f"{{{_DRAWING_NS}}}from")
        ET.SubElement(from_elem, f"{{{_DRAWING_NS}}}col").text = str(int(anchor["col"]))
        ET.SubElement(from_elem, f"{{{_DRAWING_NS}}}colOff").text = "0"
        ET.SubElement(from_elem, f"{{{_DRAWING_NS}}}row").text = str(int(anchor["row"]))
        ET.SubElement(from_elem, f"{{{_DRAWING_NS}}}rowOff").text = str(
            _pixels_to_emu(float(anchor["row_offset_px"]))
        )

        ET.SubElement(
            anchor_elem,
            f"{{{_DRAWING_NS}}}ext",
            {
                "cx": str(_pixels_to_emu(float(anchor["width_px"]))),
                "cy": str(_pixels_to_emu(float(anchor["height_px"]))),
            },
        )

        pic = ET.SubElement(anchor_elem, f"{{{_DRAWING_NS}}}pic")
        nv_pic = ET.SubElement(pic, f"{{{_DRAWING_NS}}}nvPicPr")
        ET.SubElement(
            nv_pic,
            f"{{{_DRAWING_NS}}}cNvPr",
            {"id": str(index), "name": filename},
        )
        c_nv_pic_pr = ET.SubElement(nv_pic, f"{{{_DRAWING_NS}}}cNvPicPr")
        ET.SubElement(c_nv_pic_pr, f"{{{_DRAWING_A_NS}}}picLocks", {"noChangeAspect": "1"})

        blip_fill = ET.SubElement(pic, f"{{{_DRAWING_NS}}}blipFill")
        ET.SubElement(
            blip_fill,
            f"{{{_DRAWING_A_NS}}}blip",
            {f"{{{_REL_NS}}}embed": rel_id},
        )
        stretch = ET.SubElement(blip_fill, f"{{{_DRAWING_A_NS}}}stretch")
        ET.SubElement(stretch, f"{{{_DRAWING_A_NS}}}fillRect")

        sp_pr = ET.SubElement(pic, f"{{{_DRAWING_NS}}}spPr")
        ET.SubElement(sp_pr, f"{{{_DRAWING_A_NS}}}xfrm")
        prst_geom = ET.SubElement(sp_pr, f"{{{_DRAWING_A_NS}}}prstGeom", {"prst": "rect"})
        ET.SubElement(prst_geom, f"{{{_DRAWING_A_NS}}}avLst")

        ET.SubElement(anchor_elem, f"{{{_DRAWING_NS}}}clientData")

        ET.SubElement(
            drawing_rels_root,
            f"{{{_REL_NS}}}Relationship",
            {
                "Id": rel_id,
                "Type": "http://schemas.openxmlformats.org/officeDocument/2006/relationships/image",
                "Target": f"../media/{filename}",
            },
        )

    drawing_xml = ET.tostring(drawing_root, encoding="utf-8", xml_declaration=True)
    drawing_rels_xml = ET.tostring(
        drawing_rels_root, encoding="utf-8", xml_declaration=True
    )

    image_extensions = {filename.rsplit(".", 1)[-1].lower() for filename, _ in image_entries}
    updated_content_types = _update_content_types(content_types_bytes, image_extensions)

    # Add drawing reference to sheet xml
    drawing_elem = ET.Element(f"{{{_SPREADSHEET_NS}}}drawing")
    drawing_elem.set(f"{{{_REL_NS}}}id", sheet_rel_id)
    sheet_root.append(drawing_elem)
    final_sheet = ET.tostring(sheet_root, encoding="utf-8", xml_declaration=True)

    source_buffer.seek(0)
    output_buffer = io.BytesIO()
    with zipfile.ZipFile(source_buffer, "r") as source, zipfile.ZipFile(output_buffer, "w") as target:
        for info in source.infolist():
            data = source.read(info.filename)
            if info.filename == _XLSX_SHEET_PATH:
                data = final_sheet
            elif info.filename == "xl/worksheets/_rels/sheet1.xml.rels":
                data = updated_rels
            elif info.filename == "[Content_Types].xml":
                data = updated_content_types
            target.writestr(info, data)

        target.writestr("xl/drawings/drawing2.xml", drawing_xml)
        target.writestr("xl/drawings/_rels/drawing2.xml.rels", drawing_rels_xml)
        for filename, content in image_entries:
            target.writestr(f"xl/media/{filename}", content)

    return output_buffer.getvalue()
