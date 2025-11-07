from __future__ import annotations

import base64
import importlib.util
import io
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

# Ensure the backend/app package is importable when running tests from the repository root.
BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.excel_templates import (
    DEFECT_REPORT_EXPECTED_HEADERS,
    FEATURE_LIST_EXPECTED_HEADERS,
    SECURITY_REPORT_EXPECTED_HEADERS,
    TESTCASE_EXPECTED_HEADERS,
    DefectReportImage,
    extract_feature_list_overview,
    populate_defect_report,
    populate_feature_list,
    populate_security_report,
    populate_testcase_list,
)
from app.services.excel_templates.defect_report import (
    DefectReportImage as modern_DefectReportImage,
    _inject_defect_images as modern_inject_defect_images,
)
from app.services.excel_templates.security_report import _extract_existing_rows

_SPREADSHEET_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
_REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
_RELATIONSHIPS_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
_DUMMY_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAACklEQVR42mP8/5+hHgAHggJ/P0BkhQAAAABJRU5ErkJggg=="
)
import app.services.excel_templates.utils as modern_utils
sys.modules.setdefault("app.services.utils", modern_utils)
_LEGACY_SPEC = importlib.util.spec_from_file_location(
    "app.services._legacy_excel_templates",
    BACKEND_ROOT / "app/services/excel_templates.py",
)
assert _LEGACY_SPEC and _LEGACY_SPEC.loader is not None
legacy_module = importlib.util.module_from_spec(_LEGACY_SPEC)
sys.modules[_LEGACY_SPEC.name] = legacy_module
_LEGACY_SPEC.loader.exec_module(legacy_module)
legacy_inject_defect_images = legacy_module._inject_defect_images
legacy_DefectReportImage = legacy_module.DefectReportImage


def _load_sheet(workbook_bytes: bytes) -> ET.Element:
    with zipfile.ZipFile(io.BytesIO(workbook_bytes), "r") as zf:
        data = zf.read("xl/worksheets/sheet1.xml")
    return ET.fromstring(data)


def _build_test_workbook(*, include_drawing: bool, include_legacy: bool) -> tuple[bytes, bytes]:
    page_margins = '<pageMargins left="0" right="0" top="0" bottom="0"/>'
    sheet_parts = [
        "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>",
        "<worksheet xmlns=\"http://schemas.openxmlformats.org/spreadsheetml/2006/main\"",
        "           xmlns:r=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships\">",
        "  <sheetData>",
        "    <row r=\"6\" ht=\"15\"/>",
        "  </sheetData>",
        f"  {page_margins}",
    ]

    rel_entries: list[str] = []

    if include_drawing:
        sheet_parts.append('  <drawing r:id="rId1"/>')
        rel_entries.append(
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/drawing" '
            'Target="../drawings/drawing1.xml"/>'
        )

    if include_legacy:
        legacy_rel_id = "rId2" if include_drawing else "rId1"
        sheet_parts.append(f'  <legacyDrawing r:id="{legacy_rel_id}"/>')
        rel_entries.append(
            f'<Relationship Id="{legacy_rel_id}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/vmlDrawing" '
            'Target="../drawings/vmlDrawing1.vml"/>'
        )

    sheet_parts.append("</worksheet>")
    sheet_xml = "\n".join(sheet_parts)

    rels_lines = [
        "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>",
        f"<Relationships xmlns=\"{_RELATIONSHIPS_NS}\">",
        *rel_entries,
        "</Relationships>",
    ]
    sheet_rels_xml = "\n".join(rels_lines)

    content_types_xml = """<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>
<Types xmlns=\"http://schemas.openxmlformats.org/package/2006/content-types\">
  <Default Extension=\"rels\" ContentType=\"application/vnd.openxmlformats-package.relationships+xml\"/>
  <Default Extension=\"xml\" ContentType=\"application/xml\"/>
  <Override PartName=\"/xl/worksheets/sheet1.xml\" ContentType=\"application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml\"/>
</Types>
"""

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        zf.writestr("[Content_Types].xml", content_types_xml)
        zf.writestr("xl/worksheets/sheet1.xml", sheet_xml)
        zf.writestr("xl/worksheets/_rels/sheet1.xml.rels", sheet_rels_xml)

    return buffer.getvalue(), sheet_xml.encode("utf-8")


def _cell_text(root: ET.Element, ref: str) -> str | None:
    ns = {"s": _SPREADSHEET_NS}
    column = "".join(filter(str.isalpha, ref))
    row_index = "".join(filter(str.isdigit, ref))
    row = root.find(f"s:sheetData/s:row[@r='{row_index}']", ns)
    if row is None:
        return None
    for cell in row.findall("s:c", ns):
        if cell.get("r") != ref:
            continue
        is_elem = cell.find("s:is", ns)
        if is_elem is None:
            return None
        text_elem = is_elem.find("s:t", ns)
        return text_elem.text if text_elem is not None else ""
    return None


def test_populate_feature_list_inserts_rows() -> None:
    template_path = Path("backend/template/가.계획/GS-B-XX-XXXX 기능리스트 v1.0.xlsx")
    template_bytes = template_path.read_bytes()

    csv_text = "\n".join(
        [
            "|".join(FEATURE_LIST_EXPECTED_HEADERS),
            "대1|중1|소1|상세 설명1",
            "대2|중2|소2|상세 설명2",
        ]
    )

    updated = populate_feature_list(template_bytes, csv_text)
    root = _load_sheet(updated)

    assert _cell_text(root, "A8") == "대1"
    assert _cell_text(root, "B8") == "중1"
    assert _cell_text(root, "C8") == "소1"
    assert _cell_text(root, "D8") == "상세 설명1"
    assert _cell_text(root, "A9") == "대2"
    assert _cell_text(root, "B9") == "중2"
    assert _cell_text(root, "C9") == "소2"
    assert _cell_text(root, "D9") == "상세 설명2"
    assert _cell_text(root, "A10") is None


def test_populate_feature_list_sets_project_overview() -> None:
    template_path = Path("backend/template/가.계획/GS-B-XX-XXXX 기능리스트 v1.0.xlsx")
    template_bytes = template_path.read_bytes()

    csv_text = "\n".join(
        [
            "|".join(FEATURE_LIST_EXPECTED_HEADERS),
            "대1|중1|소1|기능 상세",
        ]
    )

    overview_text = "이 프로젝트는 신규 인증 기능을 제공합니다."
    updated = populate_feature_list(template_bytes, csv_text, project_overview=overview_text)
    root = _load_sheet(updated)

    ref, value = extract_feature_list_overview(updated)
    assert ref is not None
    assert value == overview_text
    assert _cell_text(root, ref) == overview_text


def test_populate_testcase_list_maps_columns() -> None:
    template_path = Path("backend/template/나.설계/GS-B-XX-XXXX 테스트케이스.xlsx")
    template_bytes = template_path.read_bytes()

    csv_header = "|".join(TESTCASE_EXPECTED_HEADERS)
    csv_row = "|".join(
        [
            "대분류A",
            "중분류B",
            "소분류C",
            "TC-001",
            "시나리오 설명",
            "입력 데이터",
            "기대 결과",
            "미실행",
            "",
            "비고 메모",
        ]
    )
    csv_text = f"{csv_header}\n{csv_row}"

    updated = populate_testcase_list(template_bytes, csv_text)
    root = _load_sheet(updated)

    assert _cell_text(root, "A6") == "대분류A"
    assert _cell_text(root, "B6") == "중분류B"
    assert _cell_text(root, "C6") == "소분류C"
    assert _cell_text(root, "D6") == "TC-001"
    assert _cell_text(root, "E6") == "시나리오 설명"
    assert _cell_text(root, "F6") == "입력 데이터"
    assert _cell_text(root, "G6") == "기대 결과"
    assert _cell_text(root, "H6") == "미실행"
    assert _cell_text(root, "I6") is None
    assert _cell_text(root, "J6") == "비고 메모"


def test_populate_testcase_list_validates_headers() -> None:
    template_path = Path("backend/template/나.설계/GS-B-XX-XXXX 테스트케이스.xlsx")
    template_bytes = template_path.read_bytes()

    csv_text = "대분류|중분류\nA|B"

    with pytest.raises(ValueError):
        populate_testcase_list(template_bytes, csv_text)


def test_populate_security_report_fills_rows() -> None:
    template_path = Path("backend/template/다.수행/GS-B-2X-XXXX 결함리포트 v1.0.xlsx")
    template_bytes = template_path.read_bytes()

    csv_header = "|".join(
        SECURITY_REPORT_EXPECTED_HEADERS
        + ["Invicti 결과", "위험도", "발생경로", "조치 가이드", "원본 세부내용", "매핑 유형"]
    )
    csv_row = "|".join(
        [
            "1",
            "시험환경 모든 OS",
            "요약",
            "H",
            "A",
            "보안성",
            "상세 설명",
            "",
            "",
            "비고",
            "SQL Injection",
            "High",
            "/login",
            "가이드",
            "세부",
            "기준표 매칭",
        ]
    )
    csv_text = f"{csv_header}\n{csv_row}"

    existing_rows = _extract_existing_rows(template_bytes)
    updated = populate_security_report(template_bytes, csv_text)
    root = _load_sheet(updated)

    start_row = 6
    target_row = start_row + len(existing_rows)
    expected_order = str(len(existing_rows) + 1)
    assert _cell_text(root, f"A{target_row}") == expected_order
    assert _cell_text(root, f"B{target_row}") == "시험환경 모든 OS"
    assert _cell_text(root, f"C{target_row}") == "요약"
    assert _cell_text(root, f"D{target_row}") == "H"
    assert _cell_text(root, f"E{target_row}") == "A"
    assert _cell_text(root, f"G{target_row}") == "상세 설명"
    assert _cell_text(root, f"J{target_row}") == "비고"


def test_populate_security_report_appends_existing_rows() -> None:
    template_path = Path("backend/template/다.수행/GS-B-2X-XXXX 결함리포트 v1.0.xlsx")
    template_bytes = template_path.read_bytes()

    defect_header = "|".join(DEFECT_REPORT_EXPECTED_HEADERS)
    defect_row = "|".join(
        [
            "1",
            "시험환경 모든 OS",
            "기존 결함 요약",
            "M",
            "I",
            "보안성",
            "기존 결함 설명",
            "",
            "",
            "기존 비고",
        ]
    )
    existing_csv = f"{defect_header}\n{defect_row}"
    existing_bytes = populate_defect_report(template_bytes, existing_csv)

    security_header = "|".join(
        SECURITY_REPORT_EXPECTED_HEADERS
        + ["Invicti 결과", "위험도", "발생경로", "조치 가이드", "원본 세부내용", "매핑 유형"]
    )
    security_row = "|".join(
        [
            "",
            "",
            "신규 결함 요약",
            "H",
            "A",
            "보안성",
            "신규 결함 설명",
            "",
            "",
            "신규 비고",
            "SQL Injection",
            "High",
            "/login",
            "가이드",
            "세부",
            "기준표 매칭",
        ]
    )
    security_csv = f"{security_header}\n{security_row}"

    updated = populate_security_report(existing_bytes, security_csv)
    root = _load_sheet(updated)

    assert _cell_text(root, "A6") == "1"
    assert _cell_text(root, "C6") == "기존 결함 요약"
    assert _cell_text(root, "A7") == "2"
    assert _cell_text(root, "C7") == "신규 결함 요약"
    assert _cell_text(root, "J7") == "신규 비고"


def test_populate_defect_report_injects_images_with_relationship_namespace() -> None:
    template_path = Path("backend/template/다.수행/GS-B-2X-XXXX 결함리포트 v1.0.xlsx")
    template_bytes = template_path.read_bytes()

    header = "|".join(DEFECT_REPORT_EXPECTED_HEADERS)
    row = "|".join(
        [
            "1",
            "Windows",
            "요약",
            "High",
            "Frequent",
            "품질",
            "설명",
            "응답",
            "수정",
            "비고",
        ]
    )
    csv_text = f"{header}\n{row}"

    image_bytes = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVQIW2P8z/C/HwAFgwJ/lW+7TQAAAABJRU5ErkJggg=="
    )

    workbook_bytes = populate_defect_report(
        template_bytes,
        csv_text,
        images={1: [DefectReportImage(file_name="image.png", content=image_bytes)]},
    )

    with zipfile.ZipFile(io.BytesIO(workbook_bytes), "r") as zf:
        drawing_xml = zf.read("xl/drawings/drawing2.xml")

    assert b"<xdr:wsDr" in drawing_xml
    assert b"xmlns:r=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships\"" in drawing_xml
    assert b"r:embed=\"rId1\"" in drawing_xml


def test_populate_defect_report_accepts_spaced_headers() -> None:
    template_path = Path("backend/template/다.수행/GS-B-2X-XXXX 결함리포트 v1.0.xlsx")
    template_bytes = template_path.read_bytes()

    csv_header = "|".join(
        [
            "순번",
            "시험환경 OS",
            "결함 요약",
            "결함 정도",
            "발생 빈도",
            "품질 특성",
            "결함 설명",
            "업체 응답",
            "수정 여부",
            "비고",
        ]
    )
    csv_row = "|".join(
        [
            "7",
            "시험환경 모든 OS",
            "요약 텍스트",
            "M",
            "I",
            "보안성",
            "상세 설명",
            "",
            "",
            "비고 메모",
        ]
    )
    csv_text = f"{csv_header}\n{csv_row}"

    updated = populate_defect_report(template_bytes, csv_text)
    root = _load_sheet(updated)

    assert _cell_text(root, "A6") == "7"
    assert _cell_text(root, "B6") == "시험환경 모든 OS"
    assert _cell_text(root, "C6") == "요약 텍스트"
    assert _cell_text(root, "D6") == "M"
    assert _cell_text(root, "E6") == "I"
    assert _cell_text(root, "F6") == "보안성"
    assert _cell_text(root, "G6") == "상세 설명"
    assert _cell_text(root, "J6") == "비고 메모"


@pytest.mark.parametrize(
    "inject_fn,image_cls",
    [
        (modern_inject_defect_images, modern_DefectReportImage),
        (legacy_inject_defect_images, legacy_DefectReportImage),
    ],
)
def test_inject_defect_images_inserts_before_legacy(
    inject_fn, image_cls
) -> None:
    workbook_bytes, sheet_bytes = _build_test_workbook(
        include_drawing=False, include_legacy=True
    )
    images_map = {1: [image_cls(file_name="image.png", content=_DUMMY_PNG)]}

    result = inject_fn(
        workbook_bytes,
        sheet_bytes,
        row_positions={1: 6},
        images_map=images_map,
        column_letter="J",
    )

    root = _load_sheet(result)
    child_tags = [child.tag.split("}", 1)[-1] for child in list(root)]
    assert child_tags == ["sheetData", "pageMargins", "drawing", "legacyDrawing"]


@pytest.mark.parametrize(
    "inject_fn,image_cls",
    [
        (modern_inject_defect_images, modern_DefectReportImage),
        (legacy_inject_defect_images, legacy_DefectReportImage),
    ],
)
def test_inject_defect_images_preserves_existing_drawing_order(
    inject_fn, image_cls
) -> None:
    workbook_bytes, sheet_bytes = _build_test_workbook(
        include_drawing=True, include_legacy=True
    )
    images_map = {1: [image_cls(file_name="image.png", content=_DUMMY_PNG)]}

    result = inject_fn(
        workbook_bytes,
        sheet_bytes,
        row_positions={1: 6},
        images_map=images_map,
        column_letter="J",
    )

    root = _load_sheet(result)
    child_tags = [child.tag.split("}", 1)[-1] for child in list(root)]
    assert child_tags == ["sheetData", "pageMargins", "drawing", "drawing", "legacyDrawing"]

    drawings = [child for child in root if child.tag.split("}", 1)[-1] == "drawing"]
    assert len(drawings) == 2
    assert all(drawing.get(f"{{{_REL_NS}}}id") for drawing in drawings)
