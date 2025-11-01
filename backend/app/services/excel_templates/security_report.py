from __future__ import annotations

import csv
import io

from typing import Dict, List

from .defect_report import populate_defect_report
from .models import DEFECT_REPORT_EXPECTED_HEADERS, SECURITY_REPORT_EXPECTED_HEADERS
from .utils import AI_CSV_DELIMITER, parse_csv_records


def _extract_existing_rows(workbook_bytes: bytes) -> List[Dict[str, str]]:
    from ..google_drive import defect_reports as drive_defect_reports

    try:
        _, _, _, rows = drive_defect_reports.parse_defect_report_workbook(workbook_bytes)
    except Exception:
        return []
    return rows


def _determine_next_order(rows: List[Dict[str, str]]) -> int:
    max_order = 0
    for row in rows:
        try:
            order_value = int(str(row.get("order", "")).strip())
        except (TypeError, ValueError):
            continue
        if order_value > max_order:
            max_order = order_value
    return max_order + 1

__all__ = [
    "SECURITY_REPORT_EXPECTED_HEADERS",
    "populate_security_report",
]


def populate_security_report(workbook_bytes: bytes, csv_text: str) -> bytes:
    records = parse_csv_records(csv_text, SECURITY_REPORT_EXPECTED_HEADERS)
    existing_rows = _extract_existing_rows(workbook_bytes)
    next_order = _determine_next_order(existing_rows)

    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=AI_CSV_DELIMITER)
    writer.writerow(DEFECT_REPORT_EXPECTED_HEADERS)

    for row in existing_rows:
        writer.writerow(
            [
                row.get("order", ""),
                row.get("environment", ""),
                row.get("summary", ""),
                row.get("severity", ""),
                row.get("frequency", ""),
                row.get("quality", ""),
                row.get("description", ""),
                row.get("vendorResponse", ""),
                row.get("fixStatus", ""),
                row.get("note", ""),
            ]
        )

    for record in records:
        order_value = str(record.get("순번", "")).strip()
        if not order_value:
            order_value = str(next_order)
            next_order += 1
        else:
            try:
                numeric_order = int(order_value)
            except ValueError:
                numeric_order = None
            if numeric_order is not None and numeric_order >= next_order:
                next_order = numeric_order + 1

        environment = record.get("시험환경 OS", "").strip() or "시험환경 모든 OS"

        writer.writerow(
            [
                order_value,
                environment,
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
