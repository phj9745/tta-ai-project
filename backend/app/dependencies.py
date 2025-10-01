from __future__ import annotations

from fastapi import Depends, Request

from .container import Container
from .services.ai_generation import AIGenerationService
from .services.google_drive import GoogleDriveService
from .services.oauth import GoogleOAuthService
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
