from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .container import settings
from .routes import auth_router, drive_router

app = FastAPI()

allow_origins = [settings.frontend_origin] if settings.frontend_origin != "*" else ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(drive_router)


@app.get("/")
def read_root() -> dict[str, str]:
    return {
        "project": "TTA-AI-Project",
        "status": "running",
    }
