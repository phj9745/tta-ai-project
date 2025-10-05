from __future__ import annotations

from .config import Settings, load_settings
from .services.ai_generation import AIGenerationService
from .services.prompt_config import PromptConfigService
from .services.google_drive import GoogleDriveService
from .services.oauth import GoogleOAuthService
from .token_store import TokenStorage


class Container:
    """Application service container for dependency management."""

    def __init__(self) -> None:
        self._settings = load_settings()
        self._token_storage = TokenStorage(self._settings.tokens_path)
        self._oauth_service = GoogleOAuthService(self._settings, self._token_storage)
        self._drive_service = GoogleDriveService(
            self._settings, self._token_storage, self._oauth_service
        )
        prompt_storage_path = self._settings.tokens_path.with_name("prompt_configs.json")
        self._prompt_config_service = PromptConfigService(prompt_storage_path)
        self._ai_generation_service = AIGenerationService(
            self._settings, self._prompt_config_service
        )

    @property
    def settings(self) -> Settings:
        return self._settings

    @property
    def token_storage(self) -> TokenStorage:
        return self._token_storage

    @property
    def oauth_service(self) -> GoogleOAuthService:
        return self._oauth_service

    @property
    def drive_service(self) -> GoogleDriveService:
        return self._drive_service

    @property
    def ai_generation_service(self) -> AIGenerationService:
        return self._ai_generation_service

    @property
    def prompt_config_service(self) -> PromptConfigService:
        return self._prompt_config_service
