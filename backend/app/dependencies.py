from __future__ import annotations

from fastapi import Depends, Request

from .container import Container
from .services.ai_generation import AIGenerationService
from .services.configuration_images import ConfigurationImageService
from .services.google_drive import GoogleDriveService
from .services.prompt_config import PromptConfigService
from .services.prompt_request_log import PromptRequestLogService
from .services.oauth import GoogleOAuthService
from .services.security_report import SecurityReportService
from .token_store import TokenStorage


def get_container(request: Request) -> Container:
    container = getattr(request.app.state, "container", None)
    if not isinstance(container, Container):
        raise RuntimeError("Application container is not configured on FastAPI app state.")
    return container


def get_token_storage(container: Container = Depends(get_container)) -> TokenStorage:
    return container.token_storage


def get_oauth_service(container: Container = Depends(get_container)) -> GoogleOAuthService:
    return container.oauth_service


def get_drive_service(container: Container = Depends(get_container)) -> GoogleDriveService:
    return container.drive_service


def get_ai_generation_service(
    container: Container = Depends(get_container),
) -> AIGenerationService:
    return container.ai_generation_service


def get_prompt_config_service(
    container: Container = Depends(get_container),
) -> PromptConfigService:
    return container.prompt_config_service


def get_prompt_request_log_service(
    container: Container = Depends(get_container),
) -> PromptRequestLogService:
    return container.prompt_request_log_service


def get_security_report_service(
    container: Container = Depends(get_container),
) -> SecurityReportService:
    return container.security_report_service


def get_configuration_image_service(
    container: Container = Depends(get_container),
) -> ConfigurationImageService:
    return container.configuration_image_service
