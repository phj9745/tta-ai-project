from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.excel_templates.models import DEFECT_REPORT_EXPECTED_HEADERS
from app.services.excel_templates.utils import parse_csv_records


def test_parse_csv_records_preserves_commas_in_description() -> None:
    csv_text = (
        "순번,시험환경(OS),결함요약,결함정도,발생빈도,품질특성,결함 설명,업체 응답,수정여부,비고\n"
        "1,Windows 11,로그인 오류,H,A,기능적합성,동명 기업이 여러 개 존재할 경우, 이런식으로,조치 예정,미정,-\n"
    )

    records = parse_csv_records(csv_text, DEFECT_REPORT_EXPECTED_HEADERS)

    assert records == [
        {
            "순번": "1",
            "시험환경(OS)": "Windows 11",
            "결함요약": "로그인 오류",
            "결함정도": "H",
            "발생빈도": "A",
            "품질특성": "기능적합성",
            "결함 설명": "동명 기업이 여러 개 존재할 경우, 이런식으로",
            "업체 응답": "조치 예정",
            "수정여부": "미정",
            "비고": "-",
        }
    ]
