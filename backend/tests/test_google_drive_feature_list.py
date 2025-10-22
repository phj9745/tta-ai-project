from __future__ import annotations

import sys
from pathlib import Path

import pytest

pytest.importorskip("openpyxl")

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.google_drive import (  # noqa: E402
    FEATURE_LIST_EXPECTED_HEADERS,
    _looks_like_header_row,
)


def test_header_row_accepts_suffixes_and_whitespace():
    values = (" 대분류 (필수)", "중분류\n항목", "소분류-예시")
    assert _looks_like_header_row(values, FEATURE_LIST_EXPECTED_HEADERS)


def test_header_row_requires_multiple_matches():
    values = ("대분류", "", "기타")
    assert not _looks_like_header_row(values, FEATURE_LIST_EXPECTED_HEADERS)
