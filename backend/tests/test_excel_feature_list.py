from __future__ import annotations

import hashlib
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.excel_templates import feature_list

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
