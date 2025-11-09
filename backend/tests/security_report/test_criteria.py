from __future__ import annotations

import io
import sys
from pathlib import Path

import pytest

pytest.importorskip("pandas")
pytest.importorskip("openpyxl")
from openpyxl import Workbook

BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.security_report import criteria
from app.services.security_report.models import StandardizedFinding


def _criteria_bytes(include_columns: bool = True) -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    if include_columns:
        sheet.append(list(criteria.CRITERIA_REQUIRED_COLUMNS))
    else:
        sheet.append(["Invicti 결과", "결함 요약"])
    sheet.append(
        [
            "SQL Injection",
            "SQL Injection 위험",
            "High",
            "A",
            "보안성",
            "SQL Injection 설명",
            "0",
        ]
    )
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def test_load_criteria_from_bytes_normalizes_columns() -> None:
    dataframe = criteria.load_criteria_from_bytes(_criteria_bytes())
    assert set(criteria.CRITERIA_REQUIRED_COLUMNS) <= set(dataframe.columns)
    assert dataframe.iloc[0]["Invicti 결과"] == "SQL Injection"


def test_load_criteria_from_bytes_missing_columns_raises() -> None:
    with pytest.raises(criteria.CriteriaValidationError):
        criteria.load_criteria_from_bytes(_criteria_bytes(include_columns=False))


def test_find_best_match_returns_expected_index() -> None:
    dataframe = criteria.load_criteria_from_bytes(_criteria_bytes())
    match = criteria.find_best_match("SQL Injection", dataframe["Invicti 결과"])
    assert match is not None
    value, score, index = match
    assert value == "SQL Injection"
    assert score == 100
    assert index == 0


def test_append_generated_rule_adds_row() -> None:
    dataframe = criteria.load_criteria_from_bytes(_criteria_bytes())
    finding = StandardizedFinding(
        invicti_name="Command Injection",
        path="/api",
        severity="High",
        severity_rank=3,
        anchor_id=None,
        summary="Command Injection",
        recommendation="Fix",
        category="보안성",
        occurrence="A",
        description="desc",
        excluded=False,
        raw_details="raw",
        ai_notes={},
        source="ai",
    )

    criteria.append_generated_rule(dataframe, finding)
    assert "Command Injection" in dataframe["Invicti 결과"].tolist()
