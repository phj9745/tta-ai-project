# hybrid_excel.py  (고수준: openpyxl만 사용 + 패키지 자동 수리)
from __future__ import annotations

import csv
import io
import re
import zipfile
from dataclasses import dataclass
from typing import Dict, Iterable, List, Mapping, Sequence, Tuple, Optional

from openpyxl import load_workbook
from openpyxl.worksheet.worksheet import Worksheet
from openpyxl.drawing.image import Image as XLImage
from openpyxl.utils import get_column_letter

# 선택적(고급 앵커) 의존성: 없으면 자동 폴백
try:
    from openpyxl.drawing.spreadsheet_drawing import AnchorMarker, OneCellAnchor, XDRPositiveSize2D
    from openpyxl.utils.units import pixels_to_EMU
    _HAS_ONE_CELL_ANCHOR = True
except Exception:  # pragma: no cover
    AnchorMarker = OneCellAnchor = XDRPositiveSize2D = None  # type: ignore
    def pixels_to_EMU(px: float) -> int:  # type: ignore
        return int(round(px * 9525))  # EMU_PER_PIXEL
    _HAS_ONE_CELL_ANCHOR = False

# 외부 유틸(구현 의존 최소화)
try:
    from .utils import AI_CSV_DELIMITER  # CSV 구분자
except Exception:  # pragma: no cover
    AI_CSV_DELIMITER = ','

# --------------------- 데이터 구조 ---------------------
@dataclass(frozen=True)
class ColumnSpec:
    key: str
    letter: str
    style: str  # openpyxl에서는 템플릿 행의 셀 스타일 복사로 대체

@dataclass(frozen=True)
class DefectReportImage:
    file_name: str
    content: bytes
    content_type: Optional[str] = None


# --------------------- 유틸 ---------------------
def _safe_int(value: object) -> Optional[int]:
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
    # Excel UI의 '문자폭' 기준을 픽셀 근사로 환산
    if width <= 0:
        return 64
    return max(1, int(round(width * 7.0 + 5)))

def _row_height_to_pixels(height_points: float) -> float:
    if height_points <= 0:
        height_points = 15.0
    return height_points * 96.0 / 72.0

def _image_dimensions(content: bytes) -> Tuple[int, int]:
    # PNG
    if len(content) >= 24 and content.startswith(b"\x89PNG\r\n\x1a\n"):
        width = int.from_bytes(content[16:20], "big")
        height = int.from_bytes(content[20:24], "big")
        return width, height
    # JPEG
    if len(content) > 4 and content.startswith(b"\xff\xd8"):
        index = 2
        length = len(content)
        while index + 9 < length:
            if content[index] != 0xFF:
                break
            marker = content[index + 1]
            if marker == 0xD9:
                break
            if marker in {0xC0,0xC1,0xC2,0xC3,0xC5,0xC6,0xC7,0xC9,0xCA,0xCB,0xCD,0xCE,0xCF}:
                block_length = int.from_bytes(content[index+2:index+4], "big")
                start = index + 4
                if start + 5 < length:
                    height = int.from_bytes(content[start+1:start+3], "big")
                    width  = int.from_bytes(content[start+3:start+5], "big")
                    return width, height
                break
            block_length = int.from_bytes(content[index+2:index+4], "big")
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

def _column_to_index(letter: str) -> int:
    result = 0
    for ch in letter:
        if not ch.isalpha():
            break
        result = result * 26 + (ord(ch.upper()) - ord("A") + 1)
    return result

def _index_to_column(index: int) -> str:
    if index <= 0:
        index = 1
    letters: List[str] = []
    while index:
        index, remainder = divmod(index - 1, 26)
        letters.append(chr(ord("A") + remainder))
    return "".join(reversed(letters)) or "A"

def _split_cell(reference: str) -> tuple[str, int]:
    m = re.match(r"([A-Z]+)(\d+)", reference)
    if not m:
        raise ValueError(f"셀 참조를 해석할 수 없습니다: {reference}")
    col, row = m.groups()
    return col, int(row)

def _sanitize_xml_text(value: str) -> str:
    def ok(cp: int) -> bool:
        return (
            cp in {0x9, 0xA, 0xD} or
            0x20 <= cp <= 0xD7FF or
            0xE000 <= cp <= 0xFFFD or
            0x10000 <= cp <= 0x10FFFF
        )
    return "".join(ch for ch in value if ok(ord(ch)))


# --------------------- CSV 정규화/헤더 매칭 ---------------------
def _normalize_header_token(value: str) -> str:
    cleaned = str(value or "").strip().lower()
    if not cleaned:
        return ""
    cleaned = cleaned.lstrip("\ufeff")
    cleaned = re.sub(r"[\s\u00a0]+", "", cleaned)
    cleaned = re.sub(r"[()\[\]{}<>]+", "", cleaned)
    cleaned = cleaned.replace("-", "").replace("_", "")
    return cleaned

def _parse_csv_records(csv_text: str, expected_columns: Sequence[str]) -> List[Dict[str, str]]:
    stripped = (csv_text or "").strip()
    if not stripped:
        return []
    reader = csv.reader(io.StringIO(stripped), delimiter=AI_CSV_DELIMITER)
    rows = [row for row in reader]
    if not rows:
        return []
    header = [cell.strip() for cell in rows[0]]
    if header:
        header[0] = header[0].lstrip("\ufeff")

    column_index: Dict[str, int] = {}
    normalized_lookup: Dict[str, str] = {}
    for col in expected_columns:
        normalized = _normalize_header_token(col)
        if normalized and normalized not in normalized_lookup:
            normalized_lookup[normalized] = col

    for idx, name in enumerate(header):
        if not name:
            continue
        column_index.setdefault(name, idx)
        normalized = _normalize_header_token(name)
        canonical = normalized_lookup.get(normalized)
        if canonical:
            column_index.setdefault(canonical, idx)

    missing = [c for c in expected_columns if c not in column_index]
    if missing:
        raise ValueError(f"CSV에 필요한 열이 없습니다: {', '.join(missing)}")

    records: List[Dict[str, str]] = []
    for raw in rows[1:]:
        entry: Dict[str, str] = {}
        is_empty = True
        for col in expected_columns:
            i = column_index[col]
            value = raw[i].strip() if i < len(raw) else ""
            if value:
                is_empty = False
            entry[col] = value
        if not is_empty:
            records.append(entry)
    return records


# --------- 기능리스트 CSV 헤더 별칭/정규화 ---------
_FEATURE_LIST_START_ROW = 8

_FEATURE_LIST_HEADER_ALIASES: Mapping[str, Tuple[str, ...]] = {
    "대분류": ("대분류", "대 분류", "상위 기능", "상위기능"),
    "중분류": ("중분류", "중 분류", "중간 기능", "중간기능"),
    "소분류": ("소분류", "소 분류", "세부 기능", "세부기능"),
    "기능 설명": (
        "기능 설명", "상세 설명", "상세 내용", "기능 상세",
        "상세내용", "상세설명", "기능상세", "내용",
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

def match_feature_list_header(value: str) -> Optional[str]:
    normalized = _normalize_feature_header_token(value)
    if not normalized:
        return None
    return _FEATURE_LIST_NORMALIZED_HEADERS.get(normalized)

FEATURE_LIST_COLUMNS: Sequence[ColumnSpec] = (
    ColumnSpec(key="대분류", letter="A", style="12"),
    ColumnSpec(key="중분류", letter="B", style="8"),
    ColumnSpec(key="소분류", letter="C", style="15"),
    ColumnSpec(key="기능 설명", letter="D", style="7"),
)
FEATURE_LIST_EXPECTED_HEADERS: Sequence[str] = ["대분류", "중분류", "소분류", "기능 설명"]

def _normalize_feature_list_records(csv_text: str) -> List[Dict[str, str]]:
    stripped = (csv_text or "").strip()
    if not stripped:
        return []
    reader = csv.reader(io.StringIO(stripped), delimiter=AI_CSV_DELIMITER)
    rows = [row for row in reader if any(cell.strip() for cell in row)]
    if not rows:
        return []
    header = [cell.strip() for cell in rows[0]]
    if header:
        header[0] = header[0].lstrip("\ufeff")

    column_map: Dict[str, int] = {}
    overview_index: Optional[int] = None
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
    return _normalize_feature_list_records(csv_text)


# --------------------- 개요 셀 위치/값 추출 (openpyxl 기반) ---------------------
def _find_overview_cell_ref_openpyxl(ws: Worksheet, feature_start_row: int) -> Optional[str]:
    """
    상단(=feature_start_row 이전)의 영역에서 “개요/기능 개요” 헤더를 찾고,
    그 헤더와 같은 열의 바로 아래(또는 동일 열 범위의 다음 병합셀) 첫 셀 주소를 반환.
    """
    targets = {"개요", "프로젝트개요", "기능 개요"}
    merged_ranges = list(ws.merged_cells.ranges)  # e.g., [CellRange A1:D1, ...]

    def _merged_of(r: int, c: int):
        for rng in merged_ranges:
            if rng.min_row <= r <= rng.max_row and rng.min_col <= c <= rng.max_col:
                return rng
        return None

    max_col = ws.max_column or 1
    for r in range(1, max(1, feature_start_row)):
        for c in range(1, max_col + 1):
            v = ws.cell(r, c).value
            if not v:
                continue
            txt = str(v).strip()
            hit = match_feature_list_header(txt) or ""
            token = _normalize_feature_header_token(txt)
            if token not in {"개요", "프로젝트개요"} and hit != "기능 개요":
                continue

            rng = _merged_of(r, c)
            base_col_min = rng.min_col if rng else c
            base_col_max = rng.max_col if rng else c
            base_row = (rng.max_row if rng else r) + 1  # 헤더 바로 아래

            # 같은 열 범위의 다음 병합블록(최대 6행 이내)을 우선 사용
            for nxt in merged_ranges:
                same_cols = (nxt.min_col == base_col_min) and (nxt.max_col == base_col_max)
                if same_cols and base_row <= nxt.min_row <= base_row + 6:
                    return f"{_index_to_column(nxt.min_col)}{nxt.min_row}"
            return f"{_index_to_column(base_col_min)}{base_row}"
    return None

def extract_feature_list_overview(workbook_bytes: bytes) -> Tuple[Optional[str], str]:
    wb = load_workbook(io.BytesIO(workbook_bytes))
    ws = wb.worksheets[0]
    feature_start_row = globals().get("_FEATURE_LIST_START_ROW", 8)
    ref = _find_overview_cell_ref_openpyxl(ws, feature_start_row)
    if ref:
        val = str(ws[ref].value or "").strip()
        return ref, val
    return None, ""


# --------------------- 패키지 수리(Windows Excel 호환 보정) ---------------------
_CT_NS = "http://schemas.openxmlformats.org/package/2006/content-types"
_S_NS  = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
_R_NS  = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
_PKG_RELS_NS = "http://schemas.openxmlformats.org/package/2006/relationships" 
_BAD_XML_CHARS = re.compile(r"[\x00-\x08\x0B\x0C\x0E-\x1F]")

def _clean_invalid_xml_bytes(data: bytes) -> bytes:
    try:
        s = data.decode("utf-8")
    except Exception:
        return data
    s2 = _BAD_XML_CHARS.sub("", s)
    return s2.encode("utf-8")

def _repair_content_types(ct_bytes: bytes, names_in_pkg: set[str]) -> bytes:
    import xml.etree.ElementTree as ET
    try:
        root = ET.fromstring(ct_bytes)
    except ET.ParseError:
        return ct_bytes

    changed = False
    names = set(names_in_pkg)
    names_with_slash = {"/" + n for n in names_in_pkg}

    # 정식 sheet metadata 컨텐트 타입
    VALID_SHEET_METADATA_CT = (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheetMetadata+xml"
    )

    def _is_override(elem: ET.Element) -> bool:
        tag = elem.tag
        return tag == "Override" or tag.endswith("}Override")

    for node in list(root):
        if not _is_override(node):
            continue

        part = (node.get("PartName") or "").strip()          # "/xl/metadata" 등
        ctype = (node.get("ContentType") or "").strip()
        norm = part[1:] if part.startswith("/") else part     # "xl/metadata"

        # 1) metadata 오버라이드는 '정상 CT'가 아니면 무조건 제거
        if norm in ("xl/metadata", "xl/metadata.xml"):
            # 파일이 있든 없든, CT가 정상이 아니면 제거
            if ctype != VALID_SHEET_METADATA_CT:
                root.remove(node); changed = True
                continue
            # CT가 정상이어도 실제 파일이 없으면 제거
            if ("xl/metadata.xml" not in names) and ("xl/metadata" not in names):
                root.remove(node); changed = True
                continue

        # 2) 존재하지 않는 파트를 광고하면 제거
        if (norm not in names) and (part not in names_with_slash):
            root.remove(node); changed = True

    return ET.tostring(root, encoding="utf-8", xml_declaration=True) if changed else ct_bytes


def _ensure_drawing_link(sheet_bytes: bytes, rels_bytes: Optional[bytes]) -> Tuple[bytes, Optional[bytes]]:
    """
    sheet1.xml.rels(=package ns) 안에 drawing 관계가 있는데 sheet 본문에 <drawing r:id="..."/> 가 없으면 삽입.
    반대로 본문에 있는데 rels가 없으면 rels 생성.
    """
    import xml.etree.ElementTree as ET
    try:
        s_root = ET.fromstring(sheet_bytes)
    except ET.ParseError:
        return sheet_bytes, rels_bytes

    # 1) .rels 파싱 (package ns)
    r_root = None
    if rels_bytes:
        try:
            r_root = ET.fromstring(rels_bytes)
        except ET.ParseError:
            r_root = None

    drawing_rel_ids: List[str] = []
    if r_root is not None:
        for rel in r_root.findall(f"{{{_PKG_RELS_NS}}}Relationship"):
            if rel.get("Type") == "http://schemas.openxmlformats.org/officeDocument/2006/relationships/drawing":
                rid = rel.get("Id")
                if rid:
                    drawing_rel_ids.append(rid)

    ns = {"s": _S_NS, "r": _R_NS}
    has_drawing_elem = s_root.find("s:drawing", ns) is not None

    changed_sheet = False
    changed_rels  = False

    # 본문에 없고 rels에 있으면: 첫 rId로 삽입(위치는 sheetData 뒤에 두는 보수적 전략)
    if not has_drawing_elem and drawing_rel_ids:
        sd = s_root.find("s:sheetData", ns)
        drawing = ET.Element(f"{{{_S_NS}}}drawing")
        drawing.set(f"{{{_R_NS}}}id", drawing_rel_ids[0])  # r:id
        if sd is not None:
            idx = list(s_root).index(sd)
            s_root.insert(idx + 1, drawing)
        else:
            s_root.append(drawing)
        changed_sheet = True

    # 본문에 있는데 rels가 없으면: rId 신규 발급하고 rels 생성(package ns)
    if has_drawing_elem and not drawing_rel_ids:
        if r_root is None:
            r_root = ET.Element("Relationships", {"xmlns": _PKG_RELS_NS})

        # 새 rId
        exists_ids = []
        for rel in r_root.findall(f"{{{_PKG_RELS_NS}}}Relationship"):
            rid = rel.get("Id")
            if rid and rid.startswith("rId"):
                exists_ids.append(rid)
        max_id = 0
        for rid in exists_ids:
            try:
                max_id = max(max_id, int(rid[3:]))
            except Exception:
                pass
        new_id = f"rId{max_id + 1}"

        # 관계 추가 (package ns)
        ET.SubElement(
            r_root,
            f"{{{_PKG_RELS_NS}}}Relationship",
            {
                "Id": new_id,
                "Type": "http://schemas.openxmlformats.org/officeDocument/2006/relationships/drawing",
                "Target": "../drawings/drawing1.xml",
            },
        )
        # sheet 본문 r:id 갱신
        dnode = s_root.find("s:drawing", ns)
        if dnode is not None:
            dnode.set(f"{{{_R_NS}}}id", new_id)
        changed_sheet = True
        changed_rels  = True

    new_sheet = (ET.tostring(s_root, encoding="utf-8", xml_declaration=True)
                 if changed_sheet else sheet_bytes)
    new_rels  = (ET.tostring(r_root, encoding="utf-8", xml_declaration=True)
                 if (changed_rels and r_root is not None) else rels_bytes)
    return new_sheet, new_rels

def _ensure_dimension_first(sheet_bytes: bytes) -> bytes:
    import xml.etree.ElementTree as ET
    try:
        root = ET.fromstring(sheet_bytes)
    except ET.ParseError:
        return sheet_bytes

    ns = {"s": _S_NS}
    dim = root.find("s:dimension", ns)
    sd  = root.find("s:sheetData", ns)
    if dim is None or sd is None:
        return sheet_bytes  # 보정 불필요

    # 현재 위치가 sheetData 뒤라면 sheetData 앞(가능하면 cols 뒤)에 재배치
    children = list(root)
    try:
        i_dim = children.index(dim)
        i_sd  = children.index(sd)
    except ValueError:
        return sheet_bytes

    if i_dim > i_sd:
        # 우선 제거
        root.remove(dim)
        # cols가 있으면 그 뒤, 없으면 sheetViews/sheetFormatPr 뒤, 전부 없으면 맨 앞
        insert_idx = 0
        pref_order = ["cols", "sheetFormatPr", "sheetViews"]
        for tag in pref_order:
            node = root.find(f"s:{tag}", ns)
            if node is not None:
                insert_idx = list(root).index(node) + 1
        root.insert(insert_idx, dim)
        return ET.tostring(root, encoding="utf-8", xml_declaration=True)
    return sheet_bytes


def _repair_package(xlsx_bytes: bytes) -> bytes:
    """
    - [Content_Types].xml에서 잘못된 /xl/metadata Override 제거
    - sheet1.xml의 dimension 위치 보정
    - sheet1.xml/rel 간 drawing 연결 일관화
    - sheet1.xml / sharedStrings.xml 에 남은 금지 제어문자 제거
    """
    try:
        bio = io.BytesIO(xlsx_bytes)
        if not zipfile.is_zipfile(bio):
            return xlsx_bytes
        bio.seek(0)
        with zipfile.ZipFile(bio, "r") as zin:
            names = {i.filename for i in zin.infolist()}
            files: Dict[str, bytes] = {i.filename: zin.read(i.filename) for i in zin.infolist()}

        # 1) Content_Types 정리
        if "[Content_Types].xml" in files:
            files["[Content_Types].xml"] = _repair_content_types(files["[Content_Types].xml"], names)

        # 2) 금지 제어문자 제거
        if "xl/worksheets/sheet1.xml" in files:
            files["xl/worksheets/sheet1.xml"] = _clean_invalid_xml_bytes(files["xl/worksheets/sheet1.xml"])
        if "xl/sharedStrings.xml" in files:
            files["xl/sharedStrings.xml"] = _clean_invalid_xml_bytes(files["xl/sharedStrings.xml"])

        # 3) sheet1.xml 구조 보정
        if "xl/worksheets/sheet1.xml" in files:
            files["xl/worksheets/sheet1.xml"] = _ensure_dimension_first(files["xl/worksheets/sheet1.xml"])

            rels_name = "xl/worksheets/_rels/sheet1.xml.rels"
            rels_bytes = files.get(rels_name)
            new_sheet, new_rels = _ensure_drawing_link(files["xl/worksheets/sheet1.xml"], rels_bytes)
            files["xl/worksheets/sheet1.xml"] = new_sheet
            if new_rels is not None:
                files[rels_name] = new_rels

        # 4) 다시 ZIP 작성
        out = io.BytesIO()
        with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as zout:
            for name, data in files.items():
                zout.writestr(name, data)
        return out.getvalue()

    except Exception:
        # 수리 실패해도 원본 반환(방어)
        return xlsx_bytes


# --------------------- openpyxl 작성기 ---------------------
def _copy_style_from_template(ws: Worksheet, template_row: int, target_row: int, columns: Sequence[ColumnSpec]) -> None:
    for spec in columns:
        src = ws[f"{spec.letter}{template_row}"]
        dst = ws[f"{spec.letter}{target_row}"]
        dst.font = src.font
        dst.fill = src.fill
        dst.border = src.border
        dst.alignment = src.alignment
        dst.number_format = src.number_format
        dst.protection = src.protection

def _clear_region(ws: Worksheet, start_row: int, end_row: int, columns: Sequence[ColumnSpec]) -> None:
    for r in range(start_row, end_row + 1):
        for spec in columns:
            ws[f"{spec.letter}{r}"].value = None  # 값만 정리(스타일 유지)

def _set_row_values(ws: Worksheet, row_index: int, record: Dict[str, str], columns: Sequence[ColumnSpec]) -> None:
    for spec in columns:
        raw = record.get(spec.key, "")
        ws[f"{spec.letter}{row_index}"].value = _sanitize_xml_text(str(raw or ""))

def _wb_to_bytes(wb) -> bytes:
    bio = io.BytesIO()
    wb.save(bio)
    # 저장 직후 Windows Excel 호환 수리 수행
    return _repair_package(bio.getvalue())


# --------------------- 공개 API: 표 채우기 ---------------------
def populate_feature_list(workbook_bytes: bytes, csv_text: str, project_overview: Optional[str] = None) -> bytes:
    records = _normalize_feature_list_records(csv_text)

    wb = load_workbook(io.BytesIO(workbook_bytes))
    ws = wb.worksheets[0]  # sheet1
    start_row = _FEATURE_LIST_START_ROW
    last_template_row = max(ws.max_row, start_row)

    _clear_region(ws, start_row, last_template_row, FEATURE_LIST_COLUMNS)

    for i, rec in enumerate(records, start=start_row):
        _copy_style_from_template(ws, start_row, i, FEATURE_LIST_COLUMNS)
        _set_row_values(ws, i, rec, FEATURE_LIST_COLUMNS)

    end_row = start_row + len(records)
    if end_row <= last_template_row:
        _clear_region(ws, end_row, last_template_row, FEATURE_LIST_COLUMNS)

    if project_overview is not None:
        overview_ref = _find_overview_cell_ref_openpyxl(ws, start_row)
        if overview_ref:
            ws[overview_ref].value = _sanitize_xml_text(project_overview)

    return _wb_to_bytes(wb)


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
    "대분류","중분류","소분류","테스트 케이스 ID","테스트 시나리오",
    "입력(사전조건 포함)","기대 출력(사후조건 포함)","테스트 결과","상세 테스트 결과","비고",
]

def populate_testcase_list(workbook_bytes: bytes, csv_text: str) -> bytes:
    records = _parse_csv_records(csv_text, TESTCASE_EXPECTED_HEADERS)
    wb = load_workbook(io.BytesIO(workbook_bytes))
    ws = wb.worksheets[0]
    start_row = 6
    last_template_row = max(ws.max_row, start_row)

    _clear_region(ws, start_row, last_template_row, TESTCASE_COLUMNS)

    for i, rec in enumerate(records, start=start_row):
        _copy_style_from_template(ws, start_row, i, TESTCASE_COLUMNS)
        _set_row_values(ws, i, rec, TESTCASE_COLUMNS)

    end_row = start_row + len(records)
    if end_row <= last_template_row:
        _clear_region(ws, end_row, last_template_row, TESTCASE_COLUMNS)

    return _wb_to_bytes(wb)


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
    "순번","시험환경(OS)","결함요약","결함정도","발생빈도",
    "품질특성","결함 설명","업체 응답","수정여부","비고",
]
SECURITY_REPORT_EXPECTED_HEADERS: Sequence[str] = [
    "순번","시험환경 OS","결함 요약","결함 정도","발생 빈도",
    "품질 특성","결함 설명","업체 응답","수정여부","비고","매핑 유형",
]

def populate_defect_report(
    workbook_bytes: bytes,
    csv_text: str,
    *,
    images: Mapping[int, Sequence[DefectReportImage]] | None = None,
    attachment_notes: Mapping[int, Sequence[str]] | None = None,
) -> bytes:
    records = _parse_csv_records(csv_text, DEFECT_REPORT_EXPECTED_HEADERS)

    # 순번 -> 행 위치 & 비고(첨부) 주입
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

    wb = load_workbook(io.BytesIO(workbook_bytes))
    ws = wb.worksheets[0]
    last_template_row = max(ws.max_row, start_row)
    _clear_region(ws, start_row, last_template_row, DEFECT_REPORT_COLUMNS)

    for i, rec in enumerate(normalized_records, start=start_row):
        _copy_style_from_template(ws, start_row, i, DEFECT_REPORT_COLUMNS)
        _set_row_values(ws, i, rec, DEFECT_REPORT_COLUMNS)

    end_row = start_row + len(normalized_records)
    if end_row <= last_template_row:
        _clear_region(ws, end_row, last_template_row, DEFECT_REPORT_COLUMNS)

    if images:
        _place_defect_images_openpyxl(
            ws,
            row_positions=row_positions,
            images_map=images,
            column_letter="J",
            vertical_gap_px=4,
        )

    return _wb_to_bytes(wb)


def populate_security_report(workbook_bytes: bytes, csv_text: str) -> bytes:
    records = _parse_csv_records(csv_text, SECURITY_REPORT_EXPECTED_HEADERS)
    # 보안 리포트 -> 일반 결함 리포트 포맷으로 열 매핑
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=AI_CSV_DELIMITER)
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


# --------------------- 이미지 배치 (고수준) ---------------------
def _get_column_width_px(ws: Worksheet, col_idx: int) -> int:
    width = None
    dim = ws.column_dimensions.get(get_column_letter(col_idx))
    if dim and dim.width:
        try:
            width = float(dim.width)
        except Exception:
            width = None
    if width is None:
        width = 8.43  # Excel 기본값
    return max(1, _column_width_to_pixels(width))

def _place_defect_images_openpyxl(
    ws: Worksheet,
    *,
    row_positions: Dict[int, int],
    images_map: Mapping[int, Sequence[DefectReportImage]],
    column_letter: str = "J",
    vertical_gap_px: int = 4,
) -> None:
    col_idx = _column_to_index(column_letter)
    first_col_width_px = _get_column_width_px(ws, col_idx)

    for defect_idx, attachments in images_map.items():
        if not attachments:
            continue
        row = row_positions.get(defect_idx)
        if not row:
            continue

        # 크기 스케일링 및 총 높이 계산
        sized_imgs: List[Tuple[XLImage, int, int, str]] = []
        total_h_px = 0
        for i, att in enumerate(attachments):
            w_px, h_px = _scale_image_dimensions(att.content, first_col_width_px)
            img = XLImage(io.BytesIO(att.content))
            img.width, img.height = w_px, h_px
            sized_imgs.append((img, w_px, h_px, att.file_name))
            total_h_px += h_px
            if i < len(attachments) - 1:
                total_h_px += vertical_gap_px

        # 1) 시도: OneCellAnchor(rowOff)로 같은 셀 안 세로 스택
        if _HAS_ONE_CELL_ANCHOR:
            try:
                # 행 높이: 전체 이미지 높이에 맞춰 포인트로 설정
                ws.row_dimensions[row].height = total_h_px * 72.0 / 96.0
                offset_px = 0
                for img, w_px, h_px, _fn in sized_imgs:
                    marker = AnchorMarker(
                        col=col_idx - 1,
                        colOff=pixels_to_EMU(0),
                        row=row - 1,
                        rowOff=pixels_to_EMU(offset_px),
                    )
                    ext = XDRPositiveSize2D(pixels_to_EMU(w_px), pixels_to_EMU(h_px))
                    img.anchor = OneCellAnchor(_from=marker, ext=ext)  # type: ignore
                    ws.add_image(img)
                    offset_px += h_px + vertical_gap_px
                continue  # 다음 결함으로
            except Exception:  # 폴백 경로로 이동
                pass

        # 2) 폴백: 같은 행의 이웃 열(J, K, L, ...)에 수평 분산
        #    - 겹침 회피, 다른 행을 침범하지 않음
        #    - 열 너비는 첫 열(QoL)과 동일하게 맞춤
        max_h_px = 0
        for j, (img, w_px, h_px, _fn) in enumerate(sized_imgs):
            target_col_idx = col_idx + j
            letter = _index_to_column(target_col_idx)
            # 가독성을 위해 열 너비를 동일하게 맞춤(선택)
            ws.column_dimensions[letter].width = ws.column_dimensions[get_column_letter(col_idx)].width or 8.43
            ws.add_image(img, f"{letter}{row}")
            max_h_px = max(max_h_px, h_px)
        ws.row_dimensions[row].height = max_h_px * 72.0 / 96.0
