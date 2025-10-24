"""Helpers related to Drive defect report workflows."""
from __future__ import annotations

from typing import Any, Dict, Iterable, List

from ..excel_templates.models import DEFECT_REPORT_EXPECTED_HEADERS, DefectReportImage

__all__ = [
    "DEFECT_REPORT_EXPECTED_HEADERS",
    "serialize_defect_report_images",
]


def serialize_defect_report_images(images: Iterable[DefectReportImage]) -> List[Dict[str, Any]]:
    serialized: List[Dict[str, Any]] = []
    for image in images:
        serialized.append(
            {
                "filename": image.filename,
                "contentType": image.content_type,
                "size": image.size,
                "defectIndex": image.defect_index,
            }
        )
    return serialized
