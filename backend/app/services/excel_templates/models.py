from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

__all__ = [
    "SPREADSHEET_NS",
    "XML_NS",
    "XLSX_SHEET_PATH",
    "DRAWING_NS",
    "DRAWING_A_NS",
    "REL_NS",
    "CONTENT_TYPES_NS",
    "EMU_PER_PIXEL",
    "IMAGE_VERTICAL_GAP_PX",
    "FEATURE_LIST_START_ROW",
    "TESTCASE_START_ROW",
    "DEFECT_REPORT_START_ROW",
    "ColumnSpec",
    "DefectReportImage",
    "FEATURE_LIST_COLUMNS",
    "FEATURE_LIST_EXPECTED_HEADERS",
    "TESTCASE_COLUMNS",
    "TESTCASE_EXPECTED_HEADERS",
    "DEFECT_REPORT_COLUMNS",
    "DEFECT_REPORT_EXPECTED_HEADERS",
    "SECURITY_REPORT_EXPECTED_HEADERS",
]


SPREADSHEET_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
XML_NS = "http://www.w3.org/XML/1998/namespace"
XLSX_SHEET_PATH = "xl/worksheets/sheet1.xml"
DRAWING_NS = "http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing"
DRAWING_A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
CONTENT_TYPES_NS = "http://schemas.openxmlformats.org/package/2006/content-types"
EMU_PER_PIXEL = 9525
IMAGE_VERTICAL_GAP_PX = 4

FEATURE_LIST_START_ROW = 8
TESTCASE_START_ROW = 6
DEFECT_REPORT_START_ROW = 6


@dataclass(frozen=True)
class ColumnSpec:
    key: str
    letter: str
    style: str


@dataclass(frozen=True)
class DefectReportImage:
    file_name: str
    content: bytes
    content_type: str | None = None


FEATURE_LIST_COLUMNS: Sequence[ColumnSpec] = (
    ColumnSpec(key="대분류", letter="A", style="12"),
    ColumnSpec(key="중분류", letter="B", style="8"),
    ColumnSpec(key="소분류", letter="C", style="15"),
    ColumnSpec(key="기능 설명", letter="D", style="7"),
)

FEATURE_LIST_EXPECTED_HEADERS: Sequence[str] = [
    "대분류",
    "중분류",
    "소분류",
    "기능 설명",
]

TESTCASE_COLUMNS: Sequence[ColumnSpec] = (
    ColumnSpec(key="대분류", letter="A", style="31"),
    ColumnSpec(key="중분류", letter="B", style="31"),
    ColumnSpec(key="소분류", letter="C", style="18"),
    ColumnSpec(key="테스트 케이스 ID", letter="D", style="24"),
    ColumnSpec(key="테스트 시나리오", letter="E", style="18"),
    ColumnSpec(key="입력(사전조건 포함)", letter="F", style="18"),
    ColumnSpec(key="기대 출력(사후조건 포함)", letter="G", style="18"),
    ColumnSpec(key="테스트 결과", letter="H", style="19"),
    ColumnSpec(key="상세 테스트 결과", letter="I", style="7"),
    ColumnSpec(key="비고", letter="J", style="6"),
)

TESTCASE_EXPECTED_HEADERS: Sequence[str] = [
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

DEFECT_REPORT_COLUMNS: Sequence[ColumnSpec] = (
    ColumnSpec(key="순번", letter="A", style="24"),
    ColumnSpec(key="시험환경(OS)", letter="B", style="25"),
    ColumnSpec(key="결함요약", letter="C", style="10"),
    ColumnSpec(key="결함정도", letter="D", style="26"),
    ColumnSpec(key="발생빈도", letter="E", style="26"),
    ColumnSpec(key="품질특성", letter="F", style="25"),
    ColumnSpec(key="결함 설명", letter="G", style="23"),
    ColumnSpec(key="업체 응답", letter="H", style="10"),
    ColumnSpec(key="수정여부", letter="I", style="10"),
    ColumnSpec(key="비고", letter="J", style="11"),
)

DEFECT_REPORT_EXPECTED_HEADERS: Sequence[str] = [
    "순번",
    "시험환경(OS)",
    "결함요약",
    "결함정도",
    "발생빈도",
    "품질특성",
    "결함 설명",
    "업체 응답",
    "수정여부",
    "비고",
]

SECURITY_REPORT_EXPECTED_HEADERS: Sequence[str] = [
    "순번",
    "시험환경 OS",
    "결함 요약",
    "결함 정도",
    "발생 빈도",
    "품질 특성",
    "결함 설명",
    "업체 응답",
    "수정여부",
    "비고",
    "매핑 유형",
]
