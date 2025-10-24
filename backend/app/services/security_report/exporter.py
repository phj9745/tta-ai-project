from __future__ import annotations

from typing import Sequence

import pandas as pd

from .models import StandardizedFinding


def build_dataframe(findings: Sequence[StandardizedFinding]) -> pd.DataFrame:
    rows = []
    for finding in findings:
        rows.append(
            {
                "Invicti 결과": finding.invicti_name,
                "결함 요약": finding.summary,
                "결함정도": finding.severity,
                "발생경로": finding.path,
                "발생빈도": finding.occurrence,
                "품질특성": finding.category,
                "결함 설명": finding.description,
                "조치 가이드": finding.recommendation,
                "anchor_id": finding.anchor_id or "",
                "원본 세부내용": finding.raw_details,
                "AI 메모": finding.ai_notes,
                "매핑 유형": "AI 생성" if finding.source == "ai" else "기준표 매칭",
            }
        )
    dataframe = pd.DataFrame(rows)
    columns = [
        "Invicti 결과",
        "결함 요약",
        "결함정도",
        "발생경로",
        "발생빈도",
        "품질특성",
        "결함 설명",
        "조치 가이드",
        "anchor_id",
        "원본 세부내용",
        "매핑 유형",
        "AI 메모",
    ]
    return dataframe.reindex(columns=columns)


def build_csv_view(dataframe: pd.DataFrame) -> pd.DataFrame:
    if dataframe.empty:
        return pd.DataFrame(
            columns=[
                "순번",
                "시험환경 OS",
                "결함 요약",
                "결함 정도",
                "발생 빈도",
                "품질 특성",
                "결함 설명",
                "업체 응답",
                "수정여부",
                "비고",
                "매핑 유형",
            ]
        )

    output = dataframe.copy()
    output.insert(0, "순번", [str(index) for index in range(1, len(output) + 1)])
    output.insert(1, "시험환경 OS", ["시험환경 모든 OS"] * len(output))

    severity_map = {
        "Critical": "H",
        "High": "H",
        "Medium": "M",
        "Low": "L",
        "Info": "L",
        "Informational": "L",
    }
    raw_severity = output["결함정도"].fillna("").astype(str)
    output["결함 정도"] = raw_severity.map(severity_map).fillna("M")

    output["발생 빈도"] = output["발생빈도"].fillna("").astype(str)
    output["품질 특성"] = output["품질특성"].fillna("").astype(str)
    output["결함 설명"] = output["결함 설명"].fillna("").astype(str)
    output["결함 요약"] = output["결함 요약"].fillna("").astype(str)

    if "조치 가이드" in output.columns:
        output["조치 가이드"] = output["조치 가이드"].fillna("").astype(str)
    if "발생경로" in output.columns:
        output["발생경로"] = output["발생경로"].fillna("").astype(str)
    if "Invicti 결과" in output.columns:
        output["Invicti 결과"] = output["Invicti 결과"].fillna("").astype(str)
    if "원본 세부내용" in output.columns:
        output["원본 세부내용"] = output["원본 세부내용"].fillna("").astype(str)

    output["업체 응답"] = ""
    output["수정여부"] = ""
    output["비고"] = "보안성 시험 결과 참고"

    columns = [
        "순번",
        "시험환경 OS",
        "결함 요약",
        "결함 정도",
        "발생 빈도",
        "품질 특성",
        "결함 설명",
        "업체 응답",
        "수정여부",
        "비고",
        "매핑 유형",
    ]
    return output.reindex(columns=columns)
