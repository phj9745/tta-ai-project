from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    """Application configuration loaded from environment variables."""

    client_id: str
    client_secret: str
    redirect_uri: str
    frontend_redirect_url: str
    tokens_path: Path
    openai_api_key: str
    openai_model: str
    builtin_template_root: Optional[Path] = None

    @property
    def frontend_origin(self) -> str:
        parsed = urlparse(self.frontend_redirect_url)
        if not parsed.scheme:
            return "*"
        return f"{parsed.scheme}://{parsed.netloc}"

    @property
    def has_oauth_credentials(self) -> bool:
        return bool(self.client_id and self.client_secret and self.redirect_uri)


def load_settings() -> Settings:
    tokens_env = os.getenv("GOOGLE_TOKEN_DB_PATH") or os.getenv("GOOGLE_TOKEN_PATH")
    default_tokens_path = Path(__file__).resolve().parent / "google_tokens.db"

    template_root_env = os.getenv("BUILTIN_TEMPLATE_ROOT")
    template_root = Path(template_root_env).expanduser() if template_root_env else None

    return Settings(
        client_id=os.getenv("GOOGLE_CLIENT_ID", ""),
        client_secret=os.getenv("GOOGLE_CLIENT_SECRET", ""),
        redirect_uri=os.getenv("GOOGLE_REDIRECT_URI", ""),
        frontend_redirect_url=os.getenv("FRONTEND_REDIRECT_URL", "http://localhost:5173/"),
        tokens_path=Path(tokens_env) if tokens_env else default_tokens_path,
        openai_api_key=os.getenv("OPENAI_API_KEY", ""),
        openai_model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        builtin_template_root=template_root,
    )
