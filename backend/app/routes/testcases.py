from __future__ import annotations

import io
from pathlib import Path
from typing import List

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from ..dependencies import get_ai_generation_service
from ..services.ai_generation import AIGenerationService
from ..services.excel_templates import testcases
from ..services.excel_templates.models import TESTCASE_EXPECTED_HEADERS
from ..services.excel_templates.utils import parse_csv_records

router = APIRouter(tags=["testcases"])

_TEMPLATE_ROOT = Path(__file__).resolve().parents[2] / "template"
_TESTCASE_TEMPLATE = _TEMPLATE_ROOT / "나.설계" / "GS-B-XX-XXXX 테스트케이스.xlsx"


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


class TestcaseGenerateResponse(BaseModel):
    rows: List[TestcaseRow]


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

    metadata = []
    for index, file in enumerate(files):
        metadata.append(
            {
                "role": "required" if index == 0 else "additional",
                "id": "user-manual" if index == 0 else None,
                "label": "사용자 매뉴얼" if index == 0 else "추가 문서",
                "description": "테스트케이스 생성 참고 문서" if index > 0 else "",
            }
        )

    generated = await ai_generation_service.generate_csv(
        project_id="single-project",
        menu_id="testcase-generation",
        uploads=files,
        metadata=metadata,
    )

    rows = _rows_from_csv_text(generated.csv_text)
    if project_overview.strip() and rows:
        rows[0].note = f"프로젝트 개요: {project_overview.strip()}"

    return TestcaseGenerateResponse(rows=rows)




@router.get("/api/testcases/health")
@router.get("/testcases/health")
@router.get("/health")
async def testcase_health() -> dict[str, object]:
    return {
        "status": "ok",
        "service": "testcases",
        "paths": [
            "/api/testcases/generate",
            "/testcases/generate",
            "/generate",
            "/api/testcases/export",
            "/testcases/export",
            "/export",
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
