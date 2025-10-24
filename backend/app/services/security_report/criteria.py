from __future__ import annotations

import io
import logging
from typing import Any, Dict, Iterable, Optional, Sequence, Tuple

import pandas as pd
from thefuzz import process as fuzz_process

from .models import StandardizedFinding

logger = logging.getLogger(__name__)

CRITERIA_FILE_NAME = "보안성 결함판단기준표 v1.0.xlsx"
CRITERIA_REQUIRED_COLUMNS: Tuple[str, ...] = (
    "Invicti 결과",
    "결함 요약",
    "결함정도",
    "발생빈도",
    "품질특성",
    "결함 설명",
    "결함 제외 여부",
)


class CriteriaError(Exception):
    """Base error for criteria handling."""


class CriteriaFormatError(CriteriaError):
    """Raised when the spreadsheet cannot be parsed."""


class CriteriaValidationError(CriteriaError):
    """Raised when the spreadsheet misses required columns."""


def load_criteria_from_bytes(payload: bytes) -> pd.DataFrame:
    try:
        criteria_df = pd.read_excel(io.BytesIO(payload))
    except Exception as exc:  # pragma: no cover - pandas internals
        raise CriteriaFormatError("Failed to load criteria spreadsheet") from exc

    missing_columns = [
        column for column in CRITERIA_REQUIRED_COLUMNS if column not in criteria_df.columns
    ]
    if missing_columns:
        logger.error(
            "Security criteria spreadsheet missing required columns: %s",
            ", ".join(missing_columns),
        )
        raise CriteriaValidationError(
            "Criteria spreadsheet missing required columns",
        )

    normalized = criteria_df.copy()
    normalized["Invicti 결과"] = normalized["Invicti 결과"].astype(str).str.strip()
    normalized["결함 제외 여부"] = normalized["결함 제외 여부"].fillna(0).astype(str)
    return normalized


def find_best_match(
    finding_name: str,
    criteria_candidates: Sequence[str],
    *,
    threshold: int = 70,
) -> Optional[Tuple[str, int, int]]:
    if not finding_name:
        return None

    choices = list(criteria_candidates)
    matches = fuzz_process.extractOne(
        query=finding_name,
        choices=choices,
        score_cutoff=threshold,
    )
    if not matches:
        return None
    value, score = matches[:2]
    try:
        index = choices.index(value)
    except ValueError:
        return None
    return value, score, index


def is_excluded(value: Any) -> bool:
    text = str(value or "").strip().lower()
    return text in {"1", "true", "yes", "y", "t", "on"}


def determine_recommendation(record: pd.Series) -> str:
    recommendation = record.get("조치 가이드")
    if isinstance(recommendation, str):
        return recommendation.strip()
    return ""


def append_generated_rule(criteria_df: pd.DataFrame, finding: StandardizedFinding) -> None:
    new_row = {
        "Invicti 결과": finding.invicti_name,
        "결함 요약": finding.summary,
        "결함정도": finding.severity,
        "발생빈도": finding.occurrence,
        "품질특성": finding.category,
        "결함 설명": finding.description,
        "결함 제외 여부": "0",
    }
    criteria_df.loc[len(criteria_df)] = new_row
