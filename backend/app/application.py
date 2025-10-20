from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .container import Container
from .routes import auth_router, drive_router, prompt_router


def create_app() -> FastAPI:
    """Create and configure a FastAPI application instance."""

    container = Container()

    app = FastAPI()
    app.state.container = container

    frontend_origin = container.settings.frontend_origin
    allow_origins = [frontend_origin] if frontend_origin != "*" else ["*"]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allow_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["Content-Disposition"]
    )

    app.include_router(auth_router)
    app.include_router(drive_router)
    app.include_router(prompt_router)

    @app.get("/")
    def read_root() -> dict[str, str]:
        return {
            "project": "TTA-AI-Project",
            "status": "running",
        }

    return app
