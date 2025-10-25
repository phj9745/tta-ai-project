from __future__ import annotations

import io
import sys
from pathlib import Path

import pytest

pytest.importorskip("openpyxl")
from openpyxl import Workbook

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.google_drive.feature_lists import (  # noqa: E402
    build_feature_list_rows_csv,
    parse_feature_list_workbook,
    prepare_feature_list_response,
)


def _build_workbook() -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "기능 리스트"
    sheet.append([" 대분류 ", "중 분류", "소분류", "기능 설명"])
    sheet.append(["인증", "로그인", "아이디", "사용자 인증 처리"])
    buffer = io.BytesIO()
    workbook.save(buffer)
    workbook.close()
    return buffer.getvalue()


def test_parse_feature_list_workbook_extracts_rows() -> None:
    sheet_title, start_row, headers, rows = parse_feature_list_workbook(_build_workbook())
    assert sheet_title.lower().startswith("기능")
    assert start_row == 2
    assert headers[0] == "대분류"
    assert rows == [
        {
            "majorCategory": "인증",
            "middleCategory": "로그인",
            "minorCategory": "아이디",
            "featureDescription": "사용자 인증 처리",
        }
    ]


def test_build_feature_list_rows_csv_roundtrips_rows() -> None:
    csv_text = build_feature_list_rows_csv([
        {
            "majorCategory": "인증",
            "middleCategory": "로그인",
            "minorCategory": "아이디",
            "featureDescription": "사용자 인증 처리",
        },
        {
            "majorCategory": "",
            "middleCategory": "",
            "minorCategory": "",
            "featureDescription": "",
        },
    ])
    assert "사용자 인증 처리" in csv_text
    assert csv_text.count("로그인") == 1


def test_prepare_feature_list_response_includes_overview() -> None:
    response = prepare_feature_list_response(
        file_id="123",
        file_name="기능리스트.xlsx",
        sheet_name="Sheet1",
        start_row=8,
        headers=["대분류"],
        rows=[{"majorCategory": "인증"}],
        modified_time="2024-01-01T00:00:00Z",
        project_overview="Overview",
    )
    assert response["projectOverview"] == "Overview"
    assert response["rows"] == [{"majorCategory": "인증"}]
