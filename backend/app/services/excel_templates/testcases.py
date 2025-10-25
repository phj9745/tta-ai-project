from __future__ import annotations

import io
import zipfile

from .models import TESTCASE_COLUMNS, TESTCASE_EXPECTED_HEADERS, TESTCASE_START_ROW, XLSX_SHEET_PATH
from .utils import parse_csv_records
from .workbook import WorksheetPopulator, replace_sheet_bytes

__all__ = [
    "TESTCASE_COLUMNS",
    "TESTCASE_EXPECTED_HEADERS",
    "populate_testcase_list",
]


def populate_testcase_list(workbook_bytes: bytes, csv_text: str) -> bytes:
    records = parse_csv_records(csv_text, TESTCASE_EXPECTED_HEADERS)
    with zipfile.ZipFile(io.BytesIO(workbook_bytes), "r") as source:
        sheet_bytes = source.read(XLSX_SHEET_PATH)
    populator = WorksheetPopulator(sheet_bytes, start_row=TESTCASE_START_ROW, columns=TESTCASE_COLUMNS)
    populator.populate(records)
    return replace_sheet_bytes(workbook_bytes, populator.to_bytes())
