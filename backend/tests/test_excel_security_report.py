from __future__ import annotations

import hashlib
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.excel_templates import security_report

FIXTURE_DIR = Path(__file__).resolve().parent / "data" / "excel_templates"
TEMPLATE_PATH = BACKEND_ROOT / "template" / "다.수행" / "GS-B-2X-XXXX 결함리포트 v1.0.xlsx"


def test_populate_security_report_matches_fixture() -> None:
    template_bytes = TEMPLATE_PATH.read_bytes()
    csv_text = (FIXTURE_DIR / "security_report.csv").read_text(encoding="utf-8")
    expected_hash = (FIXTURE_DIR / "security_report_expected.sha256").read_text().strip()

    result = security_report.populate_security_report(template_bytes, csv_text)

    assert hashlib.sha256(result).hexdigest() == expected_hash
