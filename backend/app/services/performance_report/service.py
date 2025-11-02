from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from fastapi import HTTPException, UploadFile

from ..google_drive.service import GoogleDriveService
from ..excel_templates.performance_report import (
    PerformanceWorkbookPayload,
    build_performance_workbook,
)
from .models import PerformanceDataset, PerformanceOSType
from .parsers import detect_os_type, parse_performance_file


TEMPLATE_PATH = Path(__file__).resolve().parents[3] / "template" / "다.수행" / "성능시험" / "GS-B-XX-XXXX 성능시험.xlsx"


@dataclass
class PerformanceWorkbookResult:
    filename: str
    content: bytes
    datasets_by_os: Mapping[PerformanceOSType, Sequence[PerformanceDataset]]
    warnings: Sequence[str]


@dataclass
class UnresolvedPerformanceFile:
    name: str
    index: int


@dataclass
class PerformanceFileMetadata:
    memory_gb: float
    device_name: str


class PerformanceOSResolutionRequired(Exception):
    def __init__(self, files: Sequence[UnresolvedPerformanceFile]) -> None:
        super().__init__("OS resolution required for rawdata files.")
        self.files = list(files)


class PerformanceReportService:
    def __init__(self, *, drive_service: GoogleDriveService) -> None:
        self._drive_service = drive_service

    async def generate_workbook(
        self,
        *,
        project_id: str,
        google_id: Optional[str],
        uploads: Sequence[UploadFile],
        overrides: Optional[Mapping[str, str]] = None,
        metadata: Optional[Sequence[PerformanceFileMetadata]] = None,
    ) -> PerformanceWorkbookResult:
        raw_files = await self._collect_uploads(uploads)
        overrides = overrides or {}
        metadata = list(metadata or [])

        if metadata and len(metadata) != len(raw_files):
            raise HTTPException(status_code=422, detail="메모리 및 장비명 정보를 다시 확인해 주세요.")
        if not metadata:
            metadata = [PerformanceFileMetadata(memory_gb=0.0, device_name="") for _ in raw_files]

        datasets_by_os: Dict[PerformanceOSType, List[PerformanceDataset]] = {
            PerformanceOSType.WINDOWS: [],
            PerformanceOSType.LINUX: [],
        }
        warnings: List[str] = []
        unresolved: List[UnresolvedPerformanceFile] = []

        for index, (upload, raw_bytes) in enumerate(raw_files):
            override_os = self._resolve_override(overrides, upload.filename, index)
            os_type = _normalize_os_label(override_os)
            if os_type is None:
                os_type = detect_os_type(upload.filename or "", raw_bytes)

            if os_type is None:
                unresolved.append(UnresolvedPerformanceFile(name=upload.filename or f"file-{index+1}", index=index))
                continue

            try:
                parsing = parse_performance_file(
                    os_type,
                    raw_bytes,
                    source_name=upload.filename or f"file-{index+1}",
                )
            except ValueError as exc:
                raise HTTPException(status_code=422, detail=str(exc)) from exc

            meta = metadata[index] if index < len(metadata) else PerformanceFileMetadata(memory_gb=0.0, device_name="")
            if meta.memory_gb > 0:
                parsing.dataset.metadata["memory_gb"] = float(meta.memory_gb)
                if os_type == PerformanceOSType.LINUX:
                    parsing.dataset.metadata["total_memory_kib"] = int(float(meta.memory_gb) * 1024 * 1024)
            parsing.dataset.metadata["device_name"] = meta.device_name

            datasets_by_os[os_type].append(parsing.dataset)
            warnings.extend(parsing.warnings)

        if unresolved:
            raise PerformanceOSResolutionRequired(unresolved)

        try:
            template_bytes = TEMPLATE_PATH.read_bytes()
        except FileNotFoundError as exc:
            raise HTTPException(status_code=500, detail="성능시험 템플릿 파일을 찾지 못했습니다.") from exc
        except OSError as exc:
            raise HTTPException(status_code=500, detail="성능시험 템플릿 파일을 읽는 중 오류가 발생했습니다.") from exc

        payload = PerformanceWorkbookPayload(
            template_bytes=template_bytes,
            windows_datasets=datasets_by_os[PerformanceOSType.WINDOWS],
            linux_datasets=datasets_by_os[PerformanceOSType.LINUX],
        )
        try:
            workbook_bytes = build_performance_workbook(payload)
        except RuntimeError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

        project_number = await self._drive_service.get_project_exam_number(project_id=project_id, google_id=google_id)
        filename = f"{project_number} 성능시험 v1.0.xlsx"

        return PerformanceWorkbookResult(
            filename=filename,
            content=workbook_bytes,
            datasets_by_os=datasets_by_os,
            warnings=warnings,
        )

    async def _collect_uploads(self, uploads: Sequence[UploadFile]) -> List[Tuple[UploadFile, bytes]]:
        results: List[Tuple[UploadFile, bytes]] = []

        for upload in uploads:
            data = await upload.read()
            if not data:
                await upload.close()
                raise HTTPException(status_code=422, detail=f"{upload.filename or '업로드 파일'}이 비어 있습니다.")
            results.append((upload, data))
            await upload.close()
        return results

    def _resolve_override(self, overrides: Mapping[str, str], filename: Optional[str], index: int) -> Optional[str]:
        candidates: List[str] = []
        if filename:
            candidates.append(filename)
        candidates.append(str(index))
        candidates.append(str(index + 1))
        candidates.append(f"index:{index}")
        candidates.append(f"file:{index+1}")
        for key in candidates:
            if key in overrides:
                return overrides[key]
        return None


def _normalize_os_label(label: Optional[str]) -> Optional[PerformanceOSType]:
    if not label:
        return None
    normalized = label.strip().lower()
    mapping = {
        "windows": PerformanceOSType.WINDOWS,
        "win": PerformanceOSType.WINDOWS,
        "w": PerformanceOSType.WINDOWS,
        "linux": PerformanceOSType.LINUX,
        "lin": PerformanceOSType.LINUX,
        "l": PerformanceOSType.LINUX,
    }
    return mapping.get(normalized)
