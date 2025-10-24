from __future__ import annotations

import logging
from typing import Dict, Protocol

import pandas as pd
from bs4 import BeautifulSoup
from fastapi import HTTPException, UploadFile
from openai import OpenAI

from ..ai_generation import GeneratedCsv
from ..prompt_config import PromptConfigService
from ..prompt_request_log import PromptRequestLogService
from .ai import SecurityReportAI
from . import criteria, exporter, parser
from .criteria import (
    CRITERIA_FILE_NAME,
    CriteriaFormatError,
    CriteriaValidationError,
)
from .models import InvictiFinding, StandardizedFinding

logger = logging.getLogger(__name__)


class DriveServicePort(Protocol):
    async def download_shared_security_criteria(
        self,
        *,
        google_id: str | None,
        file_name: str,
    ) -> bytes:
        ...

    async def get_project_exam_number(
        self,
        *,
        project_id: str,
        google_id: str | None,
    ) -> str:
        ...


class SecurityReportService:
    def __init__(
        self,
        *,
        drive_service: DriveServicePort,
        prompt_config_service: PromptConfigService,
        prompt_request_log_service: PromptRequestLogService | None,
        openai_client: OpenAI,
    ) -> None:
        self._drive_service = drive_service
        self._ai = SecurityReportAI(
            prompt_config_service=prompt_config_service,
            prompt_request_log_service=prompt_request_log_service,
            openai_client=openai_client,
        )

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
        csv_dataframe = exporter.build_csv_view(dataframe)
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

        findings = parser.parse_findings(soup)
        if not findings:
            raise HTTPException(
                status_code=422,
                detail="분석 가능한 Invicti 결함 정보를 찾지 못했습니다.",
            )

        criteria_df = await self._load_security_criteria(google_id)

        standardized: list[StandardizedFinding] = []
        criteria_modified = False
        for finding in findings:
            placeholder_values = parser.build_placeholder_values(finding, soup)
            mapped, updated = await self._map_finding_to_standard(
                finding,
                criteria_df,
                placeholder_values,
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

        merged = parser.merge_similar_findings(standardized)

        if criteria_modified:
            logger.info("Security criteria augmented with AI-generated rules during processing.")

        return exporter.build_dataframe(merged)

    async def _load_security_criteria(self, google_id: str | None) -> pd.DataFrame:
        criteria_bytes = await self._drive_service.download_shared_security_criteria(
            google_id=google_id,
            file_name=CRITERIA_FILE_NAME,
        )
        try:
            return criteria.load_criteria_from_bytes(criteria_bytes)
        except CriteriaFormatError as exc:
            logger.exception("Failed to load shared security criteria spreadsheet.")
            raise HTTPException(status_code=500, detail="결함 판단 기준표를 읽지 못했습니다.") from exc
        except CriteriaValidationError as exc:
            raise HTTPException(
                status_code=500,
                detail="결함 판단 기준표 형식이 올바르지 않습니다.",
            ) from exc

    async def _map_finding_to_standard(
        self,
        finding: InvictiFinding,
        criteria_df: pd.DataFrame,
        placeholder_values: Dict[str, str],
        *,
        project_id: str,
    ) -> tuple[StandardizedFinding | None, bool]:
        best_match = criteria.find_best_match(finding.name, criteria_df["Invicti 결과"])
        if best_match is None:
            generated = await self._generate_new_standard(
                finding,
                placeholder_values,
                project_id=project_id,
            )
            if generated is None:
                return None, False
            criteria.append_generated_rule(criteria_df, generated)
            return generated, True

        match_value, score, row_index = best_match
        record = criteria_df.iloc[row_index]
        excluded = criteria.is_excluded(record.get("결함 제외 여부"))

        if excluded:
            return None, False

        summary_template = str(record.get("결함 요약") or match_value)
        description_template = str(record.get("결함 설명") or "")
        recommendation_template = criteria.determine_recommendation(record)

        summary_text = await self._ai.fill_template_field(
            summary_template,
            finding,
            project_id=project_id,
            placeholder_values=placeholder_values,
        )
        description_text = await self._ai.fill_template_field(
            description_template,
            finding,
            project_id=project_id,
            placeholder_values=placeholder_values,
        )
        recommendation_text = await self._ai.fill_template_field(
            recommendation_template,
            finding,
            project_id=project_id,
            placeholder_values=placeholder_values,
        )

        summary_final = parser.finalize_summary(summary_text or match_value, finding)
        description_final = parser.finalize_description(
            description_text,
            finding,
            placeholder_values,
        )
        recommendation_final = parser.finalize_recommendation(recommendation_text)

        return (
            StandardizedFinding(
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
            ),
            False,
        )

    async def _generate_new_standard(
        self,
        finding: InvictiFinding,
        placeholder_values: Dict[str, str],
        *,
        project_id: str,
    ) -> StandardizedFinding | None:
        prompt_payload = await self._ai.generate_new_finding_payload(
            finding,
            project_id=project_id,
            placeholder_values=placeholder_values,
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

        summary_final = parser.finalize_summary(summary, finding)
        description_final = parser.finalize_description(
            description,
            finding,
            placeholder_values,
        )
        recommendation_final = parser.finalize_recommendation(recommendation)

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
