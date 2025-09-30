from __future__ import annotations

import io
import json
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import JSONResponse, StreamingResponse

from ..dependencies import get_ai_generation_service, get_drive_service
from ..services.ai_generation import AIGenerationService
from ..services.google_drive import GoogleDriveService

router = APIRouter()


_REQUIRED_MENU_DOCUMENTS: Dict[str, List[Dict[str, str]]] = {
    "feature-list": [
        {"id": "user-manual", "label": "사용자 매뉴얼"},
        {"id": "configuration", "label": "형상 이미지"},
        {"id": "vendor-feature-list", "label": "업체 기능리스트"},
    ],
    "testcase-generation": [
        {"id": "user-manual", "label": "사용자 매뉴얼"},
        {"id": "configuration", "label": "형상 이미지"},
        {"id": "vendor-feature-list", "label": "기능리스트"},
    ],
}


@router.post("/drive/gs/setup")
async def ensure_gs_folder(
    google_id: Optional[str] = Query(None, description="Drive 작업에 사용할 Google 사용자 식별자 (sub)"),
    drive_service: GoogleDriveService = Depends(get_drive_service),
) -> JSONResponse:
    result = await drive_service.ensure_drive_setup(google_id)
    return JSONResponse(result)


@router.post("/drive/projects")
async def create_drive_project(
    folder_id: Optional[str] = Form(None),
    files: List[UploadFile] = File(...),
    google_id: Optional[str] = Query(None, description="Drive 작업에 사용할 Google 사용자 식별자 (sub)"),
    drive_service: GoogleDriveService = Depends(get_drive_service),
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
    file_metadata: Optional[str] = Form(
        None, description="업로드된 파일에 대한 메타데이터(JSON 배열)"
    ),
    ai_generation_service: AIGenerationService = Depends(get_ai_generation_service),
) -> StreamingResponse:
    uploads = files or []
    metadata_entries: List[Dict[str, Any]] = []
    if file_metadata:
        try:
            parsed = json.loads(file_metadata)
        except json.JSONDecodeError as exc:  # pragma: no cover - 방어적 처리
            raise HTTPException(status_code=422, detail="파일 메타데이터 형식이 올바르지 않습니다.") from exc

        if not isinstance(parsed, list):
            raise HTTPException(status_code=422, detail="파일 메타데이터 형식이 올바르지 않습니다.")

        for entry in parsed:
            if not isinstance(entry, dict):
                raise HTTPException(status_code=422, detail="파일 메타데이터 형식이 올바르지 않습니다.")
            metadata_entries.append(entry)

    if metadata_entries and len(metadata_entries) != len(uploads):
        raise HTTPException(status_code=422, detail="파일 메타데이터와 업로드된 파일 수가 일치하지 않습니다.")

    required_docs = _REQUIRED_MENU_DOCUMENTS.get(menu_id, [])
    if required_docs:
        if not metadata_entries:
            raise HTTPException(status_code=422, detail="필수 문서 정보가 누락되었습니다.")

        doc_counts = {doc["id"]: 0 for doc in required_docs}
        for entry in metadata_entries:
            role = entry.get("role")
            if role == "required":
                doc_id = entry.get("id")
                if doc_id not in doc_counts:
                    raise HTTPException(status_code=422, detail="알 수 없는 필수 문서 유형입니다.")
                doc_counts[doc_id] += 1
            elif role == "additional":
                description = str(entry.get("description", "")).strip()
                if not description:
                    raise HTTPException(status_code=422, detail="추가 업로드한 문서의 종류를 입력해 주세요.")
            else:
                raise HTTPException(status_code=422, detail="파일 메타데이터 형식이 올바르지 않습니다.")

        missing = [doc["label"] for doc in required_docs if doc_counts.get(doc["id"], 0) == 0]
        if missing:
            raise HTTPException(
                status_code=422,
                detail=f"다음 필수 문서를 업로드해 주세요: {', '.join(missing)}",
            )
    else:
        for entry in metadata_entries:
            role = entry.get("role")
            if role == "additional":
                description = str(entry.get("description", "")).strip()
                if not description:
                    raise HTTPException(status_code=422, detail="추가 업로드한 문서의 종류를 입력해 주세요.")
            elif role not in {"required", "additional"}:
                raise HTTPException(status_code=422, detail="파일 메타데이터 형식이 올바르지 않습니다.")

    result = await ai_generation_service.generate_csv(
        project_id=project_id,
        menu_id=menu_id,
        uploads=uploads,
        metadata=metadata_entries,
    )

    headers = {
        "Content-Disposition": f'attachment; filename="{result.filename}"',
        "Cache-Control": "no-store",
    }

    return StreamingResponse(io.BytesIO(result.content), media_type="text/csv", headers=headers)
