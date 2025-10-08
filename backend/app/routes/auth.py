from __future__ import annotations

from typing import Optional
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from ..dependencies import get_oauth_service, get_token_storage
from ..services.oauth import GOOGLE_AUTH_ENDPOINT, GOOGLE_SCOPES, GoogleOAuthService
from ..token_store import TokenStorage

router = APIRouter()


@router.get("/auth/google/login")
def google_login(
    oauth_service: GoogleOAuthService = Depends(get_oauth_service),
) -> RedirectResponse:
    oauth_service.ensure_credentials()

    state = oauth_service.create_state()
    params = {
        "client_id": oauth_service.settings.client_id,
        "redirect_uri": oauth_service.settings.redirect_uri,
        "response_type": "code",
        "scope": " ".join(GOOGLE_SCOPES),
        "access_type": "offline",
        "prompt": "consent",
        "include_granted_scopes": "true",
        "state": state,
    }

    auth_url = f"{GOOGLE_AUTH_ENDPOINT}?{urlencode(params)}"
    return RedirectResponse(auth_url)


@router.get("/auth/google/callback")
async def google_callback(
    request: Request,
    oauth_service: GoogleOAuthService = Depends(get_oauth_service),
) -> RedirectResponse:
    oauth_service.ensure_credentials()

    params = request.query_params
    error = params.get("error")
    state = params.get("state")

    if error:
        message = params.get("error_description", "Google 인증이 취소되었습니다.")
        redirect_url = oauth_service.build_frontend_redirect("error", message)
        return RedirectResponse(redirect_url)

    code = params.get("code")
    if not code or not state:
        raise HTTPException(status_code=400, detail="code 또는 state 매개변수가 누락되었습니다.")

    try:
        oauth_service.validate_state(state)
        tokens = await oauth_service.exchange_code_for_tokens(code)
        access_token = tokens.get("access_token")
        if not isinstance(access_token, str) or not access_token:
            raise HTTPException(status_code=502, detail="Google 토큰 발급에 실패했습니다.")

        userinfo = await oauth_service.fetch_userinfo(access_token)
        stored = oauth_service.save_tokens(userinfo, tokens)
    except HTTPException as exc:  # convert to frontend redirect
        detail = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
        redirect_url = oauth_service.build_frontend_redirect("error", detail)
        return RedirectResponse(redirect_url)

    redirect_url = oauth_service.build_frontend_redirect(
        "success",
        message=f"{stored['display_name']} 계정의 토큰이 저장되었습니다.",
    )
    return RedirectResponse(redirect_url)


@router.get("/auth/google/tokens")
def read_tokens(
    google_id: Optional[str] = Query(None, description="조회할 Google 사용자 식별자 (sub)"),
    email: Optional[str] = Query(None, description="조회할 Google 계정 이메일"),
    token_storage: TokenStorage = Depends(get_token_storage),
    oauth_service: GoogleOAuthService = Depends(get_oauth_service),
) -> JSONResponse:
    oauth_service.ensure_credentials()

    if not google_id and not email:
        raise HTTPException(
            status_code=400,
            detail="google_id 또는 email 중 하나는 반드시 제공해야 합니다.",
        )

    stored = None
    if google_id:
        stored = token_storage.load_by_google_id(google_id)
    if stored is None and email:
        stored = token_storage.load_by_email(email)
    if not stored:
        raise HTTPException(status_code=404, detail="요청한 사용자에 대한 저장된 토큰이 없습니다.")

    payload = stored.to_dict()
    payload.pop("access_token", None)
    payload.pop("refresh_token", None)

    return JSONResponse(payload)


@router.get("/auth/google/users")
def list_users(
    token_storage: TokenStorage = Depends(get_token_storage),
    oauth_service: GoogleOAuthService = Depends(get_oauth_service),
) -> JSONResponse:
    oauth_service.ensure_credentials()

    accounts = [account.to_dict() for account in token_storage.list_accounts()]
    return JSONResponse(accounts)


@router.get("/auth/google/callback/success")
def success_page() -> HTMLResponse:
    return HTMLResponse(
        """
        <html>
            <head>
                <meta charset="utf-8" />
                <title>Google 인증 완료</title>
                <style>
                    body { font-family: sans-serif; padding: 48px; text-align: center; }
                    h1 { color: #2563eb; }
                </style>
            </head>
            <body>
                <h1>Google Drive 인증이 완료되었습니다.</h1>
                <p>이 창은 닫으셔도 됩니다.</p>
            </body>
        </html>
        """,
    )
