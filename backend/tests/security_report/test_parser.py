from __future__ import annotations

import sys
from pathlib import Path

import pytest

pytest.importorskip("bs4")
from bs4 import BeautifulSoup

BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.security_report import parser
from app.services.security_report.models import StandardizedFinding


_HTML_SAMPLE = """
<html>
  <body>
    <table class="detailed-scan">
      <tbody>
        <tr class="high-severity">
          <td>High</td>
          <td><a href="#finding-1">SQL Injection</a></td>
          <td>detail</td>
          <td>/login</td>
          <td>param</td>
        </tr>
        <tr class="low-severity">
          <td>Low</td>
          <td><a href="#finding-2">Low Risk</a></td>
          <td>detail</td>
          <td>/health</td>
          <td>param</td>
        </tr>
      </tbody>
    </table>
    <div id="finding-1">
      <h2>Finding Description</h2>
      <p>SQL injection details</p>
      <h3>Evidence</h3>
      <p>Proof details</p>
    </div>
  </body>
</html>
"""


def _soup() -> BeautifulSoup:
    return BeautifulSoup(_HTML_SAMPLE, "html.parser")


def test_parse_findings_extracts_high_severity_only() -> None:
    findings = parser.parse_findings(_soup())
    assert len(findings) == 1
    finding = findings[0]
    assert finding.name == "SQL Injection"
    assert finding.severity == "High"
    assert finding.path == "/login"
    assert finding.anchor_id == "finding-1"
    assert "SQL injection" in finding.description_text
    assert finding.evidence_text == "Proof details"


def test_build_placeholder_values_includes_url() -> None:
    soup = _soup()
    finding = parser.parse_findings(soup)[0]
    values = parser.build_placeholder_values(finding, soup)
    assert values["URL"] == "/login"


def test_merge_similar_findings_preserves_first_path() -> None:
    findings = [
        StandardizedFinding(
            invicti_name="SQL Injection",
            path="/login",
            severity="High",
            severity_rank=3,
            anchor_id="finding-1",
            summary="SQL Injection",
            recommendation="Fix",
            category="보안성",
            occurrence="A",
            description="desc",
            excluded=False,
            raw_details="raw",
            ai_notes={},
            source="criteria",
        ),
        StandardizedFinding(
            invicti_name="SQL Injection",
            path="/admin",
            severity="High",
            severity_rank=3,
            anchor_id="finding-1",
            summary="SQL Injection",
            recommendation="Fix",
            category="보안성",
            occurrence="A",
            description="desc",
            excluded=False,
            raw_details="raw",
            ai_notes={},
            source="criteria",
        ),
    ]

    merged = parser.merge_similar_findings(findings)
    assert len(merged) == 1
    assert merged[0].path == "/login"
