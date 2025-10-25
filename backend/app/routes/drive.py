from __future__ import annotations

import base64
import csv
import io
import base64
import csv
import io
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, TypedDict
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, Response
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from ..dependencies import (
    get_ai_generation_service,
    get_drive_service,
    get_security_report_service,
)
from ..services.ai_generation import AIGenerationService
from ..services.google_drive import GoogleDriveService
from ..services.google_drive import feature_lists as drive_feature_lists
from ..services.security_report import SecurityReportService
from ..services.excel_templates import defect_report, testcases
from ..services.excel_templates import feature_list as feature_list_templates
from ..services.excel_templates.models import (
    DEFECT_REPORT_EXPECTED_HEADERS,
    TESTCASE_EXPECTED_HEADERS,
    DefectReportImage,
)

router = APIRouter()


class RequiredDocument(TypedDict, total=False):
    id: str
    label: str
    allowed_extensions: List[str]


class DefectCellRewriteRequest(BaseModel):
    column_key: str = Field(..., alias="columnKey", description="수정할 열 식별자")
    column_label: str | None = Field(
        None, alias="columnLabel", description="열 표시 이름 (선택)"
    )
    original_value: str | None = Field(
        None, alias="originalValue", description="현재 셀 값"
    )
    instructions: str = Field(..., description="GPT에게 전달할 수정 지시")
    row_values: Dict[str, str] | None = Field(
        None,
        alias="rowValues",
        description="해당 행의 다른 셀 값",
    )

    model_config = ConfigDict(populate_by_name=True)


class FeatureListRowModel(BaseModel):
    major_category: str = Field("", alias="majorCategory")
    middle_category: str = Field("", alias="middleCategory")
    minor_category: str = Field("", alias="minorCategory")
    feature_description: str = Field("", alias="featureDescription")

    model_config = ConfigDict(populate_by_name=True)


class FeatureListUpdateRequest(BaseModel):
    rows: List[FeatureListRowModel] = Field(default_factory=list)
    project_overview: str = Field("", alias="projectOverview")

    model_config = ConfigDict(populate_by_name=True)


class TestcaseFeatureListResponse(BaseModel):
    file_name: str = Field("", alias="fileName")
    project_overview: str = Field("", alias="projectOverview")
    rows: List[FeatureListRowModel] = Field(default_factory=list)

    model_config = ConfigDict(populate_by_name=True)


class TestcaseScenarioModel(BaseModel):
    scenario: str = Field("", description="테스트 시나리오 요약")
    input: str = Field("", description="입력 또는 사전조건")
    expected: str = Field("", description="기대 출력 또는 사후조건")


class TestcaseScenarioGroup(BaseModel):
    major_category: str = Field("", alias="majorCategory")
    middle_category: str = Field("", alias="middleCategory")
    minor_category: str = Field("", alias="minorCategory")
    feature_description: str = Field("", alias="featureDescription")
    scenarios: List[TestcaseScenarioModel] = Field(default_factory=list)

    model_config = ConfigDict(populate_by_name=True)


class TestcaseScenarioResponse(BaseModel):
    scenarios: List[TestcaseScenarioModel] = Field(default_factory=list)


class TestcaseFinalizeRowModel(BaseModel):
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

    model_config = ConfigDict(populate_by_name=True)


class TestcaseFinalizeRequest(BaseModel):
    project_overview: str | None = Field(None, alias="projectOverview")
    groups: List[TestcaseScenarioGroup] = Field(default_factory=list)

    model_config = ConfigDict(populate_by_name=True)


class TestcaseFinalizeResponse(BaseModel):
    csv_text: str = Field(..., alias="csvText")
    file_name: str = Field(..., alias="fileName")
    rows: List[TestcaseFinalizeRowModel]
    xlsx_base64: str = Field(..., alias="xlsxBase64")


class TestcaseExportRequest(BaseModel):
    rows: List[TestcaseFinalizeRowModel]

    model_config = ConfigDict(populate_by_name=True)


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
_TESTCASE_TEMPLATE = _TEMPLATE_ROOT / "나.설계" / "GS-B-XX-XXXX 테스트케이스.xlsx"

_STANDARD_TEMPLATE_POPULATORS: Dict[str, tuple[Path, Callable[[bytes, str], bytes]]] = {
    "testcase-generation": (_TESTCASE_TEMPLATE, testcases.populate_testcase_list),
}


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


def _build_attachment_header(filename: str, *, default_filename: str = "security-report.csv") -> str:
    ascii_fallback = re.sub(r"[^A-Za-z0-9._-]+", "_", filename)
    if not ascii_fallback or not re.search(r"[A-Za-z0-9]", ascii_fallback):
        ascii_fallback = default_filename
    quoted = quote(filename)
    return f'attachment; filename="{ascii_fallback}"; filename*=UTF-8\'\'{quoted}'


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
    security_report_service: SecurityReportService = Depends(get_security_report_service),
) -> Response:
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

    if menu_id == "security-report":
        if metadata_entries:
            raise HTTPException(status_code=422, detail="보안성 리포트에는 추가 파일 정보를 입력할 수 없습니다.")
        if len(uploads) != 1:
            raise HTTPException(status_code=422, detail="Invicti HTML 결과 파일을 1개 업로드해 주세요.")
        upload = uploads[0]
        filename = (upload.filename or "invicti-report").lower()
        if not filename.endswith(".html") and not filename.endswith(".htm"):
            raise HTTPException(status_code=422, detail="Invicti HTML 결과 파일만 업로드할 수 있습니다.")

        result = await security_report_service.generate_csv_report(
            invicti_upload=upload,
            project_id=project_id,
            google_id=google_id,
        )

        await drive_service.apply_csv_to_spreadsheet(
            project_id=project_id,
            menu_id=menu_id,
            csv_text=result.csv_text,
            google_id=google_id,
        )

        headers = {
            "Content-Disposition": _build_attachment_header(result.filename),
            "Cache-Control": "no-store",
        }

        return StreamingResponse(io.BytesIO(result.content), media_type="text/csv", headers=headers)

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

    spreadsheet_info = await drive_service.apply_csv_to_spreadsheet(
        project_id=project_id,
        menu_id=menu_id,
        csv_text=result.csv_text,
        google_id=google_id,
        project_overview=getattr(result, "project_overview", None),
    )

    if menu_id == "feature-list":
        if not spreadsheet_info or not spreadsheet_info.get("fileId"):
            raise HTTPException(status_code=500, detail="기능리스트 파일을 업데이트하지 못했습니다. 다시 시도해 주세요.")

        payload: Dict[str, Any] = {
            "status": "updated",
            "projectId": project_id,
            "fileId": spreadsheet_info.get("fileId"),
            "fileName": spreadsheet_info.get("fileName"),
            "modifiedTime": spreadsheet_info.get("modifiedTime"),
        }
        if "projectOverview" in spreadsheet_info:
            payload["projectOverview"] = spreadsheet_info.get("projectOverview")
        if getattr(result, "filename", None):
            payload["generatedFilename"] = result.filename

        return JSONResponse(payload)

    if menu_id in _STANDARD_TEMPLATE_POPULATORS:
        template_path, populate_template = _STANDARD_TEMPLATE_POPULATORS[menu_id]
        if not template_path.exists():
            raise HTTPException(status_code=500, detail="생성 결과 템플릿을 찾을 수 없습니다.")

        try:
            template_bytes = template_path.read_bytes()
        except FileNotFoundError as exc:  # pragma: no cover - unexpected
            raise HTTPException(status_code=500, detail="템플릿 파일을 읽을 수 없습니다.") from exc
        except OSError as exc:
            raise HTTPException(status_code=500, detail="템플릿 파일을 읽는 중 오류가 발생했습니다.") from exc

        try:
            workbook_bytes = populate_template(template_bytes, result.csv_text)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        safe_stem = Path(result.filename).stem or menu_id
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

    if menu_id == "defect-report":
        if not _DEFECT_REPORT_TEMPLATE.exists():
            raise HTTPException(status_code=500, detail="결함 리포트 템플릿을 찾을 수 없습니다.")

        try:
            template_bytes = _DEFECT_REPORT_TEMPLATE.read_bytes()
        except FileNotFoundError as exc:  # pragma: no cover - unexpected
            raise HTTPException(status_code=500, detail="결함 리포트 템플릿을 읽을 수 없습니다.") from exc

        image_map: Dict[int, List[DefectReportImage]] = {}
        if result.defect_images:
            for defect_index, uploads in result.defect_images.items():
                images: List[DefectReportImage] = []
                for upload in uploads:
                    images.append(
                        DefectReportImage(
                            file_name=upload.name,
                            content=upload.content,
                            content_type=upload.content_type,
                        )
                    )
                if not images:
                    continue
                try:
                    normalized_index = int(defect_index)
                except (TypeError, ValueError):
                    continue
                image_map[normalized_index] = images

        attachment_notes: Dict[int, List[str]] = {}
        if result.defect_summary:
            for entry in result.defect_summary:
                names = [att.file_name for att in entry.attachments if att.file_name]
                if names:
                    attachment_notes[entry.index] = names

        try:
            workbook_bytes = defect_report.populate_defect_report(
                template_bytes,
                result.csv_text,
                images=image_map,
                attachment_notes=attachment_notes,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        safe_stem = Path(result.filename).stem or "defect-report"
        download_name = f"{safe_stem}.xlsx"
        headers = {
            "Content-Disposition": f'attachment; filename="{download_name}"',
            "Cache-Control": "no-store",
            "X-Defect-Table": base64.b64encode(result.csv_text.encode("utf-8")).decode("ascii"),
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


@router.get("/drive/projects/{project_id}/feature-list")
async def get_feature_list(
    project_id: str,
    google_id: Optional[str] = Query(None, description="Drive 작업에 사용할 Google 사용자 식별자 (sub)"),
    file_id: Optional[str] = Query(
        None,
        alias="fileId",
        description="편집할 기능리스트 파일 ID",
    ),
    drive_service: GoogleDriveService = Depends(get_drive_service),
) -> Dict[str, Any]:
    result = await drive_service.get_feature_list_rows(
        project_id=project_id,
        google_id=google_id,
        file_id=file_id,
    )
    return result


@router.put("/drive/projects/{project_id}/feature-list")
async def update_feature_list(
    project_id: str,
    payload: FeatureListUpdateRequest,
    google_id: Optional[str] = Query(None, description="Drive 작업에 사용할 Google 사용자 식별자 (sub)"),
    file_id: Optional[str] = Query(
        None,
        alias="fileId",
        description="편집할 기능리스트 파일 ID",
    ),
    drive_service: GoogleDriveService = Depends(get_drive_service),
) -> Dict[str, Any]:
    normalized_rows = [row.model_dump(by_alias=True) for row in payload.rows]
    result = await drive_service.update_feature_list_rows(
        project_id=project_id,
        rows=normalized_rows,
        project_overview=str(payload.project_overview or ""),
        google_id=google_id,
        file_id=file_id,
    )
    return result


@router.get("/drive/projects/{project_id}/feature-list/download")
async def download_feature_list(
    project_id: str,
    google_id: Optional[str] = Query(None, description="Drive 작업에 사용할 Google 사용자 식별자 (sub)"),
    file_id: Optional[str] = Query(
        None,
        alias="fileId",
        description="다운로드할 기능리스트 파일 ID",
    ),
    drive_service: GoogleDriveService = Depends(get_drive_service),
) -> StreamingResponse:
    file_name, content = await drive_service.download_feature_list_workbook(
        project_id=project_id,
        google_id=google_id,
        file_id=file_id,
    )
    safe_name = file_name or "feature-list.xlsx"
    headers = {
        "Content-Disposition": _build_attachment_header(safe_name, default_filename="feature-list.xlsx"),
        "Cache-Control": "no-store",
    }
    return StreamingResponse(
        io.BytesIO(content),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers=headers,
    )


async def _read_upload_bytes(upload: UploadFile) -> bytes:
    try:
        return await upload.read()
    finally:
        await upload.close()


def _normalize_feature_list_records(rows: Sequence[Dict[str, str]]) -> List[Dict[str, str]]:
    normalized: List[Dict[str, str]] = []
    for entry in rows:
        normalized.append(
            {
                "majorCategory": str(entry.get("majorCategory", "") or "").strip(),
                "middleCategory": str(entry.get("middleCategory", "") or "").strip(),
                "minorCategory": str(entry.get("minorCategory", "") or "").strip(),
                "featureDescription": str(entry.get("featureDescription", "") or "").strip(),
            }
        )
    return normalized


def _csv_from_testcase_rows(rows: Sequence[TestcaseFinalizeRowModel]) -> str:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=list(TESTCASE_EXPECTED_HEADERS), lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow(
            {
                "대분류": row.major_category,
                "중분류": row.middle_category,
                "소분류": row.minor_category,
                "테스트 케이스 ID": row.testcase_id,
                "테스트 시나리오": row.scenario,
                "입력(사전조건 포함)": row.input,
                "기대 출력(사후조건 포함)": row.expected,
                "테스트 결과": row.result,
                "상세 테스트 결과": row.detail,
                "비고": row.note,
            }
        )
    return buffer.getvalue()


def _strip_label_prefix(value: str, label: str) -> str:
    if not value:
        return ""

    pattern = rf"^\s*{re.escape(label)}\s*[:：-]?\s*"
    stripped = re.sub(pattern, "", value, count=1)
    return stripped.strip()


def _decode_feature_list_csv(content: bytes) -> List[Dict[str, str]]:
    text = _decode_text(content)
    records = feature_list_templates.normalize_feature_list_records(text)
    normalized: List[Dict[str, str]] = []
    for record in records:
        normalized.append(
            {
                "majorCategory": record.get("대분류", ""),
                "middleCategory": record.get("중분류", ""),
                "minorCategory": record.get("소분류", ""),
                "featureDescription": record.get("기능 설명", ""),
            }
        )
    return normalized


@router.post("/drive/projects/{project_id}/testcases/workflow/feature-list")
async def prepare_testcase_feature_list(
    project_id: str,
    feature_list_file: UploadFile = File(
        ..., description="테스트케이스 생성을 위한 기능리스트 파일"
    ),
) -> TestcaseFeatureListResponse:
    filename = feature_list_file.filename or "feature-list"
    extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    content = await _read_upload_bytes(feature_list_file)

    rows: List[Dict[str, str]] = []
    project_overview = ""

    if extension in {"xlsx", "xlsm"}:
        try:
            _, _, _, parsed_rows = drive_feature_lists.parse_feature_list_workbook(content)
            rows = _normalize_feature_list_records(parsed_rows)
        except HTTPException:
            raise
        except Exception as exc:  # pragma: no cover - 안전망
            raise HTTPException(
                status_code=422,
                detail="기능리스트 엑셀 파일을 해석하는 중 오류가 발생했습니다.",
            ) from exc

        try:
            _, project_overview = feature_list_templates.extract_feature_list_overview(content)
        except Exception:  # pragma: no cover - 개요 추출 실패는 무시
            project_overview = ""
    else:
        rows = _normalize_feature_list_records(_decode_feature_list_csv(content))

    if not rows:
        raise HTTPException(status_code=422, detail="기능리스트에서 항목을 찾을 수 없습니다.")

    response = TestcaseFeatureListResponse(
        fileName=filename,
        projectOverview=project_overview or "",
        rows=[FeatureListRowModel(**row) for row in rows],
    )
    return response


@router.post("/drive/projects/{project_id}/testcases/workflow/scenarios")
async def generate_testcase_scenarios(
    project_id: str,
    major_category: str = Form(..., description="테스트케이스 대분류"),
    middle_category: str = Form(..., description="테스트케이스 중분류"),
    minor_category: str = Form(..., description="테스트케이스 소분류"),
    feature_description: str = Form("", description="기능 설명"),
    project_overview: str = Form("", description="프로젝트 개요"),
    scenario_count: int = Form(3, description="생성할 시나리오 수(3~5)"),
    attachments: Optional[List[UploadFile]] = File(
        None, description="소분류 관련 참고 이미지"
    ),
    ai_generation_service: AIGenerationService = Depends(get_ai_generation_service),
) -> TestcaseScenarioResponse:
    normalized_count = max(3, min(5, scenario_count))
    uploads = attachments or []

    suggestions = await ai_generation_service.suggest_testcase_scenarios(
        project_id=project_id,
        major_category=major_category,
        middle_category=middle_category,
        minor_category=minor_category,
        feature_description=feature_description,
        project_overview=project_overview,
        scenario_count=normalized_count,
        attachments=uploads,
    )

    return TestcaseScenarioResponse(
        scenarios=[TestcaseScenarioModel(**entry) for entry in suggestions]
    )


@router.post("/drive/projects/{project_id}/testcases/workflow/finalize")
async def finalize_testcases(
    project_id: str,
    payload: TestcaseFinalizeRequest,
) -> TestcaseFinalizeResponse:
    if not payload.groups:
        raise HTTPException(status_code=422, detail="시나리오 정보가 없습니다.")

    normalized_groups = [group.model_dump(by_alias=True) for group in payload.groups]

    rows: List[TestcaseFinalizeRowModel] = []
    group_index = 0

    for group in normalized_groups:
        major = str(group.get("majorCategory") or "").strip()
        middle = str(group.get("middleCategory") or "").strip()
        minor = str(group.get("minorCategory") or "").strip()
        scenarios = group.get("scenarios")
        if not isinstance(scenarios, Sequence):
            continue

        normalized_entries: List[tuple[str, str, str]] = []
        for entry in scenarios:
            if not isinstance(entry, Mapping):
                continue
            scenario_text = str(
                entry.get("테스트 시나리오")
                or entry.get("scenario")
                or ""
            ).strip()
            input_text = str(
                entry.get("입력(사전조건 포함)")
                or entry.get("input")
                or ""
            ).strip()
            expected_text = str(
                entry.get("기대 출력(사후조건 포함)")
                or entry.get("expected")
                or ""
            ).strip()

            if not (scenario_text or input_text or expected_text):
                continue

            normalized_entries.append((scenario_text, input_text, expected_text))

        if not normalized_entries:
            continue

        group_index += 1

        for scenario_index, (scenario_text, input_text, expected_text) in enumerate(
            normalized_entries, start=1
        ):
            testcase_id = f"TC-{group_index:03d}-{scenario_index:03d}"

            rows.append(
                TestcaseFinalizeRowModel(
                    major_category=major,
                    middle_category=middle,
                    minor_category=minor,
                    testcase_id=testcase_id,
                    scenario=_strip_label_prefix(scenario_text, "테스트 시나리오"),
                    input=_strip_label_prefix(input_text, "입력(사전조건 포함)"),
                    expected=_strip_label_prefix(expected_text, "기대 출력(사후조건 포함)"),
                    result="P",
                    detail="",
                    note="",
                )
            )

    if not rows:
        raise HTTPException(status_code=422, detail="생성된 테스트케이스 행을 찾을 수 없습니다.")

    csv_text = _csv_from_testcase_rows(rows)

    try:
        template_bytes = _TESTCASE_TEMPLATE.read_bytes()
    except FileNotFoundError as exc:  # pragma: no cover - 방어
        raise HTTPException(status_code=500, detail="테스트케이스 템플릿을 찾을 수 없습니다.") from exc
    except OSError as exc:  # pragma: no cover - 방어
        raise HTTPException(status_code=500, detail="테스트케이스 템플릿을 읽는 중 오류가 발생했습니다.") from exc

    try:
        workbook_bytes = testcases.populate_testcase_list(template_bytes, csv_text)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    workbook_base64 = base64.b64encode(workbook_bytes).decode("ascii")

    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    safe_project = re.sub(r"[^A-Za-z0-9_-]+", "_", project_id)
    file_stem = f"{safe_project}_testcase_workflow_{timestamp}"
    xlsx_name = f"{file_stem}.xlsx"

    return TestcaseFinalizeResponse(
        csvText=csv_text,
        fileName=xlsx_name,
        rows=rows,
        xlsxBase64=workbook_base64,
    )


@router.post("/drive/projects/{project_id}/testcases/workflow/export")
async def export_testcases(
    project_id: str,
    payload: TestcaseExportRequest,
) -> StreamingResponse:
    if not payload.rows:
        raise HTTPException(status_code=422, detail="내보낼 테스트케이스 행이 없습니다.")

    csv_text = _csv_from_testcase_rows(payload.rows)

    try:
        template_bytes = _TESTCASE_TEMPLATE.read_bytes()
    except FileNotFoundError as exc:  # pragma: no cover - 방어
        raise HTTPException(status_code=500, detail="테스트케이스 템플릿을 찾을 수 없습니다.") from exc
    except OSError as exc:  # pragma: no cover - 방어
        raise HTTPException(status_code=500, detail="테스트케이스 템플릿을 읽는 중 오류가 발생했습니다.") from exc

    try:
        workbook_bytes = testcases.populate_testcase_list(template_bytes, csv_text)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    filename = f"{project_id}_testcases.xlsx"
    headers = {
        "Content-Disposition": _build_attachment_header(filename, default_filename="testcases.xlsx"),
        "Cache-Control": "no-store",
    }

    return StreamingResponse(
        io.BytesIO(workbook_bytes),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers=headers,
    )


@router.post("/drive/projects/{project_id}/defect-report/rewrite")
async def rewrite_defect_report_cell(
    project_id: str,
    payload: DefectCellRewriteRequest,
    ai_generation_service: AIGenerationService = Depends(get_ai_generation_service),
) -> Dict[str, str]:
    updated = await ai_generation_service.rewrite_defect_report_cell(
        project_id=project_id,
        column_key=payload.column_key,
        column_label=payload.column_label,
        original_value=payload.original_value,
        instructions=payload.instructions,
        row_values=payload.row_values,
    )

    return {"updatedText": updated}


@router.post("/drive/projects/{project_id}/defect-report/compile")
async def compile_defect_report(
    project_id: str,
    rows: str = Form(..., description="결함 리포트 행 데이터(JSON 배열)"),
    attachments: Optional[List[UploadFile]] = File(
        None, description="결함 이미지 첨부 파일"
    ),
    attachment_metadata: Optional[str] = Form(
        None, description="첨부 파일 메타데이터(JSON 배열)"
    ),
) -> StreamingResponse:
    try:
        parsed_rows = json.loads(rows)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=422, detail="행 데이터 형식이 올바르지 않습니다.") from exc

    if not isinstance(parsed_rows, list):
        raise HTTPException(status_code=422, detail="행 데이터 형식이 올바르지 않습니다.")

    normalized_rows: List[Dict[str, str]] = []
    for index, entry in enumerate(parsed_rows, start=1):
        if not isinstance(entry, dict):
            raise HTTPException(
                status_code=422,
                detail=f"{index}번째 행 데이터 형식이 올바르지 않습니다.",
            )
        record: Dict[str, str] = {}
        for column in DEFECT_REPORT_EXPECTED_HEADERS:
            value = entry.get(column)
            record[column] = "" if value is None else str(value)
        normalized_rows.append(record)

    if not normalized_rows:
        raise HTTPException(status_code=422, detail="최소 한 개의 행 데이터가 필요합니다.")

    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=DEFECT_REPORT_EXPECTED_HEADERS)
    writer.writeheader()
    writer.writerows(normalized_rows)
    csv_text = buffer.getvalue()

    uploads = attachments or []
    metadata_entries: List[Dict[str, Any]] = []

    if uploads:
        if not attachment_metadata:
            raise HTTPException(status_code=422, detail="첨부 메타데이터 형식이 올바르지 않습니다.")
        try:
            parsed_metadata = json.loads(attachment_metadata)
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=422, detail="첨부 메타데이터 형식이 올바르지 않습니다.") from exc
        if not isinstance(parsed_metadata, list) or len(parsed_metadata) != len(uploads):
            raise HTTPException(status_code=422, detail="첨부 메타데이터 형식이 올바르지 않습니다.")
        metadata_entries = parsed_metadata

    image_map: Dict[int, List[DefectReportImage]] = {}
    notes_map: Dict[int, List[str]] = {}

    for upload, metadata in zip(uploads, metadata_entries):
        if not isinstance(metadata, dict):
            raise HTTPException(status_code=422, detail="첨부 메타데이터 형식이 올바르지 않습니다.")

        defect_index = metadata.get("defect_index")
        try:
            normalized_index = int(defect_index)
        except (TypeError, ValueError):
            raise HTTPException(status_code=422, detail="첨부 파일의 결함 순번이 올바르지 않습니다.")

        try:
            content = await upload.read()
        finally:
            await upload.close()

        if not content:
            continue

        file_name = upload.filename or metadata.get("originalFileName") or "attachment"
        image = DefectReportImage(
            file_name=file_name,
            content=content,
            content_type=upload.content_type,
        )
        image_map.setdefault(normalized_index, []).append(image)
        notes_map.setdefault(normalized_index, []).append(file_name)

    if not _DEFECT_REPORT_TEMPLATE.exists():
        raise HTTPException(status_code=500, detail="결함 리포트 템플릿을 찾을 수 없습니다.")

    try:
        template_bytes = _DEFECT_REPORT_TEMPLATE.read_bytes()
    except FileNotFoundError as exc:  # pragma: no cover - unexpected
        raise HTTPException(status_code=500, detail="결함 리포트 템플릿을 읽을 수 없습니다.") from exc

    try:
        workbook_bytes = defect_report.populate_defect_report(
            template_bytes,
            csv_text,
            images=image_map if image_map else None,
            attachment_notes=notes_map if notes_map else None,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    safe_project = re.sub(r"[^A-Za-z0-9_-]+", "_", project_id) or "defect-report"
    download_name = f"{safe_project}_defect-report.xlsx"
    headers = {
        "Content-Disposition": f'attachment; filename="{download_name}"',
        "Cache-Control": "no-store",
        "X-Defect-Table": base64.b64encode(csv_text.encode("utf-8")).decode("ascii"),
    }

    return StreamingResponse(
        io.BytesIO(workbook_bytes),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers=headers,
    )
