from __future__ import annotations

import csv
import io
import random
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import JSONResponse, StreamingResponse

from ..container import drive_service

router = APIRouter()


_SAMPLE_REPORTS: Dict[str, List[Dict[str, Any]]] = {
    "feature-tc": [
        {
            "filename": "feature_tc_summary.csv",
            "rows": [
                ["기능", "테스트 케이스 ID", "우선순위", "작성 상태"],
                ["사용자 로그인", "TC-FT-001", "높음", "초안"],
                ["회원가입", "TC-FT-002", "중간", "검토 중"],
                ["비밀번호 재설정", "TC-FT-003", "높음", "초안"],
            ],
        },
        {
            "filename": "feature_tc_traceability.csv",
            "rows": [
                ["요구사항 ID", "기능", "테스트 케이스"],
                ["REQ-101", "사용자 로그인", "TC-FT-011"],
                ["REQ-102", "2단계 인증", "TC-FT-012"],
                ["REQ-103", "계정 잠금", "TC-FT-013"],
            ],
        },
    ],
    "defect-report": [
        {
            "filename": "defect_overview.csv",
            "rows": [
                ["결함 ID", "심각도", "모듈", "현황"],
                ["BUG-210", "중대", "결제", "재현됨"],
                ["BUG-214", "치명", "주문", "조치 필요"],
                ["BUG-219", "경미", "알림", "검토 중"],
            ],
        },
        {
            "filename": "defect_root_cause.csv",
            "rows": [
                ["결함 ID", "원인", "개선 계획"],
                ["BUG-301", "API 응답 지연", "캐시 전략 개선"],
                ["BUG-304", "권한 검증 누락", "인증 미들웨어 보강"],
                ["BUG-308", "입력 검증 부족", "프론트 검증 추가"],
            ],
        },
    ],
    "security-report": [
        {
            "filename": "security_findings.csv",
            "rows": [
                ["취약점 ID", "위험도", "카테고리", "조치 현황"],
                ["SEC-110", "높음", "인증", "완료"],
                ["SEC-118", "중간", "데이터 암호화", "진행 중"],
                ["SEC-124", "중간", "로그 분석", "미착수"],
            ],
        },
        {
            "filename": "security_controls.csv",
            "rows": [
                ["통제 항목", "상태", "담당자"],
                ["계정 잠금 정책", "적용", "김보안"],
                ["접근 로그 모니터링", "미적용", "이감사"],
                ["취약점 정기 점검", "진행 중", "박분석"],
            ],
        },
    ],
    "performance-report": [
        {
            "filename": "performance_summary.csv",
            "rows": [
                ["시나리오", "TPS", "평균 응답시간(ms)", "성공률"],
                ["로그인", "180", "230", "99.1%"],
                ["장바구니", "120", "340", "98.4%"],
                ["결제", "75", "410", "96.8%"],
            ],
        },
        {
            "filename": "performance_trend.csv",
            "rows": [
                ["측정 구간", "CPU 사용률(%)", "메모리 사용량(MB)"],
                ["00:00-00:15", "45", "612"],
                ["00:15-00:30", "51", "648"],
                ["00:30-00:45", "63", "712"],
            ],
        },
    ],
}


@router.post("/drive/gs/setup")
async def ensure_gs_folder(
    google_id: Optional[str] = Query(None, description="Drive 작업에 사용할 Google 사용자 식별자 (sub)"),
) -> JSONResponse:
    result = await drive_service.ensure_drive_setup(google_id)
    return JSONResponse(result)


@router.post("/drive/projects")
async def create_drive_project(
    folder_id: Optional[str] = Form(None),
    files: List[UploadFile] = File(...),
    google_id: Optional[str] = Query(None, description="Drive 작업에 사용할 Google 사용자 식별자 (sub)"),
) -> Dict[str, Any]:
    if not files:
        raise HTTPException(status_code=422, detail="최소 한 개의 파일을 업로드해주세요.")

    invalid_files: List[str] = []
    for upload in files:
        filename = upload.filename or "업로드된 파일"
        if not filename.lower().endswith(".pdf"):
            invalid_files.append(filename)

    if invalid_files:
        detail = ", ".join(invalid_files)
        raise HTTPException(status_code=422, detail=f"PDF 파일만 업로드할 수 있습니다: {detail}")

    return await drive_service.create_project(
        folder_id=folder_id,
        files=files,
        google_id=google_id,
    )


@router.post("/drive/projects/{project_id}/generate")
async def generate_project_asset(
    project_id: str,
    menu_id: str = Form(..., description="생성할 메뉴 ID"),
    files: Optional[List[UploadFile]] = File(None),
) -> StreamingResponse:
    sample_options = _SAMPLE_REPORTS.get(menu_id)
    if not sample_options:
        raise HTTPException(status_code=404, detail="지원하지 않는 생성 메뉴입니다.")

    uploads = files or []
    if not uploads:
        raise HTTPException(status_code=422, detail="업로드된 자료가 없습니다. 파일을 추가해 주세요.")

    # FastAPI는 업로드 스트림을 자동으로 정리하지만, 명시적으로 읽어
    # 업로드 완료를 기다리도록 한다.
    for upload in uploads:
        try:
            await upload.read()
        finally:
            await upload.close()

    selection = random.choice(sample_options)
    rows = selection.get("rows", [])
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    for row in rows:
        writer.writerow(row)

    buffer.seek(0)
    encoded = buffer.getvalue().encode("utf-8-sig")
    stream = io.BytesIO(encoded)

    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    filename = selection.get("filename", "report.csv")
    generated_name = f"{project_id}_{timestamp}_{filename}"

    headers = {
        "Content-Disposition": f'attachment; filename="{generated_name}"',
        "Cache-Control": "no-store",
    }

    return StreamingResponse(stream, media_type="text/csv", headers=headers)
