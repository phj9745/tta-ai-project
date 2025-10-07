from __future__ import annotations

from typing import Dict

from fastapi import APIRouter, Depends, HTTPException, Query

from ..dependencies import (
    get_prompt_config_service,
    get_prompt_request_log_service,
)
from ..services.prompt_config import PromptConfig, PromptConfigService
from ..services.prompt_request_log import PromptRequestLogService

router = APIRouter(prefix="/admin/prompts", tags=["prompt-config"])


@router.get("/logs")
def list_prompt_request_logs(
    limit: int = Query(50, ge=1, le=200, description="가져올 로그 수"),
    log_service: PromptRequestLogService = Depends(get_prompt_request_log_service),
) -> Dict[str, list[dict[str, str]]]:
    entries = log_service.list_recent(limit=limit)
    return {"logs": [entry.to_dict() for entry in entries]}


@router.get("", response_model=None)
def list_prompt_configs(
    prompt_service: PromptConfigService = Depends(get_prompt_config_service),
) -> Dict[str, Dict[str, Dict]]:
    configs = prompt_service.list_configs()
    defaults = prompt_service.get_defaults()
    return {
        "current": {
            key: config.model_dump(mode="json", by_alias=True)
            for key, config in configs.items()
        },
        "defaults": defaults,
    }


@router.get("/{menu_id}")
def get_prompt_config(
    menu_id: str,
    prompt_service: PromptConfigService = Depends(get_prompt_config_service),
) -> Dict[str, Dict]:
    try:
        config = prompt_service.get_config(menu_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="알 수 없는 메뉴입니다.") from exc
    return {"config": config.model_dump(mode="json", by_alias=True)}


@router.put("/{menu_id}")
def update_prompt_config(
    menu_id: str,
    payload: PromptConfig,
    prompt_service: PromptConfigService = Depends(get_prompt_config_service),
) -> Dict[str, Dict]:
    try:
        updated = prompt_service.update_config(
            menu_id, payload.model_dump(mode="json", by_alias=True)
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="알 수 없는 메뉴입니다.") from exc
    return {"config": updated.model_dump(mode="json", by_alias=True)}
