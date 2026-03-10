from __future__ import annotations

from fastapi import Depends, Request

from .container import Container
from .services.ai_generation import AIGenerationService


def get_container(request: Request) -> Container:
    container = getattr(request.app.state, "container", None)
    if not isinstance(container, Container):
        raise RuntimeError("Application container is not configured on FastAPI app state.")
    return container


def get_ai_generation_service(container: Container = Depends(get_container)) -> AIGenerationService:
    return container.ai_generation_service
