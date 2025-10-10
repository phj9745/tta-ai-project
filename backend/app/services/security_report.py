from __future__ import annotations

import asyncio
import io
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import pandas as pd
from bs4 import BeautifulSoup
from fastapi import HTTPException, UploadFile
from openai import OpenAI
from thefuzz import process as fuzz_process

from .ai_generation import AIGenerationService, GeneratedCsv
from .google_drive import GoogleDriveService

logger = logging.getLogger(__name__)

_SEVERITY_RANKING: Dict[str, int] = {
    "informational": 0,
    "info": 0,
    "low": 1,
    "medium": 2,
    "moderate": 2,
    "high": 3,
    "critical": 4,
    "urgent": 4,
}

_CRITERIA_FILE_NAME = "보안성 결함판단기준표 v1.0.xlsx"
_CRITERIA_REQUIRED_COLUMNS = (
    "Invicti 결과",
    "결함 요약",
    "결함정도",
    "발생빈도",
    "품질특성",
    "결함 설명",
    "결함 제외 여부",
)


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


class SecurityReportService:
    def __init__(self, drive_service: GoogleDriveService, openai_client: OpenAI) -> None:
        self._drive_service = drive_service
        self._openai_client = openai_client

    async def generate_csv_report(
        self,
        *,
        invicti_upload: UploadFile,
        project_id: str,
        google_id: str | None,
    ) -> GeneratedCsv:
        source_filename = invicti_upload.filename or "invicti-report.html"
        dataframe = await self.process_invicti_report(
            invicti_upload=invicti_upload,
            google_id=google_id,
        )
        csv_dataframe = self._build_csv_view(dataframe)
        csv_text = csv_dataframe.to_csv(index=False)
        encoded = csv_text.encode("utf-8-sig")

        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        stem = Path(source_filename).stem
        if not stem:
            stem = "invicti-report"
        safe_stem = re.sub(r"[^A-Za-z0-9_-]+", "_", stem).strip("_") or "invicti-report"
        filename = f"{safe_stem}_security-report_{timestamp}.csv"

        return GeneratedCsv(filename=filename, content=encoded, csv_text=csv_text)

    async def process_invicti_report(
        self,
        *,
        invicti_upload: UploadFile,
        google_id: str | None,
    ) -> pd.DataFrame:
        raw_bytes = await invicti_upload.read()
        if not raw_bytes:
            raise HTTPException(status_code=400, detail="Invicti 보고서 파일이 비어 있습니다.")
        await invicti_upload.close()

        try:
            soup = BeautifulSoup(raw_bytes, "html.parser")
        except Exception as exc:  # pragma: no cover - BeautifulSoup internals
            logger.exception("Failed to parse Invicti HTML report.")
            raise HTTPException(status_code=422, detail="Invicti 보고서를 파싱하지 못했습니다.") from exc

        findings = self._parse_invicti_findings(soup)
        if not findings:
            raise HTTPException(status_code=422, detail="분석 가능한 Invicti 결함 정보를 찾지 못했습니다.")

        criteria_df = await self._load_security_criteria(google_id)

        standardized: List[StandardizedFinding] = []
        criteria_modified = False
        for finding in findings:
            mapped, updated = await self._map_finding_to_standard(finding, criteria_df, soup)
            criteria_modified = criteria_modified or updated
            if mapped is None:
                logger.info(
                    "Invicti finding could not be mapped; skipping.",
                    extra={
                        "name": finding.name,
                        "path": finding.path,
                        "severity": finding.severity,
                    },
                )
                continue
            if mapped.excluded:
                logger.debug(
                    "Invicti finding excluded by shared criteria.",
                    extra={"name": finding.name, "path": finding.path},
                )
                continue
            standardized.append(mapped)

        if not standardized:
            raise HTTPException(status_code=422, detail="매칭된 결함이 없어 리포트를 생성할 수 없습니다.")

        if criteria_modified:
            logger.info("Security criteria augmented with AI-generated rules during processing.")

        return self._build_dataframe(standardized)

    async def _load_security_criteria(self, google_id: str | None) -> pd.DataFrame:
        criteria_bytes = await self._drive_service.download_shared_security_criteria(
            google_id=google_id,
            file_name=_CRITERIA_FILE_NAME,
        )
        try:
            criteria_df = pd.read_excel(io.BytesIO(criteria_bytes))
        except Exception as exc:  # pragma: no cover - pandas error path
            logger.exception("Failed to load shared security criteria spreadsheet.")
            raise HTTPException(status_code=500, detail="결함 판단 기준표를 읽지 못했습니다.") from exc

        missing_columns = [
            column for column in _CRITERIA_REQUIRED_COLUMNS if column not in criteria_df.columns
        ]
        if missing_columns:
            logger.error(
                "Security criteria spreadsheet missing required columns: %s",
                ", ".join(missing_columns),
            )
            raise HTTPException(status_code=500, detail="결함 판단 기준표 형식이 올바르지 않습니다.")

        criteria_df = criteria_df.copy()
        criteria_df["Invicti 결과"] = criteria_df["Invicti 결과"].astype(str).str.strip()
        criteria_df["결함 제외 여부"] = criteria_df["결함 제외 여부"].fillna(0).astype(str)
        return criteria_df

    def _parse_invicti_findings(self, soup: BeautifulSoup) -> List[InvictiFinding]:
        findings: List[InvictiFinding] = []
        summary_rows = self._extract_summary_rows(soup)

        for cells in summary_rows:
            name = cells.get("name")
            if not name:
                continue
            severity = self._normalize_severity(cells.get("severity", ""))
            severity_rank = _SEVERITY_RANKING.get(severity.lower(), -1)
            if severity_rank < _SEVERITY_RANKING["medium"]:
                continue
            path = cells.get("path", "")
            anchor_id = cells.get("anchor_id")

            description_html, description_text, evidence_text = self._extract_detail_section(
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

    def _extract_summary_rows(self, soup: BeautifulSoup) -> List[Dict[str, str]]:
        headers_map: Dict[int, str] = {}
        extracted_rows: List[Dict[str, str]] = []
        tables = soup.find_all("table")
        for table in tables:
            classes = table.get("class") or []
            if isinstance(classes, str):
                classes = [classes]
            if "detailed-scan" in classes:
                extracted_rows.extend(self._extract_detailed_scan_rows(table))
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
                idx: header.lower()
                for idx, header in enumerate(candidate_headers)
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

    def _extract_detailed_scan_rows(self, table: BeautifulSoup) -> List[Dict[str, str]]:
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
            severity = self._normalize_severity(severity)

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

    def _extract_detail_section(
        self,
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

    async def _map_finding_to_standard(
        self,
        finding: InvictiFinding,
        criteria_df: pd.DataFrame,
        soup: BeautifulSoup,
    ) -> Tuple[Optional[StandardizedFinding], bool]:
        best_match = self._find_best_criteria(finding.name, criteria_df["Invicti 결과"])
        if best_match is None:
            generated = await self._generate_new_standard(finding)
            if generated is None:
                return None, False
            self._append_generated_rule(criteria_df, generated)
            return generated, True

        match_value, score, row_index = best_match
        record = criteria_df.iloc[row_index]
        excluded = self._is_excluded(record.get("결함 제외 여부"))

        if excluded:
            return None, False

        summary_template = str(record.get("결함 요약") or match_value)
        summary_text = await self._render_template_field(summary_template, finding, soup)

        description_template = str(record.get("결함 설명") or "")
        description_text = await self._render_template_field(description_template, finding, soup)

        recommendation_template = self._determine_recommendation(record)
        recommendation_text = await self._render_template_field(recommendation_template, finding, soup)

        return StandardizedFinding(
            invicti_name=finding.name,
            path=finding.path,
            severity=finding.severity,
            severity_rank=finding.severity_rank,
            anchor_id=finding.anchor_id,
            summary=summary_text or match_value,
            recommendation=recommendation_text,
            category=str(record.get("품질특성") or ""),
            occurrence=str(record.get("발생빈도") or ""),
            description=description_text,
            excluded=False,
            raw_details=finding.description_text,
            ai_notes={
                "match_score": score,
                "matched_criteria": match_value,
            },
            source="criteria",
        ), False

    def _find_best_criteria(
        self,
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

    async def _generate_new_standard(self, finding: InvictiFinding) -> Optional[StandardizedFinding]:
        prompt_payload = await self._call_openai_for_json(
            prompt_id="security-new-finding",
            finding=finding,
        )
        if not prompt_payload:
            logger.warning(
                "AI prompt for new finding returned no data; using fallback.",
                extra={"finding": finding.name},
            )
            prompt_payload = {}

        summary = prompt_payload.get("summary") or finding.name
        description = prompt_payload.get("description") or finding.description_text
        recommendation = prompt_payload.get("recommendation") or ""
        category = prompt_payload.get("category") or ""
        occurrence = prompt_payload.get("occurrence") or ""

        return StandardizedFinding(
            invicti_name=finding.name,
            path=finding.path,
            severity=finding.severity,
            severity_rank=finding.severity_rank,
            anchor_id=finding.anchor_id,
            summary=summary,
            recommendation=recommendation,
            category=category,
            occurrence=occurrence,
            description=description,
            excluded=False,
            raw_details=finding.description_text,
            ai_notes={"generated": True},
            source="ai",
        )

    async def _fill_template_with_ai(
        self,
        *,
        template: str,
        finding: InvictiFinding,
    ) -> str:
        placeholders = self._extract_placeholders(template)
        if not placeholders:
            return template

        prompt_payload = await self._call_openai_for_json(
            prompt_id="security-template-fill",
            finding=finding,
            placeholders=placeholders,
        )
        if not prompt_payload:
            return template

        result = template
        for key, value in prompt_payload.items():
            token = f"[{key}]"
            result = result.replace(token, str(value))
        return result

    async def _call_openai_for_json(
        self,
        *,
        prompt_id: str,
        finding: InvictiFinding,
        placeholders: Iterable[str] | None = None,
    ) -> Dict[str, Any]:
        _ = prompts = self._build_prompt(
            prompt_id=prompt_id,
            finding=finding,
            placeholders=placeholders,
        )
        if prompts is None:
            return {}

        try:
            response = await asyncio.to_thread(
                self._openai_client.responses.create,
                model="gpt-4.1-mini",
                input=prompts,
                response_format={"type": "json_object"},
            )
        except Exception as exc:  # pragma: no cover - OpenAI client failure
            logger.exception("OpenAI call failed for prompt %s", prompt_id)
            return {}

        if not response:
            return {}

        text_payload = AIGenerationService._extract_response_text(response)
        if not text_payload:
            return {}
        return self._safe_json_loads(text_payload)

    def _build_prompt(
        self,
        *,
        prompt_id: str,
        finding: InvictiFinding,
        placeholders: Iterable[str] | None,
    ) -> List[Dict[str, str]] | None:
        placeholder_text = ""
        if placeholders:
            placeholder_text = ", ".join(sorted(placeholders))

        if prompt_id == "security-new-finding":
            system = (
                "당신은 Invicti HTML 보고서를 기반으로 "
                "보안 결함을 요약하고 표준 템플릿에 맞게 설명을 작성하는 한국어 보안 분석가입니다. "
                "JSON만 출력하세요."
            )
            user = (
                "다음 Invicti 결함 정보를 읽고 JSON 객체를 생성하세요. "
                "필드: summary(간단 요약), description(3문장 이상 상세 설명), "
                "recommendation(조치 가이드), category(품질 특성), occurrence(발생 빈도 권장 값). "
                f"\n\n제목: {finding.name}\n위험도: {finding.severity}\n경로: {finding.path}\n"
                f"상세 설명:\n{finding.description_text}\n"
                f"증적:\n{finding.evidence_text or '없음'}"
            )
        elif prompt_id == "security-template-fill":
            system = (
                "Invicti 보안 결함 상세를 기반으로 템플릿 플레이스홀더 값을 추출하는 보안 분석가입니다. "
                "JSON만 출력하세요."
            )
            user = (
                "다음 결함 설명을 읽고 지정된 플레이스홀더에 맞는 값을 추출하세요. "
                "존재하지 않는 경우 빈 문자열을 넣습니다.\n"
                f"플레이스홀더: {placeholder_text}\n\n"
                f"제목: {finding.name}\n위험도: {finding.severity}\n경로: {finding.path}\n"
                f"상세 설명:\n{finding.description_text}\n"
                f"증적:\n{finding.evidence_text or '없음'}"
            )
        else:
            return None

        return [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]

    def _is_excluded(self, value: Any) -> bool:
        text = str(value or "").strip().lower()
        return text in {"1", "true", "yes", "y", "t", "on"}

    async def _render_template_field(
        self,
        template: str,
        finding: InvictiFinding,
        soup: BeautifulSoup,
    ) -> str:
        if not template or not self._has_placeholders(template):
            return template

        filled, remaining = self._fill_template_with_known_placeholders(
            template,
            finding,
            soup,
        )
        if not remaining:
            return filled

        ai_filled = await self._fill_template_with_ai(
            template=filled,
            finding=finding,
            placeholders=remaining,
        )
        return ai_filled if ai_filled else filled

    def _fill_template_with_known_placeholders(
        self,
        template: str,
        finding: InvictiFinding,
        soup: BeautifulSoup,
    ) -> Tuple[str, List[str]]:
        placeholders = self._extract_placeholders(template)
        if not placeholders:
            return template, []

        values = self._build_placeholder_values(finding, soup)
        result = template
        unresolved: List[str] = []
        for key in placeholders:
            token = f"[{key}]"
            if key in values:
                value = values[key]
                replacement = str(value).strip()
                result = result.replace(token, replacement)
            else:
                unresolved.append(key)
        return result, unresolved

    def _build_placeholder_values(
        self,
        finding: InvictiFinding,
        soup: BeautifulSoup,
    ) -> Dict[str, str]:
        values: Dict[str, str] = {}

        program_name = self._derive_program_name(finding)
        if program_name:
            values["프로그램 명"] = program_name
            values["프로그램명"] = program_name

        versions = self._extract_version_details(soup, finding.anchor_id)
        if versions.get("current"):
            values["현재 버전"] = versions["current"]
            values["현재버전"] = versions["current"]
        if versions.get("latest"):
            values["최신 버전"] = versions["latest"]
            values["최신버전"] = versions["latest"]

        weak_ciphers = self._extract_weak_ciphers(soup, finding.anchor_id)
        if weak_ciphers:
            values["암호화 목록"] = weak_ciphers
            values["암호화목록"] = weak_ciphers

        if finding.path:
            values["URL"] = finding.path
            values["Url"] = finding.path

        return values

    def _extract_version_details(
        self,
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
        self,
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
            aria_label = h4.get("aria-label", "").strip()
            if aria_label != "지원되는 약한 암호 목록":
                continue
            ul_tag = h4.find_next_sibling("ul")
            if not ul_tag:
                return ""
            ciphers = [li.get_text(strip=True) for li in ul_tag.find_all("li")]
            return "\n".join(cipher for cipher in ciphers if cipher)
        return ""

    def _derive_program_name(self, finding: InvictiFinding) -> str:
        if not finding.name:
            return ""
        match = re.search(r"\(([^)]+)\)", finding.name)
        if match:
            return match.group(1).strip()
        return ""

    def _safe_json_loads(self, payload: str) -> Dict[str, Any]:
        import json

        try:
            return json.loads(payload)
        except json.JSONDecodeError:
            logger.warning("Failed to decode JSON payload from OpenAI response.")
            return {}

    def _determine_recommendation(self, record: pd.Series) -> str:
        recommendation = record.get("조치 가이드")
        if isinstance(recommendation, str):
            return recommendation.strip()
        return ""

    def _has_placeholders(self, template: str) -> bool:
        return bool(re.search(r"\[[^\[\]]+\]", template or ""))

    def _extract_placeholders(self, template: str) -> List[str]:
        return [match.strip("[]") for match in re.findall(r"\[[^\[\]]+\]", template or "")]

    def _normalize_severity(self, value: str) -> str:
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

    def _append_generated_rule(self, criteria_df: pd.DataFrame, finding: StandardizedFinding) -> None:
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

    def _build_dataframe(self, findings: Sequence[StandardizedFinding]) -> pd.DataFrame:
        rows = []
        for finding in findings:
            rows.append(
                {
                    "Invicti 결과": finding.invicti_name,
                    "결함 요약": finding.summary,
                    "결함정도": finding.severity,
                    "발생경로": finding.path,
                    "발생빈도": finding.occurrence,
                    "품질특성": finding.category,
                    "결함 설명": finding.description,
                    "조치 가이드": finding.recommendation,
                    "anchor_id": finding.anchor_id or "",
                    "원본 세부내용": finding.raw_details,
                    "AI 메모": finding.ai_notes,
                    "매핑 유형": "AI 생성" if finding.source == "ai" else "기준표 매칭",
                }
            )
        dataframe = pd.DataFrame(rows)
        columns = [
            "Invicti 결과",
            "결함 요약",
            "결함정도",
            "발생경로",
            "발생빈도",
            "품질특성",
            "결함 설명",
            "조치 가이드",
            "anchor_id",
            "원본 세부내용",
            "매핑 유형",
            "AI 메모",
        ]
        return dataframe.reindex(columns=columns)

    def _build_csv_view(self, dataframe: pd.DataFrame) -> pd.DataFrame:
        if dataframe.empty:
            return pd.DataFrame(
                columns=[
                    "순번",
                    "시험환경 OS",
                    "결함 요약",
                    "결함 정도",
                    "발생 빈도",
                    "품질 특성",
                    "결함 설명",
                    "업체 응답",
                    "수정여부",
                    "비고",
                    "Invicti 결과",
                    "위험도",
                    "발생경로",
                    "조치 가이드",
                    "원본 세부내용",
                    "매핑 유형",
                ]
            )

        output = dataframe.copy()
        output.insert(0, "순번", [str(index) for index in range(1, len(output) + 1)])
        output.insert(1, "시험환경 OS", ["시험환경 모든 OS"] * len(output))

        severity_map = {
            "Critical": "H",
            "High": "H",
            "Medium": "M",
            "Low": "L",
            "Info": "L",
            "Informational": "L",
        }
        output["위험도"] = output["결함정도"].fillna("").astype(str)
        output["결함 정도"] = output["위험도"].map(severity_map).fillna("M")
        output["발생 빈도"] = output["발생빈도"].fillna("").astype(str)
        output["품질 특성"] = output["품질특성"].fillna("").astype(str)
        output["결함 설명"] = output["결함 설명"].fillna("").astype(str)
        output["결함 요약"] = output["결함 요약"].fillna("").astype(str)
        output["조치 가이드"] = output["조치 가이드"].fillna("").astype(str)
        output["발생경로"] = output["발생경로"].fillna("").astype(str)
        output["Invicti 결과"] = output["Invicti 결과"].fillna("").astype(str)
        output["원본 세부내용"] = output["원본 세부내용"].fillna("").astype(str)

        output["업체 응답"] = ""
        output["수정여부"] = ""
        output["비고"] = "보안성 시험 결과 참고"

        columns = [
            "순번",
            "시험환경 OS",
            "결함 요약",
            "결함 정도",
            "발생 빈도",
            "품질 특성",
            "결함 설명",
            "업체 응답",
            "수정여부",
            "비고",
            "Invicti 결과",
            "위험도",
            "발생경로",
            "조치 가이드",
            "원본 세부내용",
            "매핑 유형",
        ]
        return output.reindex(columns=columns)
