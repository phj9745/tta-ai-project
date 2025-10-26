from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.application import create_app
from app.dependencies import get_ai_generation_service, get_drive_service
from app.services.google_drive import defect_reports


def _create_app_with_mocks():
    os.environ.setdefault("OPENAI_API_KEY", "test-key")
    app = create_app()

    ai_stub = SimpleNamespace(generate_csv=AsyncMock())
    drive_stub = SimpleNamespace(
        update_defect_report_rows=AsyncMock(
            return_value={
                "fileId": "sheet-id",
                "fileName": "defect-report.xlsx",
                "modifiedTime": "2024-05-01T00:00:00Z",
            }
        )
    )

    app.dependency_overrides[get_ai_generation_service] = lambda: ai_stub
    app.dependency_overrides[get_drive_service] = lambda: drive_stub

    return app, ai_stub, drive_stub


def test_finalize_defect_report_updates_spreadsheet_without_ai():
    app, ai_stub, drive_stub = _create_app_with_mocks()

    rows_payload = [
        {
            "order": "1",
            "environment": "윈도우 11",
            "summary": "로그인 오류",
            "severity": "H",
            "frequency": "A",
            "quality": "신뢰성",
            "description": "로그인 시 빈 화면이 표시됩니다.",
            "vendorResponse": "대응 예정",
            "fixStatus": "미해결",
            "note": "스크린샷 참조",
        },
        {
            "order": "2",
            "environment": "macOS",
            "summary": "버튼 표시 문제",
            "severity": "M",
            "frequency": "B",
            "quality": "사용성",
            "description": "설정 저장 버튼이 가려집니다.",
            "vendorResponse": "확인 중",
            "fixStatus": "미해결",
            "note": "관련 로그 첨부",
        },
    ]
    attachment_stubs = [
        {"defect_index": 1, "fileName": "defect-01-login.png"},
        {"defect_index": 2, "fileName": "defect-02-settings.png"},
    ]

    with TestClient(app) as client:
        response = client.post(
            "/drive/projects/test-project/generate",
            data={
                "menu_id": "defect-report",
                "rows": json.dumps(rows_payload, ensure_ascii=False),
                "attachment_names": json.dumps(attachment_stubs, ensure_ascii=False),
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload.get("status") == "updated"
    assert payload.get("fileId") == "sheet-id"

    ai_stub.generate_csv.assert_not_called()
    assert drive_stub.update_defect_report_rows.await_count == 1

    await_args = drive_stub.update_defect_report_rows.await_args
    assert await_args.kwargs["project_id"] == "test-project"
    assert await_args.kwargs["google_id"] is None
    assert await_args.kwargs["images"] is None

    expected_rows = defect_reports.normalize_defect_report_rows(rows_payload)
    assert await_args.kwargs["rows"] == expected_rows
    assert await_args.kwargs["attachment_notes"] == {
        1: ["defect-01-login.png"],
        2: ["defect-02-settings.png"],
    }

    assert payload.get("rows") == expected_rows
    assert payload.get("headers") == list(defect_reports.DEFECT_REPORT_EXPECTED_HEADERS)
