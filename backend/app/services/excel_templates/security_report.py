from __future__ import annotations

import csv
import io

from .defect_report import populate_defect_report
from .models import DEFECT_REPORT_EXPECTED_HEADERS, SECURITY_REPORT_EXPECTED_HEADERS
from .utils import AI_CSV_DELIMITER, parse_csv_records

__all__ = [
    "SECURITY_REPORT_EXPECTED_HEADERS",
    "populate_security_report",
]


def populate_security_report(workbook_bytes: bytes, csv_text: str) -> bytes:
    records = parse_csv_records(csv_text, SECURITY_REPORT_EXPECTED_HEADERS)

    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=AI_CSV_DELIMITER)
    writer.writerow(DEFECT_REPORT_EXPECTED_HEADERS)
    for record in records:
        writer.writerow(
            [
                record.get("순번", ""),
                record.get("시험환경 OS", ""),
                record.get("결함 요약", ""),
                record.get("결함 정도", ""),
                record.get("발생 빈도", ""),
                record.get("품질 특성", ""),
                record.get("결함 설명", ""),
                record.get("업체 응답", ""),
                record.get("수정여부", ""),
                record.get("비고", ""),
            ]
        )

    converted_csv = buffer.getvalue()
    return populate_defect_report(workbook_bytes, converted_csv)
