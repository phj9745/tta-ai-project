from __future__ import annotations

import hashlib
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.excel_templates import testcases

FIXTURE_DIR = Path(__file__).resolve().parent / "data" / "excel_templates"
TEMPLATE_PATH = BACKEND_ROOT / "template" / "나.설계" / "GS-B-XX-XXXX 테스트케이스.xlsx"


def test_populate_testcase_list_matches_fixture() -> None:
    template_bytes = TEMPLATE_PATH.read_bytes()
    csv_text = (FIXTURE_DIR / "testcases.csv").read_text(encoding="utf-8")
    expected_hash = (FIXTURE_DIR / "testcases_expected.sha256").read_text().strip()

    result = testcases.populate_testcase_list(template_bytes, csv_text)

    assert hashlib.sha256(result).hexdigest() == expected_hash
