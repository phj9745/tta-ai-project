from __future__ import annotations

import io
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import pandas as pd
from bs4 import BeautifulSoup
from fastapi import HTTPException, UploadFile
from openai import OpenAI
from thefuzz import process as fuzz_process

from .ai_generation import AIGenerationService
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


class SecurityReportService:
    def __init__(self, drive_service: GoogleDriveService, openai_client: OpenAI) -> None:
        self._drive_service = drive_service
        self._openai_client = openai_client

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
            mapped, updated = await self._map_finding_to_standard(finding, criteria_df)
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
            raise HTTPException(status_code=500, detail="공유 결함 기준표를 읽지 못했습니다.") from exc

        missing_columns = [
            column for column in _CRITERIA_REQUIRED_COLUMNS if column not in criteria_df.columns
        ]
        if missing_columns:
            logger.error(
                "Security criteria spreadsheet missing required columns: %s",
                ", ".join(missing_columns),
            )
            raise HTTPException(status_code=500, detail="공유 결함 기준표 형식이 올바르지 않습니다.")

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
        return extracted_rows

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
        excluded = str(record["결함 제외 여부"]).strip() == "1"

        description_template = str(record["결함 설명"] or "")
        if self._has_placeholders(description_template):
            description_text = await self._fill_template_with_ai(
                template=description_template,
                finding=finding,
            )
        else:
            description_text = description_template

        return StandardizedFinding(
            invicti_name=finding.name,
            path=finding.path,
            severity=finding.severity,
            severity_rank=finding.severity_rank,
            anchor_id=finding.anchor_id,
            summary=str(record["결함 요약"] or match_value),
            recommendation=self._determine_recommendation(record),
            category=str(record["품질특성"] or ""),
            occurrence=str(record["발생빈도"] or ""),
            description=description_text,
            excluded=excluded,
            raw_details=finding.description_text,
            ai_notes={
                "match_score": score,
                "matched_criteria": match_value,
            },
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
            logger.warning("AI prompt for new finding returned no data; skipping.")
            return None

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
            response = self._openai_client.responses.create(
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
            "AI 메모",
        ]
        return dataframe.reindex(columns=columns)
