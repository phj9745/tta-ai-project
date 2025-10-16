from __future__ import annotations

import io
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, TypedDict

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import JSONResponse, StreamingResponse

from ..dependencies import get_ai_generation_service, get_drive_service
from ..services.ai_generation import AIGenerationService
from ..services.google_drive import GoogleDriveService
from ..services.excel_templates import populate_defect_report

router = APIRouter()


class RequiredDocument(TypedDict, total=False):
    id: str
    label: str
    allowed_extensions: List[str]


_REQUIRED_MENU_DOCUMENTS: Dict[str, List[RequiredDocument]] = {
    "feature-list": [
        {
            "id": "user-manual",
            "label": "사용자 매뉴얼",
            "allowed_extensions": ["pdf", "docx", "xlsx"],
        },
        {
            "id": "configuration",
            "label": "형상 이미지",
            "allowed_extensions": ["png", "jpg", "jpeg"],
        },
        {
            "id": "vendor-feature-list",
            "label": "업체 기능리스트",
            "allowed_extensions": ["pdf", "docx", "xlsx"],
        },
    ],
    "testcase-generation": [
        {
            "id": "user-manual",
            "label": "사용자 매뉴얼",
            "allowed_extensions": ["pdf", "docx", "xlsx"],
        },
        {
            "id": "configuration",
            "label": "형상 이미지",
            "allowed_extensions": ["png", "jpg", "jpeg"],
        },
        {
            "id": "vendor-feature-list",
            "label": "기능리스트",
            "allowed_extensions": ["pdf", "docx", "xlsx"],
        },
    ],
}

_TEMPLATE_ROOT = Path(__file__).resolve().parents[2] / "template"
_DEFECT_REPORT_TEMPLATE = _TEMPLATE_ROOT / "다.수행" / "GS-B-2X-XXXX 결함리포트 v1.0.xlsx"


def _decode_text(raw: bytes) -> str:
    for encoding in ("utf-8", "cp949"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="ignore")


_DEFECT_PATTERN = re.compile(r"(?:^|\n)\s*(\d+)\.(.*?)(?=(?:\n\s*\d+\.)|\Z)", re.S)


def _extract_defect_entries(text: str) -> List[Dict[str, str]]:
    stripped = text.strip()
    if not stripped:
        return []

    matches = list(_DEFECT_PATTERN.finditer(stripped))
    entries: List[Dict[str, str]] = []
    if matches:
        for match in matches:
            index_str, body = match.groups()
            try:
                index_value = int(index_str)
            except ValueError:
                continue
            cleaned = " ".join(body.strip().split())
            if not cleaned:
                continue
            entries.append({"index": index_value, "text": cleaned})
    else:
        lines: Sequence[str] = [line.strip() for line in stripped.splitlines() if line.strip()]
        for idx, line in enumerate(lines, start=1):
            entries.append({"index": idx, "text": line})
    return entries


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
        if not filename.lower().endswith(".docx"):
            invalid_files.append(filename)

    if invalid_files:
        detail = ", ".join(invalid_files)
        raise HTTPException(status_code=422, detail=f"DOCX 파일만 업로드할 수 있습니다: {detail}")

    return await drive_service.create_project(
        folder_id=folder_id,
        files=files,
        google_id=google_id,
    )


@router.post("/drive/projects/{project_id}/defect-report/formalize")
async def formalize_defect_report(
    project_id: str,
    file: UploadFile = File(..., description="결함 메모 TXT 파일"),
    ai_generation_service: AIGenerationService = Depends(get_ai_generation_service),
) -> Dict[str, Any]:
    try:
        raw_bytes = await file.read()
    finally:
        await file.close()

    if not raw_bytes:
        raise HTTPException(status_code=422, detail="업로드된 파일이 비어 있습니다.")

    decoded = _decode_text(raw_bytes)
    entries = _extract_defect_entries(decoded)
    if not entries:
        raise HTTPException(
            status_code=422,
            detail="결함 목록을 찾을 수 없습니다. '1. 항목' 형태로 작성된 TXT 파일을 업로드해 주세요.",
        )

    normalized = await ai_generation_service.formalize_defect_notes(
        project_id=project_id,
        entries=entries,
    )

    normalized.sort(key=lambda item: item.index)

    return {
        "defects": [
            {
                "index": item.index,
                "originalText": item.original_text,
                "polishedText": item.polished_text,
            }
            for item in normalized
        ]
    }


@router.post("/drive/projects/{project_id}/generate")
async def generate_project_asset(
    project_id: str,
    menu_id: str = Form(..., description="생성할 메뉴 ID"),
    files: Optional[List[UploadFile]] = File(None),
    file_metadata: Optional[str] = Form(
        None, description="업로드된 파일에 대한 메타데이터(JSON 배열)"
    ),
    google_id: Optional[str] = Query(None, description="Drive 작업에 사용할 Google 사용자 식별자 (sub)"),
    ai_generation_service: AIGenerationService = Depends(get_ai_generation_service),
    drive_service: GoogleDriveService = Depends(get_drive_service),
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

        required_docs_by_id = {doc["id"]: doc for doc in required_docs}
        for upload, entry in zip(uploads, metadata_entries):
            if entry.get("role") != "required":
                continue

            doc_id = entry.get("id")
            if doc_id not in required_docs_by_id:
                raise HTTPException(status_code=422, detail="알 수 없는 필수 문서 유형입니다.")

            doc_info = required_docs_by_id[doc_id]
            allowed_extensions = [
                ext.lower()
                for ext in doc_info.get("allowed_extensions", [])
                if isinstance(ext, str) and ext
            ]
            if not allowed_extensions:
                continue

            extension = ""
            if upload.filename and "." in upload.filename:
                extension = upload.filename.rsplit(".", 1)[-1].lower()

            if extension not in allowed_extensions:
                allowed_text = ", ".join(ext.upper() for ext in allowed_extensions)
                label = doc_info.get("label", doc_id)
                filename = upload.filename or label
                raise HTTPException(
                    status_code=422,
                    detail=f"{label}은(는) {allowed_text} 파일만 업로드할 수 있습니다: {filename}",
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

    await drive_service.apply_csv_to_spreadsheet(
        project_id=project_id,
        menu_id=menu_id,
        csv_text=result.csv_text,
        google_id=google_id,
    )

    if menu_id == "defect-report":
        if not _DEFECT_REPORT_TEMPLATE.exists():
            raise HTTPException(status_code=500, detail="결함 리포트 템플릿을 찾을 수 없습니다.")

        try:
            template_bytes = _DEFECT_REPORT_TEMPLATE.read_bytes()
        except FileNotFoundError as exc:  # pragma: no cover - unexpected
            raise HTTPException(status_code=500, detail="결함 리포트 템플릿을 읽을 수 없습니다.") from exc

        try:
            workbook_bytes = populate_defect_report(template_bytes, result.csv_text)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        safe_stem = Path(result.filename).stem or "defect-report"
        download_name = f"{safe_stem}.xlsx"
        headers = {
            "Content-Disposition": f'attachment; filename="{download_name}"',
            "Cache-Control": "no-store",
        }
        return StreamingResponse(
            io.BytesIO(workbook_bytes),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers=headers,
        )

    headers = {
        "Content-Disposition": f'attachment; filename="{result.filename}"',
        "Cache-Control": "no-store",
    }

    return StreamingResponse(io.BytesIO(result.content), media_type="text/csv", headers=headers)
