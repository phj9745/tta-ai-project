from __future__ import annotations

from .config import Settings, load_settings
from .services.ai_generation import AIGenerationService
from .services.prompt_config import PromptConfigService
from .services.prompt_request_log import PromptRequestLogService


class Container:
    """Application service container for testcase-only mode."""

    def __init__(self) -> None:
        self._settings = load_settings()
        prompt_storage_path = self._settings.tokens_path.with_name("prompt_configs.json")
        self._prompt_config_service = PromptConfigService(prompt_storage_path)
        request_log_path = self._settings.tokens_path.with_name("prompt_requests.log")
        self._prompt_request_log_service = PromptRequestLogService(request_log_path)
        self._ai_generation_service = AIGenerationService(
            self._settings, self._prompt_config_service, self._prompt_request_log_service
        )

    @property
    def settings(self) -> Settings:
        return self._settings

    @property
    def ai_generation_service(self) -> AIGenerationService:
        return self._ai_generation_service


    @property
    def prompt_config_service(self) -> PromptConfigService:
        return self._prompt_config_service
