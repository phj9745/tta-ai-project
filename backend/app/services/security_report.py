from __future__ import annotations

import asyncio
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

from .ai_generation import AIGenerationService, GeneratedCsv
from .google_drive import GoogleDriveService
from .prompt_config import PromptConfig, PromptConfigService
from .prompt_request_log import PromptRequestLogService

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

_PROMPT_TEMPLATE_PATTERN = re.compile(r"\{\{\s*([A-Za-z0-9_]+)\s*\}\}")
_DEFAULT_SECURITY_SYSTEM_PROMPT = (
    "당신은 Invicti HTML 보고서를 분석하여 보안 결함을 표준 템플릿에 맞게 요약하는 한국어 보안 분석가입니다. "
    "응답은 항상 JSON 형식이어야 합니다."
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
    def __init__(
        self,
        drive_service: GoogleDriveService,
        prompt_config_service: PromptConfigService,
        prompt_request_log_service: PromptRequestLogService | None,
        openai_client: OpenAI,
    ) -> None:
        self._drive_service = drive_service
        self._prompt_config_service = prompt_config_service
        self._prompt_request_log_service = prompt_request_log_service
        self._openai_client = openai_client

    async def generate_csv_report(
        self,
        *,
        invicti_upload: UploadFile,
        project_id: str,
        google_id: str | None,
    ) -> GeneratedCsv:
        dataframe = await self.process_invicti_report(
            invicti_upload=invicti_upload,
            project_id=project_id,
            google_id=google_id,
        )
        csv_dataframe = self._build_csv_view(dataframe)
        csv_text = csv_dataframe.to_csv(index=False)
        encoded = csv_text.encode("utf-8-sig")

        project_number = await self._drive_service.get_project_exam_number(
            project_id=project_id,
            google_id=google_id,
        )
        filename = f"{project_number} 보안성 결함리포트 v1.0.csv"

        return GeneratedCsv(filename=filename, content=encoded, csv_text=csv_text)

    async def process_invicti_report(
        self,
        *,
        invicti_upload: UploadFile,
        project_id: str,
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
            mapped, updated = await self._map_finding_to_standard(
                finding,
                criteria_df,
                soup,
                project_id=project_id,
            )
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

        # 병합: 동일 유형은 대표 항목(첫 경로)만 남기고 병합
        standardized = self._merge_similar_findings(standardized)

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
        *,
        project_id: str,
    ) -> Tuple[Optional[StandardizedFinding], bool]:
        best_match = self._find_best_criteria(finding.name, criteria_df["Invicti 결과"])
        if best_match is None:
            generated = await self._generate_new_standard(
                finding,
                soup,
                project_id=project_id,
            )
            if generated is None:
                return None, False
            self._append_generated_rule(criteria_df, generated)
            return generated, True

        match_value, score, row_index = best_match
        record = criteria_df.iloc[row_index]
        excluded = self._is_excluded(record.get("결함 제외 여부"))

        if excluded:
            return None, False

        context_values = self._build_placeholder_values(finding, soup)
        summary_template = str(record.get("결함 요약") or match_value)
        summary_text = await self._render_template_field(
            summary_template,
            finding,
            soup,
            project_id=project_id,
            context=context_values,
        )

        description_template = str(record.get("결함 설명") or "")
        description_text = await self._render_template_field(
            description_template,
            finding,
            soup,
            project_id=project_id,
            context=context_values,
        )

        recommendation_template = self._determine_recommendation(record)
        recommendation_text = await self._render_template_field(
            recommendation_template,
            finding,
            soup,
            project_id=project_id,
            context=context_values,
        )

        summary_final = self._finalize_summary(summary_text or match_value, finding, context_values)
        description_final = self._finalize_description(description_text, finding, context_values)
        recommendation_final = self._finalize_recommendation(recommendation_text)

        return StandardizedFinding(
            invicti_name=finding.name,
            path=finding.path,
            severity=finding.severity,
            severity_rank=finding.severity_rank,
            anchor_id=finding.anchor_id,
            summary=summary_final,
            recommendation=recommendation_final,
            category="보안성",
            occurrence="A",
            description=description_final,
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

    async def _generate_new_standard(
        self,
        finding: InvictiFinding,
        soup: BeautifulSoup,
        *,
        project_id: str,
    ) -> Optional[StandardizedFinding]:
        context_values = self._build_placeholder_values(finding, soup)
        prompt_payload = await self._call_openai_for_json(
            prompt_id="security-new-finding",
            finding=finding,
            context_data=context_values,
            project_id=project_id,
        )
        if not prompt_payload:
            logger.warning(
                "AI prompt for new finding returned no data; using fallback.",
                extra={"finding": finding.name},
            )
            prompt_payload = {}

        summary = prompt_payload.get("summary") or ""
        description = prompt_payload.get("description") or ""
        recommendation = prompt_payload.get("recommendation") or ""

        summary_final = self._finalize_summary(summary, finding, context_values)
        description_final = self._finalize_description(description, finding, context_values)
        recommendation_final = self._finalize_recommendation(recommendation)

        return StandardizedFinding(
            invicti_name=finding.name,
            path=finding.path,
            severity=finding.severity,
            severity_rank=finding.severity_rank,
            anchor_id=finding.anchor_id,
            summary=summary_final,
            recommendation=recommendation_final,
            category="보안성",
            occurrence="A",
            description=description_final,
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
        placeholders: Iterable[str],
        project_id: str,
        context: Dict[str, str] | None = None,
    ) -> str:
        if not placeholders:
            return template

        prompt_payload = await self._call_openai_for_json(
            prompt_id="security-template-fill",
            finding=finding,
            placeholders=placeholders,
            context_data=context,
            project_id=project_id,
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
        context_data: Dict[str, str] | None = None,
        project_id: str | None,
    ) -> Dict[str, Any]:
        prompts = self._build_prompt(
            prompt_id=prompt_id,
            finding=finding,
            placeholders=placeholders,
            context_data=context_data,
        )
        if prompts is None:
            return {}

        system_prompt = ""
        user_prompt = ""
        for message in prompts:
            role = str(message.get("role", ""))
            content = str(message.get("content", ""))
            if role == "system":
                system_prompt = content
            elif role == "user":
                user_prompt = content

        if self._prompt_request_log_service is not None and project_id:
            context_summary = f"{finding.name or '알 수 없는 결함'} (severity: {finding.severity or '?'})"
            try:
                self._prompt_request_log_service.record_request(
                    project_id=project_id,
                    menu_id="security-report",
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    context_summary=context_summary,
                )
            except Exception:  # pragma: no cover - logging failures must not break flow
                logger.exception(
                    "Failed to record security prompt request",
                    extra={"project_id": project_id, "prompt_id": prompt_id},
                )

        try:
            response = await asyncio.to_thread(
                self._openai_client.responses.create,
                model="gpt-4.1-mini",
                input=prompts,
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
        context_data: Dict[str, str] | None,
    ) -> List[Dict[str, str]] | None:
        placeholder_text = ""
        if placeholders:
            placeholder_text = ", ".join([str(item) for item in placeholders if str(item)])

        context_lines = ""
        if context_data:
            entries: List[str] = []
            seen_keys: set[str] = set()
            for key, value in context_data.items():
                if not isinstance(value, str):
                    continue
                stripped_value = value.strip()
                if not stripped_value:
                    continue
                normalized_key = re.sub(r"\s+", "", str(key)).lower()
                if normalized_key in seen_keys:
                    continue
                seen_keys.add(normalized_key)
                entries.append(f"- {key}: {stripped_value}")
            context_lines = "\n".join(entries)

        try:
            config = self._prompt_config_service.get_runtime_prompt("security-report")
        except KeyError as exc:  # pragma: no cover - configuration should always exist
            logger.exception("Security report prompt configuration is missing.")
            raise HTTPException(status_code=500, detail="보안성 리포트 프롬프트 구성을 불러오지 못했습니다.") from exc

        values = self._build_prompt_values(
            finding=finding,
            context_lines=context_lines,
            placeholder_text=placeholder_text,
        )

        if prompt_id == "security-new-finding":
            system = self._render_template(config.system_prompt, values).strip() or _DEFAULT_SECURITY_SYSTEM_PROMPT
            parts, details_ref, _ = self._assemble_prompt_parts(
                config,
                values,
                use_sections=True,
                use_heading=True,
                use_intro=True,
                use_closing=True,
                use_warning=True,
                track_placeholders=False,
            )
            if not details_ref:
                parts.append(values["finding_details_block"])
            user = "\n\n".join(part for part in parts if part)
        elif prompt_id == "security-template-fill":
            system = self._render_template(config.system_prompt, values).strip() or _DEFAULT_SECURITY_SYSTEM_PROMPT
            parts, details_ref, placeholders_ref = self._assemble_prompt_parts(
                config,
                values,
                use_sections=False,
                use_heading=False,
                use_intro=False,
                use_closing=True,
                use_warning=True,
                track_placeholders=True,
            )
            if not placeholders_ref:
                placeholder_line = values["placeholder_list"] or "(플레이스홀더 없음)"
                parts.insert(0, f"플레이스홀더: {placeholder_line}")
            if not details_ref:
                parts.append(values["finding_details_block"])
            user = "\n\n".join(part for part in parts if part)
        else:
            return None

        return [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]

    def _assemble_prompt_parts(
        self,
        config: PromptConfig,
        values: Dict[str, str],
        *,
        use_sections: bool,
        use_heading: bool,
        use_intro: bool,
        use_closing: bool,
        use_warning: bool,
        track_placeholders: bool,
    ) -> Tuple[List[str], bool, bool]:
        parts: List[str] = []
        details_referenced = False
        placeholders_referenced = False

        base, base_details, base_placeholders = self._render_fragment(
            config.user_prompt,
            values,
            track_details=True,
            track_placeholders=track_placeholders,
        )
        if base:
            parts.append(base)
        details_referenced = details_referenced or base_details
        placeholders_referenced = placeholders_referenced or base_placeholders

        if use_sections:
            for section in config.user_prompt_sections:
                if not section.enabled:
                    continue
                label, label_details, label_placeholders = self._render_fragment(
                    section.label,
                    values,
                    track_details=True,
                    track_placeholders=track_placeholders,
                )
                content, content_details, content_placeholders = self._render_fragment(
                    section.content,
                    values,
                    track_details=True,
                    track_placeholders=track_placeholders,
                )
                combined = "\n".join(part for part in [label, content] if part).strip()
                if combined:
                    parts.append(combined)
                details_referenced = details_referenced or label_details or content_details
                placeholders_referenced = (
                    placeholders_referenced or label_placeholders or content_placeholders
                )

        if use_heading:
            heading, heading_details, heading_placeholders = self._render_fragment(
                config.scaffolding.attachments_heading,
                values,
                track_details=True,
                track_placeholders=track_placeholders,
            )
            if heading:
                parts.append(heading)
            details_referenced = details_referenced or heading_details
            placeholders_referenced = placeholders_referenced or heading_placeholders

        if use_intro:
            intro, intro_details, intro_placeholders = self._render_fragment(
                config.scaffolding.attachments_intro,
                values,
                track_details=True,
                track_placeholders=track_placeholders,
            )
            if intro:
                parts.append(intro)
            details_referenced = details_referenced or intro_details
            placeholders_referenced = placeholders_referenced or intro_placeholders

        if use_closing:
            closing, closing_details, closing_placeholders = self._render_fragment(
                config.scaffolding.closing_note,
                values,
                track_details=True,
                track_placeholders=track_placeholders,
            )
            if closing:
                parts.append(closing)
            details_referenced = details_referenced or closing_details
            placeholders_referenced = placeholders_referenced or closing_placeholders

        if use_warning:
            warning, warning_details, warning_placeholders = self._render_fragment(
                config.scaffolding.format_warning,
                values,
                track_details=True,
                track_placeholders=track_placeholders,
            )
            if warning:
                parts.append(warning)
            details_referenced = details_referenced or warning_details
            placeholders_referenced = placeholders_referenced or warning_placeholders

        return parts, details_referenced, placeholders_referenced

    def _render_fragment(
        self,
        template: str,
        values: Dict[str, str],
        *,
        track_details: bool,
        track_placeholders: bool,
    ) -> Tuple[str, bool, bool]:
        raw = (template or "").strip()
        if not raw:
            return "", False, False
        details_referenced = track_details and "{{finding_details_block}}" in template
        placeholders_referenced = track_placeholders and "{{placeholder_list}}" in template
        rendered = self._render_template(raw, values).strip()
        return rendered, details_referenced, placeholders_referenced

    def _render_template(self, template: str, values: Dict[str, str]) -> str:
        def _replace(match: re.Match[str]) -> str:
            key = match.group(1)
            return str(values.get(key, ""))

        return _PROMPT_TEMPLATE_PATTERN.sub(_replace, template)

    def _build_prompt_values(
        self,
        *,
        finding: InvictiFinding,
        context_lines: str,
        placeholder_text: str,
    ) -> Dict[str, str]:
        context_block = context_lines or "- (제공된 추가 정보 없음)"
        finding_details = self._format_finding_details_block(finding, context_block)
        return {
            "finding_name": finding.name or "",
            "finding_severity": finding.severity or "",
            "finding_path": finding.path or "",
            "finding_description": finding.description_text or "",
            "finding_evidence": finding.evidence_text or "없음",
            "context_block": context_block,
            "finding_details_block": finding_details,
            "placeholder_list": placeholder_text or "",
        }

    @staticmethod
    def _format_finding_details_block(finding: InvictiFinding, context_block: str) -> str:
        name = finding.name or "-"
        severity = finding.severity or "-"
        path = finding.path or "-"
        description = finding.description_text or "-"
        evidence = finding.evidence_text or "없음"
        return (
            f"제목: {name}\n"
            f"위험도: {severity}\n"
            f"경로: {path}\n"
            f"상세 설명:\n{description}\n"
            f"증적:\n{evidence}\n"
            f"추가 참고 정보:\n{context_block}"
        )

    def _is_excluded(self, value: Any) -> bool:
        text = str(value or "").strip().lower()
        return text in {"1", "true", "yes", "y", "t", "on"}

    async def _render_template_field(
        self,
        template: str,
        finding: InvictiFinding,
        soup: BeautifulSoup,
        *,
        project_id: str,
        context: Dict[str, str] | None = None,
    ) -> str:
        if not template:
            return template

        if not self._has_placeholders(template):
            return template

        filled, remaining = self._fill_template_with_known_placeholders(
            template,
            finding,
            soup,
            context_values=context,
        )
        if not remaining:
            return filled

        ai_filled = await self._fill_template_with_ai(
            template=filled,
            finding=finding,
            placeholders=remaining,
            project_id=project_id,
            context=context,
        )
        return ai_filled if ai_filled else filled

    def _fill_template_with_known_placeholders(
        self,
        template: str,
        finding: InvictiFinding,
        soup: BeautifulSoup,
        context_values: Dict[str, str] | None = None,
    ) -> Tuple[str, List[str]]:
        placeholders = self._extract_placeholders(template)
        if not placeholders:
            return template, []

        values = context_values if context_values is not None else self._build_placeholder_values(finding, soup)
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
    
    def _weak_list_already_present(self, description: str, weak_list: str) -> bool:
        if not description or not weak_list:
            return False

        def _norm(s: str) -> str:
            return re.sub(r"\s+", " ", s).strip().lower()

        # 1) 전체 문자열 정규화 비교
        if _norm(weak_list) in _norm(description):
            return True

        # 2) 목록 항목들 중 앞쪽 2~3개가 본문에 동시에 존재하면 포함된 것으로 간주
        items = [ln.strip() for ln in weak_list.splitlines() if ln.strip()]
        if not items:
            return False
        probe = items[:3]  # 앞에서 최대 3개까지 확인
        hits = sum(1 for it in probe if it and it in description)
        if hits >= 2:
            return True

        # 3) 헤더 문구 + 첫 항목 조합 체크
        if ("취약한 암호화 목록" in description or "취약한 암호화 알고리즘 목록" in description) and items[0] in description:
            return True

        return False

    def _finalize_summary(
        self,
        summary: str,
        finding: InvictiFinding,
        context: Dict[str, str] | None,
    ) -> str:
        cleaned = self._clean_summary(summary)
        cleaned = self._normalize_summary_phrase(cleaned)
        if cleaned:
            return cleaned
        return self._fallback_summary(finding)

    def _clean_summary(self, text: str) -> str:
        if not text:
            return ""
        cleaned = re.sub(r"[\r\n]+", " ", str(text)).strip()
        cleaned = re.sub(r"^[\d\.\)\-\s]+", "", cleaned)
        cleaned = cleaned.strip(" .")
        if len(cleaned) > 20:
            cleaned = cleaned[:20].rstrip(". ")
        return cleaned

    def _fallback_summary(self, finding: InvictiFinding) -> str:
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

    def _normalize_summary_phrase(self, summary: str) -> str:
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

    def _finalize_description(
        self,
        description: str,
        finding: InvictiFinding,
        context: Dict[str, str] | None,
    ) -> str:
        context_map = context or {}
        cleaned = self._clean_description(description)
        if not cleaned:
            cleaned = self._fallback_description(finding, context_map)
        return self._ensure_description_context(cleaned, finding, context_map)

    def _clean_description(self, text: str) -> str:
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
        self,
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
        if weak_list and not self._weak_list_already_present(description, weak_list):
            segments.append(f"취약한 암호화 목록: \n{weak_list}")

        if finding.evidence_text and finding.evidence_text not in description:
            segments.append(f"Invicti 증적 요약: {finding.evidence_text}")

        combined = "\n".join(segment for segment in segments if segment)
        return combined.strip()

    def _fallback_description(
        self,
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

    def _finalize_recommendation(self, recommendation: str) -> str:
        cleaned = self._clean_sentence(recommendation)
        if cleaned:
            return cleaned
        return "취약점을 제거하기 위한 보안 구성을 즉시 적용하고 재검증을 수행하세요."

    def _clean_sentence(self, text: str) -> str:
        if not text:
            return ""
        cleaned = re.sub(r"[\r\n]+", " ", str(text)).strip()
        cleaned = re.sub(r"^[\d\.\)\-\s]+", "", cleaned)
        return cleaned.strip()

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

    def _merge_similar_findings(
        self,
        findings: Sequence[StandardizedFinding],
    ) -> List[StandardizedFinding]:
        """
        동일 취약 유형(같은 Invicti 결과/요약/위험도레벨/조치 가이드)에서 URL/파라미터만 다른 항목을 하나로 합칩니다.
        병합 시 대표 path는 해당 그룹에서 처음 등장한 path(맨 앞 항목의 path)만 사용합니다.
        결함 설명은 대표 항목의 description을 그대로 유지합니다.
        """
        merged_map: Dict[Tuple[str, str, int, str], StandardizedFinding] = {}
        first_path_seen: Dict[Tuple[str, str, int, str], str] = {}

        for f in findings:
            key = (
                (f.invicti_name or "").strip().lower(),
                (f.summary or "").strip(),
                int(f.severity_rank),
                (f.recommendation or "").strip(),
            )
            if key not in merged_map:
                # 첫 항목을 대표로 그대로 보관
                merged_map[key] = f
                first_path_seen[key] = f.path or ""
            else:
                # 이미 존재하면 ai_notes 병합(선택적) 및 대표 path 보존 (변경하지 않음)
                existing = merged_map[key]
                # preserve existing.ai_notes but add info that another occurrence existed
                existing.ai_notes = dict(existing.ai_notes or {})
                # 증거로서 간단히 카운트/기록 추가 (기존 값 유지)
                existing.ai_notes.setdefault("merged_count", 1)
                existing.ai_notes["merged_count"] = existing.ai_notes.get("merged_count", 1) + 1
                merged_map[key] = existing

        # 반환 시, path는 그룹에서 첫으로 본 path만 사용
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
            # 빈 경우에도 요구된 최종 컬럼 세트만 노출
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
                    # 요청에 따라 아래 컬럼은 CSV에서 제거됨:
                    # "Invicti 결과", "위험도", "발생경로", "조치 가이드", "원본 세부내용",
                    "매핑 유형",
                ]
            )

        output = dataframe.copy()
        output.insert(0, "순번", [str(index) for index in range(1, len(output) + 1)])
        output.insert(1, "시험환경 OS", ["시험환경 모든 OS"] * len(output))

        # '결함정도'에서 직접 매핑하여 최종 '결함 정도' 생성 (중간 '위험도' 컬럼 생성하지 않음)
        severity_map = {
            "Critical": "H",
            "High": "H",
            "Medium": "M",
            "Low": "L",
            "Info": "L",
            "Informational": "L",
        }
        raw_sev = output["결함정도"].fillna("").astype(str)
        output["결함 정도"] = raw_sev.map(severity_map).fillna("M")

        output["발생 빈도"] = output["발생빈도"].fillna("").astype(str)
        output["품질 특성"] = output["품질특성"].fillna("").astype(str)
        output["결함 설명"] = output["결함 설명"].fillna("").astype(str)
        output["결함 요약"] = output["결함 요약"].fillna("").astype(str)

        # 내부적으로는 존재하더라도 CSV에 포함하지 않을 특정 컬럼들에 대해 안전하게 처리
        if "조치 가이드" in output.columns:
            output["조치 가이드"] = output["조치 가이드"].fillna("").astype(str)
        if "발생경로" in output.columns:
            output["발생경로"] = output["발생경로"].fillna("").astype(str)
        if "Invicti 결과" in output.columns:
            output["Invicti 결과"] = output["Invicti 결과"].fillna("").astype(str)
        if "원본 세부내용" in output.columns:
            output["원본 세부내용"] = output["원본 세부내용"].fillna("").astype(str)

        output["업체 응답"] = ""
        output["수정여부"] = ""
        output["비고"] = "보안성 시험 결과 참고"

        # 최종 CSV 컬럼: 요청된 5개는 제외
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
            "매핑 유형",
        ]
        return output.reindex(columns=columns)
