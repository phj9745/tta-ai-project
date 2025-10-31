from __future__ import annotations

from .config import Settings, load_settings
from .services.ai_generation import AIGenerationService
from .services.configuration_images import ConfigurationImageService
from .services.prompt_config import PromptConfigService
from .services.prompt_request_log import PromptRequestLogService
from .services.google_drive import GoogleDriveService
from .services.oauth import GoogleOAuthService
from .services.security_report import SecurityReportService
from .token_store import TokenStorage
from openai import OpenAI


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
        request_log_path = self._settings.tokens_path.with_name("prompt_requests.log")
        self._prompt_request_log_service = PromptRequestLogService(request_log_path)
        self._ai_generation_service = AIGenerationService(
            self._settings, self._prompt_config_service, self._prompt_request_log_service
        )
        api_key = self._settings.openai_api_key
        openai_client = OpenAI(api_key=api_key) if api_key else OpenAI()
        self._security_report_service = SecurityReportService(
            drive_service=self._drive_service,
            prompt_config_service=self._prompt_config_service,
            prompt_request_log_service=self._prompt_request_log_service,
            openai_client=openai_client,
        )
        self._configuration_image_service = ConfigurationImageService(self._drive_service)

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

    @property
    def prompt_request_log_service(self) -> PromptRequestLogService:
        return self._prompt_request_log_service

    @property
    def security_report_service(self) -> SecurityReportService:
        return self._security_report_service

    @property
    def configuration_image_service(self) -> ConfigurationImageService:
        return self._configuration_image_service
