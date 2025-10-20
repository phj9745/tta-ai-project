from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Literal, Mapping

from pydantic import BaseModel, ConfigDict, Field


RenderMode = Literal["file", "image", "xlsx-to-pdf", "text"]


def _to_camel(value: str) -> str:
    parts = value.split("_")
    return parts[0] + "".join(part.capitalize() for part in parts[1:])


class PromptSection(BaseModel):
    model_config = ConfigDict(
        extra="ignore", alias_generator=_to_camel, populate_by_name=True
    )

    id: str
    label: str = ""
    content: str = ""
    enabled: bool = True


class PromptScaffolding(BaseModel):
    model_config = ConfigDict(
        extra="ignore", alias_generator=_to_camel, populate_by_name=True
    )

    attachments_heading: str = ""
    attachments_intro: str = ""
    closing_note: str = ""
    format_warning: str = ""


class PromptBuiltinContext(BaseModel):
    model_config = ConfigDict(
        extra="ignore", alias_generator=_to_camel, populate_by_name=True
    )

    id: str
    label: str = ""
    description: str = ""
    source_path: str = ""
    render_mode: RenderMode = "file"
    include_in_prompt: bool = True
    show_in_attachment_list: bool = True


class PromptModelParameters(BaseModel):
    model_config = ConfigDict(
        extra="ignore", alias_generator=_to_camel, populate_by_name=True
    )

    temperature: float = 0.2
    top_p: float = 0.9
    max_output_tokens: int = 1500
    presence_penalty: float = 0.0
    frequency_penalty: float = 0.0


class PromptConfig(BaseModel):
    model_config = ConfigDict(
        extra="ignore", alias_generator=_to_camel, populate_by_name=True
    )

    label: str
    summary: str = ""
    request_description: str = ""
    system_prompt: str
    user_prompt: str = ""
    evaluation_notes: str = ""
    user_prompt_sections: List[PromptSection] = Field(default_factory=list)
    scaffolding: PromptScaffolding = Field(default_factory=PromptScaffolding)
    attachment_descriptor_template: str = "{{index}}. {{descriptor}}"
    builtin_contexts: List[PromptBuiltinContext] = Field(default_factory=list)
    model_parameters: PromptModelParameters = Field(default_factory=PromptModelParameters)


@dataclass
class _StoredPrompt:
    menu_id: str
    config: PromptConfig


class PromptConfigStore:
    """Persist prompt configuration to a JSON file."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def load_all(self) -> Dict[str, Any]:
        try:
            with self._path.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
        except FileNotFoundError:
            return {}
        except json.JSONDecodeError:
            return {}

        if not isinstance(data, dict):
            return {}
        return data

    def save_all(self, payload: Mapping[str, Any]) -> None:
        serialized = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
        temp_path = self._path.with_suffix(".tmp")
        temp_path.write_text(serialized, encoding="utf-8")
        temp_path.replace(self._path)

    def save(self, menu_id: str, config: Mapping[str, Any]) -> None:
        data = self.load_all()
        data[menu_id] = config
        self.save_all(data)


def _merge_dict(base: Dict[str, Any], updates: Mapping[str, Any]) -> Dict[str, Any]:
    for key, value in updates.items():
        if (
            key in base
            and isinstance(base[key], dict)
            and isinstance(value, Mapping)
        ):
            base[key] = _merge_dict(base[key], value)
        else:
            base[key] = value
    return base


_DEFAULT_PROMPTS: Dict[str, PromptConfig] = {
    "feature-list": PromptConfig(
        label="기능리스트 생성",
        summary="요구사항 문서를 기반으로 신규 프로젝트의 기능 정의서를 작성합니다.",
        request_description="업로드된 자료에서 주요 기능과 근거를 추출하여 CSV로 정리합니다.",
        system_prompt="당신은 소프트웨어 기획 QA 리드입니다. 업로드된 요구사항을 기반으로 기능 정의서를 작성합니다.",
        user_prompt=(
            "요구사항 자료에서 주요 기능을 발췌하여 CSV로 정리하세요. "
            "다음 열을 포함해야 합니다: 대분류, 중분류, 소분류. "
            "각 열은 템플릿의 계층 구조에 맞춰 핵심 기능을 요약해야 합니다."
        ),
        user_prompt_sections=[
            PromptSection(
                id="feature-analysis",
                label="분석 요청",
                content=(
                    "1. 첨부 자료에서 핵심 요구사항, 비즈니스 규칙, 화면 흐름을 추출하고\n"
                    "2. 기능을 대·중·소 분류 체계로 재구성하며\n"
                    "3. 근거가 된 원문이나 페이지 번호를 증빙 자료 열에 기재하세요."
                ),
            ),
            PromptSection(
                id="feature-quality",
                label="품질 기준",
                content=(
                    "- 중복된 기능은 병합하고, 이름은 한글 명사형으로 통일합니다.\n"
                    "- 기능 설명에는 ‘무엇을/왜’를 한 문장씩 포함하고, 정량 기준이 있다면 추가합니다."
                ),
            ),
            PromptSection(
                id="feature-followup",
                label="후속 지시",
                content=(
                    "CSV에는 열 순서를 ‘대분류, 중분류, 소분류, 기능명, 기능설명, 근거자료’로 고정하고, "
                    "추가 제안은 별도 Markdown 섹션으로 출력하세요."
                ),
            ),
        ],
        scaffolding=PromptScaffolding(
            attachments_heading="첨부 파일 목록",
            attachments_intro=(
                "다음 첨부 파일을 참고하여 요구사항을 분석하고 지침에 맞는 CSV를 작성하세요.\n"
                "각 파일은 업로드된 순서대로 첨부되어 있습니다."
            ),
            closing_note="위 자료는 {{context_summary}}입니다. 이 자료를 활용하여 기능리스트를 작성해 주세요.",
            format_warning="CSV 이외의 다른 형식이나 설명 문장은 포함하지 마세요.",
        ),
        builtin_contexts=[
            PromptBuiltinContext(
                id="feature-template",
                label="기능리스트 예제 양식",
                description="내장된 기능리스트 예제 XLSX를 PDF로 변환한 자료. 열 구성 및 표기 예시 참고용.",
                source_path="template/가.계획/GS-B-XX-XXXX 기능리스트 v1.0.xlsx",
                render_mode="xlsx-to-pdf",
                include_in_prompt=True,
                show_in_attachment_list=True,
            )
        ],
    ),
    "testcase-generation": PromptConfig(
        label="테스트케이스 생성",
        summary="요구사항을 바탕으로 테스트 케이스 초안을 작성합니다.",
        request_description="핵심 시나리오를 도출하고 CSV 포맷으로 정리합니다.",
        system_prompt="당신은 소프트웨어 QA 테스터입니다. 업로드된 요구사항을 읽고 테스트 케이스 초안을 설계합니다.",
        user_prompt=(
            "요구사항을 분석하여 테스트 케이스를 CSV로 작성하세요. "
            "다음 열을 포함합니다: 대분류, 중분류, 소분류, 테스트 케이스 ID, 테스트 시나리오, 입력(사전조건 포함), 기대 출력(사후조건 포함), 테스트 결과, 상세 테스트 결과, 비고. "
            "테스트 케이스 ID는 TC-001부터 순차적으로 부여하고 테스트 결과는 기본값으로 '미실행'을 사용하세요."
        ),
        user_prompt_sections=[
            PromptSection(
                id="testcase-analysis",
                label="분석 요청",
                content=(
                    "1. 첨부 자료에서 사용자 흐름, 예외 상황, 비기능 요구사항을 식별하고\n"
                    "2. 기능리스트 항목과 매핑되는 테스트 케이스를 구성하며\n"
                    "3. 커버리지 공백이 있으면 비고에 보완이 필요한 근거를 기록하세요."
                ),
            ),
            PromptSection(
                id="testcase-quality",
                label="품질 기준",
                content=(
                    "- 테스트 시나리오는 'Given-When-Then' 구조 또는 동등한 단계로 간결히 작성합니다.\n"
                    "- 입력(사전조건 포함)과 기대 출력(사후조건 포함)에는 화면 ID, API, 데이터 범위 등 구체적 근거를 포함하세요."
                ),
            ),
            PromptSection(
                id="testcase-format",
                label="작성 지침",
                content=(
                    "CSV 열 순서는 ‘대분류, 중분류, 소분류, 테스트 케이스 ID, 테스트 시나리오, 입력(사전조건 포함), 기대 출력(사후조건 포함), 테스트 결과, 상세 테스트 결과, 비고’로 고정합니다.\n"
                    "테스트 케이스 ID는 TC-001부터 증가시키고, 테스트 결과는 기본값으로 ‘미실행’을 입력하세요."
                ),
            ),
        ],
        scaffolding=PromptScaffolding(
            attachments_heading="첨부 파일 목록",
            attachments_intro=(
                "다음 첨부 파일을 참고하여 요구사항을 분석한 뒤 지침에 맞는 테스트 케이스를 작성하세요.\n"
                "각 파일은 업로드된 순서대로 첨부되어 있습니다."
            ),
            closing_note="위 자료는 {{context_summary}}입니다. 이 자료를 바탕으로 테스트케이스를 작성해 주세요.",
            format_warning="CSV 이외의 다른 형식이나 설명 문장은 포함하지 마세요.",
        ),
        builtin_contexts=[
            PromptBuiltinContext(
                id="testcase-template",
                label="테스트케이스 예제 양식",
                description="내장된 테스트케이스 예제 XLSX를 PDF로 변환한 자료. 열 구성 및 작성 예시 참고용.",
                source_path="template/나.설계/GS-B-XX-XXXX 테스트케이스.xlsx",
                render_mode="xlsx-to-pdf",
                include_in_prompt=True,
                show_in_attachment_list=True,
            )
        ],
    ),
    "defect-report": PromptConfig(
        label="결함 리포트",
        summary="정제된 결함 목록과 증적 자료를 바탕으로 결함 리포트 표를 작성합니다.",
        request_description="결함별 현상, 심각도, 발생 정보를 표 형식으로 정리합니다.",
        system_prompt="당신은 QA 분석가입니다. 업로드된 정제된 결함 설명과 첨부 증적을 바탕으로 결함 리포트를 작성합니다.",
        user_prompt=(
            "정제된 결함 목록과 첨부 자료를 참고하여 다음 열을 포함한 CSV를 작성하세요: 순번, 시험환경(OS), 결함요약, 결함정도, 발생빈도, 품질특성, 결함 설명, 업체 응답, 수정여부, 비고. "
            "자료가 없는 항목은 '-'로 표기하고, 첨부 이미지가 있다면 결함 설명 또는 비고에 파일명을 괄호로 명시하세요."
        ),
        user_prompt_sections=[
            PromptSection(
                id="defect-analysis",
                label="작성 지침",
                content=(
                    "1. 정제된 결함 문장을 기반으로 현상을 공식 문체로 요약하고 필요한 경우 시험환경이나 재현 조건을 보완하세요.\n"
                    "2. 결함정도는 치명/중대/보통/경미 중에서 판단하여 기입하고, 발생빈도는 Always/Intermittent 등 로그에 근거해 작성하세요.\n"
                    "3. 품질특성에는 기능성, 신뢰성 등 관련 분류를 지정하고, 업체 응답과 수정여부는 근거 자료가 없으면 '-'로 표기합니다."
                ),
            ),
            PromptSection(
                id="defect-attachments",
                label="첨부 활용",
                content=(
                    "첨부 이미지가 존재하면 결함 설명 또는 비고에 '(첨부: 파일명)' 형태로 명시하여 표와 첨부를 연결하세요."
                ),
            ),
            PromptSection(
                id="defect-format",
                label="출력 형식",
                content=(
                    "모든 열을 지정된 순서로 포함한 CSV만 출력하세요. 값이 비어 있으면 '-'를 사용하고, 순번은 1부터 원본 순서를 유지합니다."
                ),
            ),
        ],
        scaffolding=PromptScaffolding(
            attachments_heading="첨부 파일 목록",
            attachments_intro=(
                "정제된 결함 요약과 추가 증적을 참고하여 결함을 정리하세요.\n"
                "이미지나 로그 파일이 있다면 해당 결함과 매핑해 활용하세요."
            ),
            format_warning="CSV 이외의 다른 형식이나 설명 문장은 포함하지 마세요.",
        ),
    ),
    "security-report": PromptConfig(
        label="보안성 리포트",
        summary="보안 점검 결과와 취약점 목록을 요약합니다.",
        request_description="발견된 취약점을 위험도와 함께 정리합니다.",
        system_prompt="당신은 보안 컨설턴트입니다. 업로드된 보안 점검 결과를 요약한 리포트를 만듭니다.",
        user_prompt=(
            "자료를 바탕으로 취약점을 정리한 CSV를 작성하세요. 열은 취약점 ID, 위험도, 영향 영역, 발견 내용, 권장 조치입니다. "
            "위험도는 높음/중간/낮음 중 하나를 사용합니다."
        ),
        scaffolding=PromptScaffolding(
            attachments_heading="첨부 파일 목록",
            attachments_intro="다음 자료를 확인하고 취약점을 정리하세요.",
            format_warning="CSV 이외의 다른 형식이나 설명 문장은 포함하지 마세요.",
        ),
    ),
    "performance-report": PromptConfig(
        label="성능 평가 리포트",
        summary="성능 측정 결과를 분석해 표로 정리합니다.",
        request_description="중요 시나리오의 성능 수치를 정리합니다.",
        system_prompt="당신은 성능 엔지니어입니다. 업로드된 성능 측정 자료를 분석하여 결과를 요약합니다.",
        user_prompt=(
            "자료를 분석하여 주요 시나리오의 성능을 정리한 CSV를 작성하세요. 열은 시나리오, 평균 응답(ms), 처리량(TPS), 자원 사용 요약, 개선 제안입니다."
        ),
        scaffolding=PromptScaffolding(
            attachments_heading="첨부 파일 목록",
            attachments_intro="관련 자료를 검토하여 성능 결과를 정리하세요.",
            format_warning="CSV 이외의 다른 형식이나 설명 문장은 포함하지 마세요.",
        ),
    ),
}


class PromptConfigService:
    """Load and persist prompt configuration for runtime use."""

    def __init__(self, storage_path: Path) -> None:
        self._store = PromptConfigStore(storage_path)

    def _default_configs(self) -> Dict[str, PromptConfig]:
        return {key: value.model_copy(deep=True) for key, value in _DEFAULT_PROMPTS.items()}

    def get_defaults(self) -> Dict[str, Dict[str, Any]]:
        return {
            key: config.model_dump(mode="json", by_alias=True)
            for key, config in self._default_configs().items()
        }

    def list_configs(self) -> Dict[str, PromptConfig]:
        stored = self._store.load_all()
        defaults = self._default_configs()
        merged: Dict[str, PromptConfig] = {}
        for menu_id, default_config in defaults.items():
            raw = stored.get(menu_id)
            base = default_config.model_dump(mode="json", by_alias=True)
            if isinstance(raw, Mapping):
                base = _merge_dict(base, raw)
            merged[menu_id] = PromptConfig.model_validate(base)
        return merged

    def get_config(self, menu_id: str) -> PromptConfig:
        configs = self.list_configs()
        if menu_id not in configs:
            raise KeyError(menu_id)
        return configs[menu_id]

    def update_config(self, menu_id: str, payload: Mapping[str, Any]) -> PromptConfig:
        if menu_id not in _DEFAULT_PROMPTS:
            raise KeyError(menu_id)
        default_config = _DEFAULT_PROMPTS[menu_id]
        base = default_config.model_dump(mode="json", by_alias=True)
        merged = _merge_dict(base, payload)
        validated = PromptConfig.model_validate(merged)
        self._store.save(menu_id, validated.model_dump(mode="json", by_alias=True))
        return validated

    def get_runtime_prompt(self, menu_id: str) -> PromptConfig:
        return self.get_config(menu_id)


__all__ = [
    "PromptConfig",
    "PromptConfigService",
    "PromptBuiltinContext",
    "PromptModelParameters",
    "PromptScaffolding",
    "PromptSection",
    "RenderMode",
]
