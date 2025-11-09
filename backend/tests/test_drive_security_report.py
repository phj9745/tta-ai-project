from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from fastapi.testclient import TestClient

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.application import create_app
from app.dependencies import (
    get_ai_generation_service,
    get_configuration_image_service,
    get_drive_service,
    get_security_report_service,
)
from app.services.excel_templates.models import SECURITY_REPORT_EXPECTED_HEADERS


def _create_app_with_security_mocks():
    os.environ.setdefault("OPENAI_API_KEY", "test-key")
    app = create_app()

    drive_stub = SimpleNamespace(
        apply_csv_to_spreadsheet=AsyncMock(
            return_value={
                "fileId": "sheet-id",
                "fileName": "결함리포트 v1.0.xlsx",
                "modifiedTime": "2024-05-01T00:00:00Z",
            }
        )
    )
    security_stub = SimpleNamespace(
        generate_preview_rows=AsyncMock(
            return_value=[
                {
                    "순번": "1",
                    "시험환경 OS": "시험환경 모든 OS",
                    "결함 요약": "SQL Injection",
                    "결함 정도": "H",
                    "발생 빈도": "높음",
                    "품질 특성": "보안성",
                    "결함 설명": "쿼리 파라미터가 검증되지 않습니다.",
                    "업체 응답": "",
                    "수정여부": "",
                    "비고": "보안성 시험 결과 참고",
                    "매핑 유형": "기준표 매칭",
                }
            ]
        ),
        build_csv_text_from_rows=MagicMock(return_value="csv-data"),
    )

    app.dependency_overrides[get_drive_service] = lambda: drive_stub
    app.dependency_overrides[get_security_report_service] = lambda: security_stub
    app.dependency_overrides[get_ai_generation_service] = lambda: SimpleNamespace(generate_csv=AsyncMock())
    app.dependency_overrides[get_configuration_image_service] = lambda: SimpleNamespace()

    return app, security_stub, drive_stub


def test_preview_security_report_returns_rows():
    app, security_stub, _ = _create_app_with_security_mocks()

    with TestClient(app) as client:
        response = client.post(
            "/drive/projects/sample-project/security-report/preview",
            files={"invictiReport": ("report.html", "<html></html>", "text/html")},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload.get("headers") == list(SECURITY_REPORT_EXPECTED_HEADERS)
    assert isinstance(payload.get("rows"), list)
    assert payload["rows"][0]["결함 요약"] == "SQL Injection"

    assert security_stub.generate_preview_rows.await_count == 1
    await_args = security_stub.generate_preview_rows.await_args
    assert await_args.kwargs["project_id"] == "sample-project"


def test_finalize_security_report_appends_rows():
    app, security_stub, drive_stub = _create_app_with_security_mocks()

    rows_payload = [
        {
            "순번": "1",
            "시험환경 OS": "시험환경 모든 OS",
            "결함 요약": "취약한 구성",
            "결함 정도": "M",
            "발생 빈도": "중간",
            "품질 특성": "보안성",
            "결함 설명": "기본 자격 증명이 유지됩니다.",
            "업체 응답": "",
            "수정여부": "",
            "비고": "AI 검토 필요",
            "매핑 유형": "AI 생성",
        }
    ]

    with TestClient(app) as client:
        response = client.post(
            "/drive/projects/sample-project/generate",
            data={
                "menu_id": "security-report",
                "rows_json": json.dumps(rows_payload, ensure_ascii=False),
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload.get("status") == "updated"
    assert payload.get("fileId") == "sheet-id"
    assert payload.get("headers") == list(SECURITY_REPORT_EXPECTED_HEADERS)
    assert payload.get("rows") == rows_payload

    security_stub.build_csv_text_from_rows.assert_called_once_with(rows_payload)
    assert drive_stub.apply_csv_to_spreadsheet.await_count == 1
    await_args = drive_stub.apply_csv_to_spreadsheet.await_args
    assert await_args.kwargs["project_id"] == "sample-project"
    assert await_args.kwargs["menu_id"] == "security-report"
    assert await_args.kwargs["csv_text"] == "csv-data"
