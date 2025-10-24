from __future__ import annotations

import logging
import re
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from bs4 import BeautifulSoup

from .models import InvictiFinding, SEVERITY_RANKING, StandardizedFinding

logger = logging.getLogger(__name__)


def parse_findings(soup: BeautifulSoup) -> List[InvictiFinding]:
    findings: List[InvictiFinding] = []
    summary_rows = _extract_summary_rows(soup)

    for cells in summary_rows:
        name = cells.get("name")
        if not name:
            continue
        severity = _normalize_severity(cells.get("severity", ""))
        severity_rank = SEVERITY_RANKING.get(severity.lower(), -1)
        if severity_rank < SEVERITY_RANKING["medium"]:
            continue
        path = cells.get("path", "")
        anchor_id = cells.get("anchor_id")

        description_html, description_text, evidence_text = extract_detail_section(
            soup, anchor_id=anchor_id
        )

        findings.append(
            InvictiFinding(
                name=name,
                severity=severity,
                severity_rank=severity_rank,
                path=path,
                anchor_id=anchor_id,
                description_html=description_html,
                description_text=description_text,
                evidence_text=evidence_text,
            )
        )
    return findings


def _extract_summary_rows(soup: BeautifulSoup) -> List[Dict[str, str]]:
    headers_map: Dict[int, str] = {}
    extracted_rows: List[Dict[str, str]] = []
    tables = soup.find_all("table")
    for table in tables:
        classes = table.get("class") or []
        if isinstance(classes, str):
            classes = [classes]
        if "detailed-scan" in classes:
            extracted_rows.extend(_extract_detailed_scan_rows(table))
            if extracted_rows:
                return extracted_rows

    for table in tables:
        header_cells = table.find_all("th")
        candidate_headers = [cell.get_text(strip=True) for cell in header_cells]
        normalized_headers = [header.lower() for header in candidate_headers]
        if not normalized_headers:
            continue
        if "severity" not in normalized_headers:
            continue
        if not {"name", "vulnerability", "issue", "url", "path"} & set(normalized_headers):
            continue

        headers_map = {
            idx: header.lower() for idx, header in enumerate(candidate_headers)
        }

        for row in table.find_all("tr"):
            cells = row.find_all("td")
            if not cells:
                continue
            values: Dict[str, str] = {}
            anchor_id: Optional[str] = None
            for idx, cell in enumerate(cells):
                header = headers_map.get(idx, "")
                text = cell.get_text(" ", strip=True)
                if header in {"name", "vulnerability", "issue"}:
                    link = cell.find("a")
                    if link and link.get("href", "").startswith("#"):
                        anchor_id = link.get("href", "").lstrip("#")
                    values["name"] = text or (link.get_text(strip=True) if link else "")
                elif header in {"url", "path"}:
                    values["path"] = text
                elif header == "severity":
                    values["severity"] = text
                elif header == "status":
                    values["status"] = text
            if not values.get("name"):
                continue
            if anchor_id:
                values["anchor_id"] = anchor_id
            extracted_rows.append(values)
        if extracted_rows:
            break
    if not extracted_rows:
        logger.warning("Failed to extract summary rows from Invicti report.")
    return extracted_rows


def _extract_detailed_scan_rows(table: BeautifulSoup) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    tbody = table.find("tbody")
    if not tbody:
        return rows

    for row in tbody.find_all("tr"):
        cells = row.find_all("td")
        if not cells or len(cells) < 4:
            continue

        classes = row.get("class") or []
        severity = ""
        for class_name in classes:
            if class_name.endswith("-severity"):
                severity = class_name.rsplit("-", 1)[0]
                break
        severity = _normalize_severity(severity)

        link = cells[1].find("a")
        if link is None:
            continue
        name = link.get_text(strip=True)
        if not name:
            continue

        anchor_raw = link.get("href", "")
        anchor_id = anchor_raw.lstrip("#") if anchor_raw and anchor_raw.startswith("#") else None
        path_text = cells[3].get_text(" ", strip=True) if len(cells) >= 4 else ""

        rows.append(
            {
                "name": name,
                "severity": severity,
                "path": path_text,
                "anchor_id": anchor_id,
            }
        )
    return rows


def extract_detail_section(
    soup: BeautifulSoup,
    *,
    anchor_id: str | None,
) -> Tuple[str, str, Optional[str]]:
    if not anchor_id:
        return "", "", None
    section = soup.find(id=anchor_id)
    if section is None:
        return "", "", None

    description_parts: List[str] = []
    evidence_parts: List[str] = []
    for heading in section.find_all(["h1", "h2", "h3", "h4", "strong"]):
        heading_text = heading.get_text(strip=True).lower()
        if "evidence" in heading_text or "proof" in heading_text:
            sibling_text = heading.find_next_sibling()
            if sibling_text:
                evidence_parts.append(sibling_text.get_text("\n", strip=True))
            continue

    text_content = section.get_text("\n", strip=True)
    if text_content:
        description_parts.append(text_content)

    description_html = str(section)
    description_text = "\n".join(description_parts).strip()
    evidence_text = "\n".join(evidence_parts).strip() or None
    return description_html, description_text, evidence_text


def _normalize_severity(value: str) -> str:
    if not value:
        return ""
    text = str(value).strip()
    if not text:
        return ""
    match = re.search(r"(critical|high|medium|low|info|informational)", text, re.IGNORECASE)
    if match:
        normalized = match.group(1).capitalize()
    else:
        normalized = text.split()[0].capitalize()
    return normalized


def merge_similar_findings(findings: Sequence[StandardizedFinding]) -> List[StandardizedFinding]:
    """
    동일 취약 유형(같은 Invicti 결과/요약/위험도레벨/조치 가이드)에서 URL/파라미터만 다른 항목을 하나로 합칩니다.
    병합 시 대표 path는 해당 그룹에서 처음 등장한 path(맨 앞 항목의 path)만 사용합니다.
    결함 설명은 대표 항목의 description을 그대로 유지합니다.
    """
    merged_map: Dict[Tuple[str, str, int, str], StandardizedFinding] = {}
    first_path_seen: Dict[Tuple[str, str, int, str], str] = {}

    for finding in findings:
        key = (
            (finding.invicti_name or "").strip().lower(),
            (finding.summary or "").strip(),
            int(finding.severity_rank),
            (finding.recommendation or "").strip(),
        )
        if key not in merged_map:
            merged_map[key] = finding
            first_path_seen[key] = finding.path or ""
        else:
            existing = merged_map[key]
            existing.ai_notes = dict(existing.ai_notes or {})
            existing.ai_notes.setdefault("merged_count", 1)
            existing.ai_notes["merged_count"] = existing.ai_notes.get("merged_count", 1) + 1
            merged_map[key] = existing

    result: List[StandardizedFinding] = []
    for key, base in merged_map.items():
        rep_path = first_path_seen.get(key, base.path)
        result.append(
            StandardizedFinding(
                invicti_name=base.invicti_name,
                path=rep_path,
                severity=base.severity,
                severity_rank=base.severity_rank,
                anchor_id=base.anchor_id,
                summary=base.summary,
                recommendation=base.recommendation,
                category=base.category,
                occurrence=base.occurrence,
                description=base.description,
                excluded=base.excluded,
                raw_details=base.raw_details,
                ai_notes=base.ai_notes,
                source=base.source,
            )
        )
    return result


def build_placeholder_values(finding: InvictiFinding, soup: BeautifulSoup) -> Dict[str, str]:
    values: Dict[str, str] = {}

    program_name = _derive_program_name(finding)
    if program_name:
        values["프로그램 명"] = program_name
        values["프로그램명"] = program_name

    versions = _extract_version_details(soup, finding.anchor_id)
    if versions.get("current"):
        values["현재 버전"] = versions["current"]
        values["현재버전"] = versions["current"]
    if versions.get("latest"):
        values["최신 버전"] = versions["latest"]
        values["최신버전"] = versions["latest"]

    weak_ciphers = _extract_weak_ciphers(soup, finding.anchor_id)
    if weak_ciphers:
        values["암호화 목록"] = weak_ciphers
        values["암호화목록"] = weak_ciphers

    if finding.path:
        values["URL"] = finding.path
        values["Url"] = finding.path

    return values


def _extract_version_details(
    soup: BeautifulSoup,
    anchor_id: str | None,
) -> Dict[str, str]:
    details = {"current": "", "latest": ""}
    if not anchor_id:
        return details

    target_id = anchor_id.lstrip("#")
    h2_tag = soup.find("h2", id=target_id)
    if not h2_tag:
        return details

    vuln_desc_div = h2_tag.find_parent(class_="vuln-desc")
    if not vuln_desc_div:
        return details

    vulns_div = vuln_desc_div.find_next_sibling("div", class_="vulns")
    if not vulns_div:
        return details

    vuln_detail_div = vulns_div.find("div", class_="vuln-detail")
    if not vuln_detail_div:
        return details

    inner_div = vuln_detail_div.find("div")
    if not inner_div:
        return details

    for h4 in inner_div.find_all("h4"):
        aria_label = h4.get("aria-label", "").strip()
        if not aria_label:
            continue
        ul = h4.find_next_sibling("ul")
        if ul is None:
            continue
        li = ul.find("li")
        if li is None:
            continue
        version_text = li.get_text(strip=True).split("(")[0].strip()
        if aria_label == "확인된 버전":
            details["current"] = version_text
        elif aria_label == "최신 버전":
            details["latest"] = version_text
    return details


def _extract_weak_ciphers(
    soup: BeautifulSoup,
    anchor_id: str | None,
) -> str:
    if not anchor_id:
        return ""

    target_id = anchor_id.lstrip("#")
    h2_tag = soup.find("h2", id=target_id)
    if not h2_tag:
        return ""

    vuln_desc_div = h2_tag.find_parent(class_="vuln-desc")
    if not vuln_desc_div:
        return ""

    vulns_div = vuln_desc_div.find_next_sibling("div", class_="vulns")
    if not vulns_div:
        return ""

    vuln_detail_div = vulns_div.find("div", class_="vuln-detail")
    if not vuln_detail_div:
        return ""

    inner_div = vuln_detail_div.find("div")
    if not inner_div:
        return ""

    for h4 in inner_div.find_all("h4"):
        heading = h4.get_text(strip=True)
        if "허용된 암호화" in heading or "취약한 암호화" in heading:
            ul_tag = h4.find_next_sibling("ul")
            if not ul_tag:
                return ""
            ciphers = [li.get_text(strip=True) for li in ul_tag.find_all("li")]
            return "\n".join(cipher for cipher in ciphers if cipher)
    return ""


def _derive_program_name(finding: InvictiFinding) -> str:
    if not finding.name:
        return ""
    match = re.search(r"\(([^)]+)\)", finding.name)
    if match:
        return match.group(1).strip()
    return ""


def _weak_list_already_present(description: str, weak_list: str) -> bool:
    if not description or not weak_list:
        return False

    def _norm(value: str) -> str:
        return re.sub(r"\s+", " ", value).strip().lower()

    if _norm(weak_list) in _norm(description):
        return True

    items = [line.strip() for line in weak_list.splitlines() if line.strip()]
    if not items:
        return False
    probe = items[:3]
    hits = sum(1 for item in probe if item and item in description)
    if hits >= 2:
        return True

    if (
        ("취약한 암호화 목록" in description or "취약한 암호화 알고리즘 목록" in description)
        and items
        and items[0] in description
    ):
        return True

    return False


def finalize_summary(summary: str, finding: InvictiFinding) -> str:
    cleaned = _clean_summary(summary)
    cleaned = _normalize_summary_phrase(cleaned)
    if cleaned:
        return cleaned
    return _fallback_summary(finding)


def _clean_summary(text: str) -> str:
    if not text:
        return ""
    cleaned = re.sub(r"[\r\n]+", " ", str(text)).strip()
    cleaned = re.sub(r"^[\d\.\)\-\s]+", "", cleaned)
    cleaned = cleaned.strip(" .")
    if len(cleaned) > 20:
        cleaned = cleaned[:20].rstrip(". ")
    return cleaned


def _fallback_summary(finding: InvictiFinding) -> str:
    name = finding.name.lower()
    if "cipher" in name or "암호" in finding.name:
        return "약한 암호 활성화"
    if "tls" in name:
        return "TLS 취약 설정"
    if "hsts" in name:
        return "HSTS 미적용"
    cleaned = re.sub(r"\[.*?\]", "", finding.name)
    cleaned = re.sub(r"\(.*?\)", "", cleaned)
    cleaned = re.sub(r"[^가-힣A-Za-z0-9\s]", " ", cleaned).strip()
    if len(cleaned) > 20:
        cleaned = cleaned.split()[0]
    return cleaned or "보안 취약점"


def _normalize_summary_phrase(summary: str) -> str:
    if not summary:
        return ""
    lower = summary.lower()
    if "cipher" in lower or "암호" in summary:
        return "약한 암호 활성화"
    if "tls" in lower:
        return "TLS 취약 설정"
    if "hsts" in lower:
        return "HSTS 미적용"
    return summary


def finalize_description(
    description: str,
    finding: InvictiFinding,
    context: Dict[str, str] | None,
) -> str:
    context_map = context or {}
    cleaned = _clean_description(description)
    if not cleaned:
        cleaned = _fallback_description(finding, context_map)
    return _ensure_description_context(cleaned, finding, context_map)


def _clean_description(text: str) -> str:
    if not text:
        return ""
    lines: List[str] = []
    for raw in str(text).splitlines():
        stripped = raw.strip()
        if not stripped:
            continue
        stripped = re.sub(r"^[\d\.\)\-\s]+", "", stripped)
        if stripped:
            lines.append(stripped)
    cleaned = " ".join(lines)
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip()
    return cleaned


def _ensure_description_context(
    description: str,
    finding: InvictiFinding,
    context: Dict[str, str],
) -> str:
    segments: List[str] = [description] if description else []

    if finding.path and finding.path not in description:
        segments.append(f"대상 경로: {finding.path}")

    current_version = context.get("현재 버전") or context.get("현재버전")
    latest_version = context.get("최신 버전") or context.get("최신버전")
    if current_version and f"현재 버전" not in description and current_version not in description:
        segments.append(f"현재 버전: {current_version}")
    if latest_version and f"최신 버전" not in description and latest_version not in description:
        segments.append(f"최신 버전: {latest_version}")

    weak_list = context.get("암호화 목록") or context.get("암호화목록")
    if weak_list and not _weak_list_already_present(description, weak_list):
        segments.append(f"취약한 암호화 목록: \n{weak_list}")

    if finding.evidence_text and finding.evidence_text not in description:
        segments.append(f"Invicti 증적 요약: {finding.evidence_text}")

    combined = "\n".join(segment for segment in segments if segment)
    return combined.strip()


def _fallback_description(
    finding: InvictiFinding,
    context: Dict[str, str],
) -> str:
    lines = [f"{finding.name} 취약점이 확인되었습니다."]
    if finding.path:
        lines.append(f"대상 경로: {finding.path}")
    current_version = context.get("현재 버전") or context.get("현재버전")
    latest_version = context.get("최신 버전") or context.get("최신버전")
    weak_list = context.get("암호화 목록") or context.get("암호화목록")
    if current_version:
        lines.append(f"현재 버전: {current_version}")
    if latest_version:
        lines.append(f"최신 버전: {latest_version}")
    if weak_list:
        lines.append(f"취약한 암호화 목록: {weak_list}")
    elif finding.evidence_text:
        lines.append(f"Invicti 증적 요약: {finding.evidence_text}")
    return "\n".join(lines)


def finalize_recommendation(recommendation: str) -> str:
    cleaned = _clean_sentence(recommendation)
    if cleaned:
        return cleaned
    return "취약점을 제거하기 위한 보안 구성을 즉시 적용하고 재검증을 수행하세요."


def _clean_sentence(text: str) -> str:
    if not text:
        return ""
    cleaned = re.sub(r"[\r\n]+", " ", str(text)).strip()
    cleaned = re.sub(r"^[\d\.\)\-\s]+", "", cleaned)
    return cleaned.strip()
