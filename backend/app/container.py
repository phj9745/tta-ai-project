from __future__ import annotations

from .config import load_settings
from .services.google_drive import GoogleDriveService
from .services.oauth import GoogleOAuthService
from .token_store import TokenStorage

settings = load_settings()

token_storage = TokenStorage(settings.tokens_path)

oauth_service = GoogleOAuthService(settings, token_storage)

drive_service = GoogleDriveService(settings, token_storage, oauth_service)
