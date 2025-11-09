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

from app.services.excel_templates import defect_report
from app.services.excel_templates.models import SPREADSHEET_NS
from app.services.excel_templates.utils import AI_CSV_DELIMITER

FIXTURE_DIR = Path(__file__).resolve().parent / "data" / "excel_templates"
TEMPLATE_PATH = BACKEND_ROOT / "template" / "다.수행" / "GS-B-2X-XXXX 결함리포트 v1.0.xlsx"


def test_populate_defect_report_matches_fixture() -> None:
    template_bytes = TEMPLATE_PATH.read_bytes()
    csv_text = (FIXTURE_DIR / "defect_report.csv").read_text(encoding="utf-8")
    if AI_CSV_DELIMITER != ",":
        csv_text = csv_text.replace(",", AI_CSV_DELIMITER)
    expected_hash = (FIXTURE_DIR / "defect_report_expected.sha256").read_text().strip()

    result = defect_report.populate_defect_report(template_bytes, csv_text)

    assert hashlib.sha256(result).hexdigest() == expected_hash


def test_populate_defect_report_does_not_inject_dimension() -> None:
    template_bytes = TEMPLATE_PATH.read_bytes()
    csv_text = (FIXTURE_DIR / "defect_report.csv").read_text(encoding="utf-8")
    if AI_CSV_DELIMITER != ",":
        csv_text = csv_text.replace(",", AI_CSV_DELIMITER)

    stripped_buffer = io.BytesIO()
    dimension_tag = f"{{{SPREADSHEET_NS}}}dimension"
    with zipfile.ZipFile(io.BytesIO(template_bytes), "r") as source, zipfile.ZipFile(
        stripped_buffer, "w"
    ) as target:
        for info in source.infolist():
            data = source.read(info.filename)
            if info.filename == "xl/worksheets/sheet1.xml":
                root = ET.fromstring(data)
                dimension = root.find(dimension_tag)
                if dimension is not None:
                    root.remove(dimension)
                data = ET.tostring(root, encoding="utf-8", xml_declaration=True)
            target.writestr(info, data)

    stripped_template = stripped_buffer.getvalue()
    result = defect_report.populate_defect_report(stripped_template, csv_text)

    with zipfile.ZipFile(io.BytesIO(result), "r") as archive:
        updated_sheet = archive.read("xl/worksheets/sheet1.xml")

    updated_root = ET.fromstring(updated_sheet)
    dimension = updated_root.find(dimension_tag)
    assert dimension is None, "<dimension> should not be injected"
