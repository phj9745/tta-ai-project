from __future__ import annotations

import hashlib
import io
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.excel_templates import feature_list
from app.services.excel_templates.models import SPREADSHEET_NS

FIXTURE_DIR = Path(__file__).resolve().parent / "data" / "excel_templates"
TEMPLATE_PATH = BACKEND_ROOT / "template" / "가.계획" / "GS-B-XX-XXXX 기능리스트 v1.0.xlsx"


def test_populate_feature_list_matches_fixture() -> None:
    template_bytes = TEMPLATE_PATH.read_bytes()
    csv_text = (FIXTURE_DIR / "feature_list.csv").read_text(encoding="utf-8")
    expected_hash = (FIXTURE_DIR / "feature_list_expected.sha256").read_text().strip()

    result = feature_list.populate_feature_list(
        template_bytes,
        csv_text,
        project_overview="프로젝트 개요",
    )

    assert hashlib.sha256(result).hexdigest() == expected_hash

    with zipfile.ZipFile(io.BytesIO(result), "r") as archive:
        sheet_xml = archive.read("xl/worksheets/sheet1.xml")

    root = ET.fromstring(sheet_xml)
    ns = {"s": SPREADSHEET_NS}
    merges = [
        (merge.get("ref") or "").strip()
        for merge in root.findall("s:mergeCells/s:mergeCell", ns)
    ]

    assert "A8:A10" in merges
    assert "A11:A12" in merges
    assert "B8:B9" in merges
    assert "B11:B12" in merges

    def cell_text(column: str, row_index: int) -> str:
        row = root.find(f"s:sheetData/s:row[@r='{row_index}']", ns)
        if row is None:
            return ""
        cell = row.find(f"s:c[@r='{column}{row_index}']", ns)
        if cell is None:
            return ""
        text_elem = cell.find("s:is/s:t", ns)
        return text_elem.text if text_elem is not None and text_elem.text else ""

    assert cell_text("A", 8) == "대1"
    assert cell_text("A", 9) == ""
    assert cell_text("B", 8) == "중1"
    assert cell_text("B", 9) == ""


def test_extract_feature_list_overview() -> None:
    template_bytes = TEMPLATE_PATH.read_bytes()
    csv_text = (FIXTURE_DIR / "feature_list.csv").read_text(encoding="utf-8")
    populated = feature_list.populate_feature_list(
        template_bytes,
        csv_text,
        project_overview="프로젝트 개요",
    )

    ref, value = feature_list.extract_feature_list_overview(populated)

    assert ref is not None
    assert value == "프로젝트 개요"
