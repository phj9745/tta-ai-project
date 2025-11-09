from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict

SEVERITY_RANKING: Dict[str, int] = {
    "informational": 0,
    "info": 0,
    "low": 1,
    "medium": 2,
    "moderate": 2,
    "high": 3,
    "critical": 4,
    "urgent": 4,
}


@dataclass(slots=True)
class InvictiFinding:
    """Parsed representation of a single Invicti finding."""

    name: str
    severity: str
    severity_rank: int
    path: str
    anchor_id: str | None
    description_html: str
    description_text: str
    evidence_text: str | None = None


@dataclass(slots=True)
class StandardizedFinding:
    """Finding aligned with the shared criteria."""

    invicti_name: str
    path: str
    severity: str
    severity_rank: int
    anchor_id: str | None
    summary: str
    recommendation: str
    category: str
    occurrence: str
    description: str
    excluded: bool
    raw_details: str
    ai_notes: Dict[str, Any] = field(default_factory=dict)
    source: str = "criteria"
