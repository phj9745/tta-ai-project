from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any, Dict, Iterable, List, Tuple

from fastapi import HTTPException
from openai import OpenAI

from ..ai_generation import AIGenerationService
from ..prompt_config import PromptConfig, PromptConfigService
from ..prompt_request_log import PromptRequestLogService
from .models import InvictiFinding

logger = logging.getLogger(__name__)

_PROMPT_TEMPLATE_PATTERN = re.compile(r"\{\{\s*([A-Za-z0-9_]+)\s*\}\}")
_DEFAULT_SECURITY_SYSTEM_PROMPT = (
    "당신은 Invicti HTML 보고서를 분석하여 보안 결함을 표준 템플릿에 맞게 요약하는 한국어 보안 분석가입니다. "
    "응답은 항상 JSON 형식이어야 합니다."
)


class SecurityReportAI:
    def __init__(
        self,
        prompt_config_service: PromptConfigService,
        prompt_request_log_service: PromptRequestLogService | None,
        openai_client: OpenAI,
    ) -> None:
        self._prompt_config_service = prompt_config_service
        self._prompt_request_log_service = prompt_request_log_service
        self._openai_client = openai_client

    async def fill_template_field(
        self,
        template: str,
        finding: InvictiFinding,
        *,
        project_id: str,
        placeholder_values: Dict[str, str],
    ) -> str:
        if not template:
            return template
        if not _has_placeholders(template):
            return template

        filled, remaining = _replace_known_placeholders(template, placeholder_values)
        if not remaining:
            return filled

        prompt_payload = await self._call_openai_for_json(
            prompt_id="security-template-fill",
            finding=finding,
            placeholders=remaining,
            context_data=placeholder_values,
            project_id=project_id,
        )
        if not prompt_payload:
            return filled

        result = filled
        for key, value in prompt_payload.items():
            token = f"[{key}]"
            result = result.replace(token, str(value))
        return result

    async def generate_new_finding_payload(
        self,
        finding: InvictiFinding,
        *,
        project_id: str,
        placeholder_values: Dict[str, str],
    ) -> Dict[str, Any]:
        return await self._call_openai_for_json(
            prompt_id="security-new-finding",
            finding=finding,
            placeholders=None,
            context_data=placeholder_values,
            project_id=project_id,
        )

    async def _call_openai_for_json(
        self,
        *,
        prompt_id: str,
        finding: InvictiFinding,
        placeholders: Iterable[str] | None = None,
        context_data: Dict[str, str] | None = None,
        project_id: str | None,
    ) -> Dict[str, Any]:
        prompts = self._build_prompt(
            prompt_id=prompt_id,
            finding=finding,
            placeholders=placeholders,
            context_data=context_data,
        )
        if prompts is None:
            return {}

        system_prompt = ""
        user_prompt = ""
        for message in prompts:
            role = str(message.get("role", ""))
            content = str(message.get("content", ""))
            if role == "system":
                system_prompt = content
            elif role == "user":
                user_prompt = content

        if self._prompt_request_log_service is not None and project_id:
            context_summary = f"{finding.name or '알 수 없는 결함'} (severity: {finding.severity or '?'})"
            try:
                self._prompt_request_log_service.record_request(
                    project_id=project_id,
                    menu_id="security-report",
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    context_summary=context_summary,
                )
            except Exception:  # pragma: no cover - logging failures must not break flow
                logger.exception(
                    "Failed to record security prompt request",
                    extra={"project_id": project_id, "prompt_id": prompt_id},
                )

        try:
            response = await asyncio.to_thread(
                self._openai_client.responses.create,
                model="gpt-4.1-mini",
                input=prompts,
            )
        except Exception as exc:  # pragma: no cover - OpenAI client failure
            logger.exception("OpenAI call failed for prompt %s", prompt_id)
            return {}

        if not response:
            return {}

        text_payload = AIGenerationService._extract_response_text(response)
        if not text_payload:
            return {}
        return _safe_json_loads(text_payload)

    def _build_prompt(
        self,
        *,
        prompt_id: str,
        finding: InvictiFinding,
        placeholders: Iterable[str] | None,
        context_data: Dict[str, str] | None,
    ) -> List[Dict[str, str]] | None:
        placeholder_text = ""
        if placeholders:
            placeholder_text = ", ".join([str(item) for item in placeholders if str(item)])

        context_lines = ""
        if context_data:
            entries: List[str] = []
            seen_keys: set[str] = set()
            for key, value in context_data.items():
                if not isinstance(value, str):
                    continue
                stripped_value = value.strip()
                if not stripped_value:
                    continue
                normalized_key = re.sub(r"\s+", "", str(key)).lower()
                if normalized_key in seen_keys:
                    continue
                seen_keys.add(normalized_key)
                entries.append(f"- {key}: {stripped_value}")
            context_lines = "\n".join(entries)

        try:
            config = self._prompt_config_service.get_runtime_prompt("security-report")
        except KeyError as exc:  # pragma: no cover - configuration should always exist
            logger.exception("Security report prompt configuration is missing.")
            raise HTTPException(
                status_code=500,
                detail="보안성 리포트 프롬프트 구성을 불러오지 못했습니다.",
            ) from exc

        values = _build_prompt_values(
            finding=finding,
            context_lines=context_lines,
            placeholder_text=placeholder_text,
        )

        if prompt_id == "security-new-finding":
            system = _render_template(config.system_prompt, values).strip() or _DEFAULT_SECURITY_SYSTEM_PROMPT
            parts, details_ref, _ = _assemble_prompt_parts(
                config,
                values,
                use_sections=True,
                use_heading=True,
                use_intro=True,
                use_closing=True,
                use_warning=True,
                track_placeholders=False,
            )
            if not details_ref:
                parts.append(values["finding_details_block"])
            user = "\n\n".join(part for part in parts if part)
        elif prompt_id == "security-template-fill":
            system = _render_template(config.system_prompt, values).strip() or _DEFAULT_SECURITY_SYSTEM_PROMPT
            parts, details_ref, placeholders_ref = _assemble_prompt_parts(
                config,
                values,
                use_sections=False,
                use_heading=False,
                use_intro=False,
                use_closing=True,
                use_warning=True,
                track_placeholders=True,
            )
            if not placeholders_ref:
                placeholder_line = values["placeholder_list"] or "(플레이스홀더 없음)"
                parts.insert(0, f"플레이스홀더: {placeholder_line}")
            if not details_ref:
                parts.append(values["finding_details_block"])
            user = "\n\n".join(part for part in parts if part)
        else:
            return None

        return [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]


def _build_prompt_values(
    *,
    finding: InvictiFinding,
    context_lines: str,
    placeholder_text: str,
) -> Dict[str, str]:
    context_block = context_lines or "- (제공된 추가 정보 없음)"
    finding_details = _format_finding_details_block(finding, context_block)
    return {
        "finding_name": finding.name or "",
        "finding_severity": finding.severity or "",
        "finding_path": finding.path or "",
        "finding_description": finding.description_text or "",
        "finding_evidence": finding.evidence_text or "없음",
        "context_block": context_block,
        "finding_details_block": finding_details,
        "placeholder_list": placeholder_text or "",
    }


def _format_finding_details_block(finding: InvictiFinding, context_block: str) -> str:
    name = finding.name or "-"
    severity = finding.severity or "-"
    path = finding.path or "-"
    description = finding.description_text or "-"
    evidence = finding.evidence_text or "없음"
    return (
        f"제목: {name}\n"
        f"위험도: {severity}\n"
        f"경로: {path}\n"
        f"상세 설명:\n{description}\n"
        f"증적:\n{evidence}\n"
        f"추가 참고 정보:\n{context_block}"
    )


def _assemble_prompt_parts(
    config: PromptConfig,
    values: Dict[str, str],
    *,
    use_sections: bool,
    use_heading: bool,
    use_intro: bool,
    use_closing: bool,
    use_warning: bool,
    track_placeholders: bool,
) -> Tuple[List[str], bool, bool]:
    parts: List[str] = []
    details_referenced = False
    placeholders_referenced = False

    base, base_details, base_placeholders = _render_fragment(
        config.user_prompt,
        values,
        track_details=True,
        track_placeholders=track_placeholders,
    )
    if base:
        parts.append(base)
    details_referenced = details_referenced or base_details
    placeholders_referenced = placeholders_referenced or base_placeholders

    if use_sections:
        for section in config.user_prompt_sections:
            if not section.enabled:
                continue
            label, label_details, label_placeholders = _render_fragment(
                section.label,
                values,
                track_details=True,
                track_placeholders=track_placeholders,
            )
            content, content_details, content_placeholders = _render_fragment(
                section.content,
                values,
                track_details=True,
                track_placeholders=track_placeholders,
            )
            combined = "\n".join(part for part in [label, content] if part).strip()
            if combined:
                parts.append(combined)
            details_referenced = details_referenced or label_details or content_details
            placeholders_referenced = (
                placeholders_referenced or label_placeholders or content_placeholders
            )

    if use_heading:
        heading, heading_details, heading_placeholders = _render_fragment(
            config.scaffolding.attachments_heading,
            values,
            track_details=True,
            track_placeholders=track_placeholders,
        )
        if heading:
            parts.append(heading)
        details_referenced = details_referenced or heading_details
        placeholders_referenced = placeholders_referenced or heading_placeholders

    if use_intro:
        intro, intro_details, intro_placeholders = _render_fragment(
            config.scaffolding.attachments_intro,
            values,
            track_details=True,
            track_placeholders=track_placeholders,
        )
        if intro:
            parts.append(intro)
        details_referenced = details_referenced or intro_details
        placeholders_referenced = placeholders_referenced or intro_placeholders

    if use_closing:
        closing, closing_details, closing_placeholders = _render_fragment(
            config.scaffolding.closing_note,
            values,
            track_details=True,
            track_placeholders=track_placeholders,
        )
        if closing:
            parts.append(closing)
        details_referenced = details_referenced or closing_details
        placeholders_referenced = placeholders_referenced or closing_placeholders

    if use_warning:
        warning, warning_details, warning_placeholders = _render_fragment(
            config.scaffolding.format_warning,
            values,
            track_details=True,
            track_placeholders=track_placeholders,
        )
        if warning:
            parts.append(warning)
        details_referenced = details_referenced or warning_details
        placeholders_referenced = placeholders_referenced or warning_placeholders

    return parts, details_referenced, placeholders_referenced


def _render_fragment(
    template: str,
    values: Dict[str, str],
    *,
    track_details: bool,
    track_placeholders: bool,
) -> Tuple[str, bool, bool]:
    raw = (template or "").strip()
    if not raw:
        return "", False, False
    details_referenced = track_details and "{{finding_details_block}}" in template
    placeholders_referenced = track_placeholders and "{{placeholder_list}}" in template
    rendered = _render_template(raw, values).strip()
    return rendered, details_referenced, placeholders_referenced


def _render_template(template: str, values: Dict[str, str]) -> str:
    def _replace(match: re.Match[str]) -> str:
        key = match.group(1)
        return str(values.get(key, ""))

    return _PROMPT_TEMPLATE_PATTERN.sub(_replace, template)


def _replace_known_placeholders(
    template: str,
    placeholder_values: Dict[str, str],
) -> Tuple[str, List[str]]:
    placeholders = _extract_placeholders(template)
    if not placeholders:
        return template, []

    result = template
    unresolved: List[str] = []
    for key in placeholders:
        token = f"[{key}]"
        if key in placeholder_values:
            value = placeholder_values[key]
            replacement = str(value).strip()
            result = result.replace(token, replacement)
        else:
            unresolved.append(key)
    return result, unresolved


def _extract_placeholders(template: str) -> List[str]:
    return [match.strip("[]") for match in re.findall(r"\[[^\[\]]+\]", template or "")]


def _has_placeholders(template: str) -> bool:
    return bool(re.search(r"\[[^\[\]]+\]", template or ""))


def _safe_json_loads(payload: str) -> Dict[str, Any]:
    try:
        return json.loads(payload)
    except json.JSONDecodeError:
        logger.warning("Failed to decode JSON payload from OpenAI response.")
        return {}
