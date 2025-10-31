"""High level service for handling configuration image captures."""

from __future__ import annotations

import asyncio
import datetime as dt
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Sequence, Tuple

from fastapi import HTTPException, UploadFile

from ..google_drive.service import GoogleDriveService
from .capture import capture_video_changes


@dataclass(slots=True)
class _UploadCandidate:
    name: str
    content: bytes
    mime_type: str
    time_sec: float
    is_start: bool


class ConfigurationImageService:
    """Coordinates video capture processing and Google Drive uploads."""

    EVENTS_FILENAME_TEMPLATE = "형상 이미지 이벤트_{timestamp}.csv"

    def __init__(self, drive_service: GoogleDriveService) -> None:
        self._drive_service = drive_service

    async def capture_and_upload(
        self,
        *,
        project_id: str,
        upload: UploadFile,
        google_id: Optional[str],
    ) -> Dict[str, Any]:
        filename = upload.filename or "configuration-video.mp4"
        suffix = Path(filename).suffix or ".mp4"

        data = await upload.read()
        if not data:
            raise HTTPException(status_code=422, detail="업로드된 동영상이 비어 있습니다.")

        candidates, events_csv = await self._process_video_bytes(data, suffix)

        if not candidates:
            raise HTTPException(
                status_code=500,
                detail="형상 이미지를 추출하지 못했습니다. 동영상 파일을 다시 확인해 주세요.",
            )

        events_filename = self.EVENTS_FILENAME_TEMPLATE.format(
            timestamp=dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d-%H%M%S")
        )
        events_bytes = events_csv.encode("utf-8")

        upload_result = await self._drive_service.upload_configuration_captures(
            project_id=project_id,
            google_id=google_id,
            images=[
                {
                    "name": candidate.name,
                    "content": candidate.content,
                    "contentType": candidate.mime_type,
                    "timeSec": candidate.time_sec,
                    "isStart": candidate.is_start,
                }
                for candidate in candidates
            ],
            events_file={
                "name": events_filename,
                "content": events_bytes,
                "contentType": "text/csv",
            },
        )

        return upload_result

    async def list_images(
        self,
        *,
        project_id: str,
        google_id: Optional[str],
    ) -> Dict[str, Any]:
        return await self._drive_service.list_configuration_images(
            project_id=project_id,
            google_id=google_id,
        )

    async def delete_images(
        self,
        *,
        project_id: str,
        google_id: Optional[str],
        file_ids: Sequence[str],
    ) -> int:
        return await self._drive_service.delete_configuration_images(
            project_id=project_id,
            google_id=google_id,
            file_ids=file_ids,
        )

    async def download_file(
        self,
        *,
        project_id: str,
        google_id: Optional[str],
        file_id: str,
    ) -> Dict[str, Any]:
        return await self._drive_service.download_configuration_file(
            project_id=project_id,
            google_id=google_id,
            file_id=file_id,
        )

    async def _process_video_bytes(self, data: bytes, suffix: str) -> Tuple[Sequence[_UploadCandidate], str]:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._process_sync, data, suffix)

    def _process_sync(self, data: bytes, suffix: str) -> Tuple[Sequence[_UploadCandidate], str]:
        from tempfile import TemporaryDirectory

        with TemporaryDirectory() as tmpdir:
            temp_dir = Path(tmpdir)
            video_path = temp_dir / f"input{suffix}"
            video_path.write_bytes(data)
            capture_dir = temp_dir / "captures"
            result = capture_video_changes(video_path, capture_dir)

            candidates = [
                _UploadCandidate(
                    name=image.filename,
                    content=(capture_dir / image.filename).read_bytes(),
                    mime_type="image/png",
                    time_sec=image.time_sec,
                    is_start=image.is_start,
                )
                for image in result.images
            ]

            return candidates, result.events_csv


__all__ = ["ConfigurationImageService"]
