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

from app.services.excel_templates import testcases
from app.services.excel_templates.models import SPREADSHEET_NS

FIXTURE_DIR = Path(__file__).resolve().parent / "data" / "excel_templates"
TEMPLATE_PATH = BACKEND_ROOT / "template" / "나.설계" / "GS-B-XX-XXXX 테스트케이스.xlsx"


def test_populate_testcase_list_matches_fixture() -> None:
    template_bytes = TEMPLATE_PATH.read_bytes()
    csv_text = (FIXTURE_DIR / "testcases.csv").read_text(encoding="utf-8")
    expected_hash = (FIXTURE_DIR / "testcases_expected.sha256").read_text().strip()

    result = testcases.populate_testcase_list(template_bytes, csv_text)

    assert hashlib.sha256(result).hexdigest() == expected_hash

    with zipfile.ZipFile(io.BytesIO(result), "r") as archive:
        sheet_xml = archive.read("xl/worksheets/sheet1.xml")

    root = ET.fromstring(sheet_xml)
    ns = {"s": SPREADSHEET_NS}
    merges = [
        (merge.get("ref") or "").strip()
        for merge in root.findall("s:mergeCells/s:mergeCell", ns)
    ]

    assert "A6:A8" in merges
    assert "A9:A10" in merges
    assert "B6:B7" in merges
    assert "B9:B10" in merges

    def cell_text(column: str, row_index: int) -> str:
        row = root.find(f"s:sheetData/s:row[@r='{row_index}']", ns)
        if row is None:
            return ""
        cell = row.find(f"s:c[@r='{column}{row_index}']", ns)
        if cell is None:
            return ""
        text_elem = cell.find("s:is/s:t", ns)
        return text_elem.text if text_elem is not None and text_elem.text else ""

    assert cell_text("A", 6) == "대분류A"
    assert cell_text("A", 7) == ""
    assert cell_text("B", 6) == "중분류B"
    assert cell_text("B", 7) == ""
