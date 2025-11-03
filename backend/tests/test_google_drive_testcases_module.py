import io
import sys
from pathlib import Path

import pytest

pytest.importorskip("openpyxl")
from openpyxl import Workbook  # type: ignore

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.google_drive.testcases import (  # type: ignore  # noqa: E402
    build_testcase_rows_csv,
    parse_testcase_workbook,
)


@pytest.fixture()
def sample_workbook_bytes() -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "테스트케이스"
    # Add banner rows before headers to mimic template layout
    sheet.append(["테스트케이스 관리", "", "", "", "", "", "", "", "", ""])
    sheet.append(["", "", "", "", "", "", "", "", "", ""])
    sheet.append(
        [
            "대분류",
            "중분류",
            "소분류",
            "테스트 케이스 ID",
            "테스트 시나리오",
            "입력(사전조건 포함)",
            "기대 출력(사후조건 포함)",
            "테스트 결과",
            "상세 테스트 결과",
            "비고",
        ]
    )
    sheet.append(
        [
            "로그인",
            "인증",
            "OTP",
            "TC-001",
            "OTP 코드를 입력한다",
            "앱에서 생성된 OTP 입력",
            "인증 성공",
            "P",
            "앱과 서버의 시간이 동기화되어 있어야 함",
            "--",
        ]
    )
    sheet.append(
        [
            None,
            None,
            None,
            "TC-001A",
            "OTP 입력 지연",
            "지연된 OTP 입력",
            "인증 실패",
            "F",
            "지연 경고 메시지가 표시되어야 함",
            "--",
        ]
    )
    sheet.append(
        [
            None,
            None,
            "OTP 재시도",
            "TC-002",
            "만료된 OTP 입력",
            "만료된 OTP 입력",
            "인증 실패",
            "F",
            "만료 안내 메시지가 표시되어야 함",
            "재발급 가능",
        ]
    )
    sheet.append(
        [
            "결제",
            "거래",
            "환불",
            "TC-003",
            "환불 시나리오",
            "환불 요청",
            "환불 성공",
            "P",
            "승인 내역 확인",
            "--",
        ]
    )
    buffer = io.BytesIO()
    workbook.save(buffer)
    workbook.close()
    return buffer.getvalue()


def test_parse_testcase_workbook_extracts_rows(sample_workbook_bytes: bytes) -> None:
    sheet_name, start_row, headers, rows = parse_testcase_workbook(sample_workbook_bytes)

    assert sheet_name == "테스트케이스"
    assert start_row >= 3
    assert headers[:3] == ["대분류", "중분류", "소분류"]
    assert len(rows) == 4
    assert rows[0]["testcaseId"] == "TC-001"
    assert rows[1]["majorCategory"] == "로그인"
    assert rows[1]["middleCategory"] == "인증"
    assert rows[1]["minorCategory"] == "OTP"
    assert rows[1]["expected"] == "인증 실패"
    assert rows[2]["minorCategory"] == "OTP 재시도"


def test_build_testcase_rows_csv_roundtrip(sample_workbook_bytes: bytes) -> None:
    _, _, _, rows = parse_testcase_workbook(sample_workbook_bytes)
    csv_text = build_testcase_rows_csv(rows)

    # When we repopulate the template with the csv, it should contain our headers
    assert "테스트 케이스 ID" in csv_text
    assert "TC-001A" in csv_text
    assert "TC-002" in csv_text
