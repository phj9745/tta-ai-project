from __future__ import annotations

import io
import re
from collections import Counter
from pathlib import Path
from typing import Any, List

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from ..container import Container
from ..dependencies import get_ai_generation_service, get_container
from ..services.ai_generation import AIGenerationService
from ..services.excel_templates import testcases
from ..services.excel_templates.models import TESTCASE_EXPECTED_HEADERS
from ..services.excel_templates.utils import parse_csv_records

router = APIRouter(tags=["testcases"])

_TEMPLATE_ROOT = Path(__file__).resolve().parents[2] / "template"
_TESTCASE_TEMPLATE = _TEMPLATE_ROOT / "나.설계" / "GS-B-XX-XXXX 테스트케이스.xlsx"
_TC_ID_PATTERN = re.compile(r"^TC-\d{3}-\d{3}$")


class TestcaseRow(BaseModel):
    major_category: str = Field("", alias="majorCategory")
    middle_category: str = Field("", alias="middleCategory")
    minor_category: str = Field("", alias="minorCategory")
    testcase_id: str = Field("", alias="testcaseId")
    scenario: str = Field("", alias="scenario")
    input: str = Field("", alias="input")
    expected: str = Field("", alias="expected")
    result: str = Field("", alias="result")
    detail: str = Field("", alias="detail")
    note: str = Field("", alias="note")


class GenerationDiagnostics(BaseModel):
    stages: list[str] = Field(default_factory=list)
    generated_count: int = Field(0, alias="generatedCount")
    id_reassigned_count: int = Field(0, alias="idReassignedCount")
    prompt_menu_id: str = Field("testcase-generation", alias="promptMenuId")


class TestcaseGenerateResponse(BaseModel):
    rows: List[TestcaseRow]
    warnings: list[str] = Field(default_factory=list)
    diagnostics: GenerationDiagnostics = Field(default_factory=GenerationDiagnostics)


class TestcaseExportRequest(BaseModel):
    rows: List[TestcaseRow]


def _rows_from_csv_text(csv_text: str) -> List[TestcaseRow]:
    try:
        records = parse_csv_records(csv_text, TESTCASE_EXPECTED_HEADERS)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    rows: List[TestcaseRow] = []
    for record in records:
        rows.append(
            TestcaseRow(
                majorCategory=record.get("대분류", ""),
                middleCategory=record.get("중분류", ""),
                minorCategory=record.get("소분류", ""),
                testcaseId=record.get("테스트 케이스 ID", ""),
                scenario=record.get("테스트 시나리오", ""),
                input=record.get("입력(사전조건 포함)", ""),
                expected=record.get("기대 출력(사후조건 포함)", ""),
                result=record.get("테스트 결과", ""),
                detail=record.get("상세 테스트 결과", ""),
                note=record.get("비고", ""),
            )
        )
    return rows


def _assign_missing_testcase_ids(rows: list[TestcaseRow]) -> int:
    reassigned = 0
    group_index: dict[tuple[str, str, str], int] = {}
    group_counts: dict[tuple[str, str, str], int] = {}

    for row in rows:
        group = (
            (row.major_category or "-").strip(),
            (row.middle_category or "-").strip(),
            (row.minor_category or "-").strip(),
        )
        if group not in group_index:
            group_index[group] = len(group_index) + 1
            group_counts[group] = 0

        group_counts[group] += 1
        if not _TC_ID_PATTERN.match((row.testcase_id or "").strip()):
            row.testcase_id = f"TC-{group_index[group]:03d}-{group_counts[group]:03d}"
            reassigned += 1

        if not row.result.strip():
            row.result = "미실행"

    return reassigned


def _build_quality_warnings(rows: list[TestcaseRow], id_reassigned_count: int) -> list[str]:
    warnings: list[str] = []

    if not rows:
        return ["생성 결과가 비어 있습니다. 업로드 문서 내용을 확인해 주세요."]

    if id_reassigned_count > 0:
        warnings.append(f"테스트 케이스 ID {id_reassigned_count}건을 표준 형식(TC-XXX-YYY)으로 자동 보정했습니다.")

    missing_scenario = sum(1 for row in rows if not row.scenario.strip())
    missing_input = sum(1 for row in rows if not row.input.strip())
    missing_expected = sum(1 for row in rows if not row.expected.strip())

    if missing_scenario:
        warnings.append(f"테스트 시나리오가 비어 있는 항목이 {missing_scenario}건 있습니다.")
    if missing_input:
        warnings.append(f"입력(사전조건 포함)이 비어 있는 항목이 {missing_input}건 있습니다.")
    if missing_expected:
        warnings.append(f"기대 출력(사후조건 포함)이 비어 있는 항목이 {missing_expected}건 있습니다.")

    normalized_scenarios = [" ".join(row.scenario.split()).lower() for row in rows if row.scenario.strip()]
    duplicate_scenarios = [text for text, count in Counter(normalized_scenarios).items() if count > 1]
    if duplicate_scenarios:
        warnings.append(f"중복 가능성이 있는 테스트 시나리오가 {len(duplicate_scenarios)}개 있습니다.")

    return warnings


def _csv_from_rows(rows: List[TestcaseRow]) -> str:
    lines = ["|".join(TESTCASE_EXPECTED_HEADERS)]
    for row in rows:
        payload = row.model_dump(by_alias=True)
        values = [
            payload["majorCategory"],
            payload["middleCategory"],
            payload["minorCategory"],
            payload["testcaseId"],
            payload["scenario"],
            payload["input"],
            payload["expected"],
            payload["result"],
            payload["detail"],
            payload["note"],
        ]
        escaped = ['"' + value.replace('"', '""') + '"' if any(ch in value for ch in ['|', '\n', '"']) else value for value in values]
        lines.append("|".join(escaped))
    return "\n".join(lines)


@router.post("/api/testcases/generate", response_model=TestcaseGenerateResponse)
@router.post("/testcases/generate", response_model=TestcaseGenerateResponse)
@router.post("/generate", response_model=TestcaseGenerateResponse)
async def generate_testcases(
    files: List[UploadFile] = File(...),
    project_overview: str = Form(""),
    ai_generation_service: AIGenerationService = Depends(get_ai_generation_service),
) -> TestcaseGenerateResponse:
    if not files:
        raise HTTPException(status_code=422, detail="최소 1개 문서를 업로드해 주세요.")

    stages: list[str] = ["upload_received"]

    metadata: list[dict[str, Any]] = []
    for index, _ in enumerate(files):
        metadata.append(
            {
                "role": "required" if index == 0 else "additional",
                "id": "user-manual" if index == 0 else None,
                "label": "사용자 매뉴얼" if index == 0 else "추가 문서",
                "description": "테스트케이스 생성 참고 문서" if index > 0 else "",
            }
        )

    try:
        generated = await ai_generation_service.generate_csv(
            project_id="single-project",
            menu_id="testcase-generation",
            uploads=files,
            metadata=metadata,
        )
    except HTTPException as exc:
        detail = str(exc.detail)
        if "지원하지 않는 생성 메뉴" in detail:
            raise HTTPException(status_code=500, detail="테스트케이스 생성 메뉴 설정이 누락되었습니다. 관리자에게 문의해 주세요.") from exc
        if "Anthropic API 키가 설정되어 있지 않습니다" in detail:
            raise HTTPException(status_code=500, detail="AI 생성 API 키가 설정되어 있지 않습니다. 관리자 설정 후 다시 시도해 주세요.") from exc
        raise

    stages.extend(["ai_csv_generated", "csv_parsed"])

    rows = _rows_from_csv_text(generated.csv_text)
    reassigned_count = _assign_missing_testcase_ids(rows)
    stages.append("post_validation_applied")

    if project_overview.strip() and rows:
        rows[0].note = f"프로젝트 개요: {project_overview.strip()}"

    warnings = _build_quality_warnings(rows, reassigned_count)

    return TestcaseGenerateResponse(
        rows=rows,
        warnings=warnings,
        diagnostics=GenerationDiagnostics(
            stages=stages,
            generatedCount=len(rows),
            idReassignedCount=reassigned_count,
            promptMenuId="testcase-generation",
        ),
    )


@router.get("/api/testcases/health")
@router.get("/testcases/health")
@router.get("/health")
async def testcase_health(container: Container = Depends(get_container)) -> dict[str, object]:
    prompt_available = True
    prompt_error: str | None = None
    try:
        container.prompt_config_service.get_runtime_prompt("testcase-generation")
    except Exception as exc:  # pragma: no cover
        prompt_available = False
        prompt_error = str(exc)

    api_key_configured = bool(container.settings.anthropic_api_key.strip())

    checks = {
        "apiKeyConfigured": api_key_configured,
        "testcasePromptConfigured": prompt_available,
        "promptError": prompt_error,
    }

    return {
        "status": "ok" if all(value is True or key == "promptError" for key, value in checks.items()) else "degraded",
        "service": "testcases",
        "paths": [
            "/api/testcases/generate",
            "/testcases/generate",
            "/generate",
            "/api/testcases/export",
            "/testcases/export",
            "/export",
        ],
        "checks": checks,
        "removedFeatures": [
            "google-drive",
            "oauth-login",
            "feature-list-workflow-ui",
            "defect-report",
            "security-report",
            "performance-report",
            "prompt-admin-ui",
        ],
    }


@router.post("/api/testcases/export")
@router.post("/testcases/export")
@router.post("/export")
async def export_testcases(payload: TestcaseExportRequest) -> StreamingResponse:
    if not payload.rows:
        raise HTTPException(status_code=422, detail="내보낼 테스트케이스가 없습니다.")

    csv_text = _csv_from_rows(payload.rows)

    try:
        template_bytes = _TESTCASE_TEMPLATE.read_bytes()
    except OSError as exc:
        raise HTTPException(status_code=500, detail="테스트케이스 템플릿을 읽을 수 없습니다.") from exc

    workbook = testcases.populate_testcase_list(template_bytes, csv_text)
    headers = {
        "Content-Disposition": "attachment; filename*=UTF-8''testcases.xlsx",
        "Cache-Control": "no-store",
    }
    return StreamingResponse(
        io.BytesIO(workbook),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers=headers,
    )
