from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.google_drive.naming import (  # noqa: E402
    drive_name_variants,
    drive_suffix_matches,
    looks_like_header_row,
    normalize_drive_text,
)


def test_normalize_drive_text_trims_and_lowercases() -> None:
    assert normalize_drive_text("  HELLO\u00a0World   ") == "hello world"


def test_drive_name_variants_includes_versionless() -> None:
    variants = drive_name_variants("Report v1.2.xlsx")
    assert "report" in variants
    assert "reportv12" in variants


def test_drive_suffix_matches_handles_partial_suffix() -> None:
    assert drive_suffix_matches("Project_Report_Final.xlsx", "report final")
    assert not drive_suffix_matches("Project_Plan.xlsx", "report final")


def test_looks_like_header_row_demands_majority() -> None:
    headers = ["A", "B", "C"]
    assert looks_like_header_row(["a", "something", "c"], headers)
    assert not looks_like_header_row(["a", "", ""], headers)
