from __future__ import annotations

import io
import sys
from pathlib import Path

import pytest

pytest.importorskip("docx")
from docx import Document

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.google_drive.metadata import (  # noqa: E402
    build_project_folder_name,
    extract_project_metadata,
    normalize_label,
)


def _build_sample_agreement() -> bytes:
    document = Document()
    table = document.add_table(rows=3, cols=2)
    table.cell(0, 0).text = "시험 신청 번호"
    table.cell(0, 1).text = "GS-B-12-3456"
    table.cell(1, 0).text = "제조자"
    table.cell(1, 1).text = "Acme Corp"
    table.cell(2, 0).text = "제품명및버전"
    table.cell(2, 1).text = "Wonder Widget 1.0"
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def test_normalize_label_strips_whitespace() -> None:
    assert normalize_label(" 제 조 자 ") == "제조자"


def test_extract_project_metadata_reads_table() -> None:
    metadata = extract_project_metadata(_build_sample_agreement())
    assert metadata == {
        "exam_number": "GS-B-12-3456",
        "company_name": "Acme Corp",
        "product_name": "Wonder Widget 1.0",
    }


def test_build_project_folder_name_formats_metadata() -> None:
    metadata = {
        "exam_number": "GS-B-12-3456",
        "company_name": "Acme Corp",
        "product_name": "Wonder Widget 1.0",
    }
    assert build_project_folder_name(metadata) == "[GS-B-12-3456] Acme Corp - Wonder Widget 1.0"
