import html
import json
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional, List
from urllib.parse import urlencode
import httpx
from fastapi import APIRouter, HTTPException, Request, status, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.base import get_db
from app.db.models import UserDB, OAuthSessionDB
from app.repositories.user_repo import user_repo
from app.core.crypto import fle_service
from app.core.security import create_access_token, resolve_public_base_url
from app.core.config import settings
from app.api.deps import get_current_user

router = APIRouter()

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"
GOOGLE_TOKENINFO_URL = "https://oauth2.googleapis.com/tokeninfo"
OAUTH_STATE_TTL_MINUTES = 10


class GoogleAuthRequest(BaseModel):
    id_token: Optional[str] = None
    google_access_token: Optional[str] = None
    email: Optional[str] = None
    name: Optional[str] = None
    picture: Optional[str] = None
    allergies: Optional[List[str]] = None
    diet_preference: Optional[str] = None


class OAuthExchangeRequest(BaseModel):
    state: str
    exchange_code: Optional[str] = None


class ProfileUpdateRequest(BaseModel):
    full_name: Optional[str] = None
    allergies: Optional[List[str]] = None
    diet_preference: Optional[str] = None


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    email: str
    full_name: str
    picture_url: Optional[str] = None
    subject_token: str
    allergies: List[str] = []
    diet_preference: str


class OAuthSessionPollResponse(BaseModel):
    status: str
    auth: Optional[AuthResponse] = None
    error: Optional[str] = None


def _build_auth_response(user: UserDB, token: str = "") -> AuthResponse:
    allergies_list = json.loads(user.allergies) if user.allergies else []
    return AuthResponse(
        access_token=token,
        user_id=user.id,
        email=user.email,
        full_name=user.full_name,
        picture_url=user.picture_url,
        subject_token=user.subject_token,
        allergies=allergies_list,
        diet_preference=user.diet_preference,
    )


def _validate_redirect_target(redirect_to: Optional[str], base_url: str) -> Optional[str]:
    if not redirect_to:
        return None
    cleaned = redirect_to.strip()
    if cleaned.startswith("/") and not cleaned.startswith("//"):
        return f"{base_url}{cleaned}"
    if cleaned.startswith(base_url):
        return cleaned
    if cleaned.startswith("sortmyplate://auth/callback"):
        return cleaned
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Invalid redirect_to URL. Only same-origin paths or sortmyplate://auth/callback are allowed.",
    )


def _is_expired(dt: datetime) -> bool:
    exp = dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) > exp


async def _exchange_google_code_for_profile(code: str, redirect_uri: str) -> dict:
    """
    Exchanges an OAuth 2.0 authorization code with Google and fetches verified
    user profile claims (email, name, picture, sub) directly from Google.
    """
    async with httpx.AsyncClient(timeout=10.0) as client:
        token_resp = await client.post(
            GOOGLE_TOKEN_URL,
            data={
                "code": code,
                "client_id": settings.GOOGLE_CLIENT_ID.strip(),
                "client_secret": settings.GOOGLE_CLIENT_SECRET.strip(),
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            },
        )
        if token_resp.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Failed to exchange authorization code with Google.",
            )
        token_data = token_resp.json()
        google_access_token = token_data.get("access_token")
        id_token = token_data.get("id_token")

        profile: dict = {}
        if google_access_token:
            userinfo_resp = await client.get(
                GOOGLE_USERINFO_URL,
                headers={"Authorization": f"Bearer {google_access_token}"},
            )
            if userinfo_resp.status_code == 200:
                profile = userinfo_resp.json()

        if (not profile.get("email")) and id_token:
            info_resp = await client.get(GOOGLE_TOKENINFO_URL, params={"id_token": id_token})
            if info_resp.status_code == 200:
                token_info = info_resp.json()
                expected_client_id = settings.GOOGLE_CLIENT_ID.strip()
                if expected_client_id and token_info.get("aud") != expected_client_id:
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Google ID Token audience mismatch.",
                    )
                profile = {**token_info, **profile}

        if not profile.get("email"):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Google account did not return an email address.",
            )
        if profile.get("email_verified") is False or profile.get("email_verified") == "false":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Google email address is not verified.",
            )
        return profile


def _render_oauth_status_html(
    title: str,
    subtitle: str,
    badge: str = "SortMyPlate Zero-Trust Auth",
    is_error: bool = False,
    popup_origin: Optional[str] = None,
    post_message_payload: Optional[dict] = None,
    deep_link_url: Optional[str] = None,
) -> HTMLResponse:
    safe_title = html.escape(title)
    safe_subtitle = html.escape(subtitle)
    safe_badge = html.escape(badge)
    accent = "#d64545" if is_error else "#2b9a5b"

    script_block = ""
    if post_message_payload and popup_origin:
        payload_js = json.dumps(post_message_payload)
        origin_js = json.dumps(popup_origin)
        script_block = f"""
        <script>
          (function() {{
            try {{
              if (window.opener && !window.opener.closed) {{
                window.opener.postMessage({payload_js}, {origin_js});
                setTimeout(function() {{ window.close(); }}, 550);
              }}
            }} catch (e) {{}}
          }})();
        </script>
        """
    elif deep_link_url:
        href_js = json.dumps(deep_link_url)
        script_block = f"""
        <script>
          setTimeout(function() {{ window.location.href = {href_js}; }}, 250);
        </script>
        """

    action_link = ""
    if deep_link_url:
        safe_href = html.escape(deep_link_url, quote=True)
        action_link = f'<a class="btn" href="{safe_href}">Return to SortMyPlate</a>'

    content = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{safe_title}</title>
  <style>
    body {{
      margin: 0;
      min-height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
      background: linear-gradient(160deg, #f3f7f2 0%, #e1ece0 100%);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      color: #141d18;
      padding: 24px;
    }}
    .card {{
      max-width: 440px;
      width: 100%;
      background: #ffffff;
      border: 1px solid #d9e5d7;
      border-radius: 24px;
      padding: 32px;
      text-align: center;
      box-shadow: 0 20px 50px rgba(20, 38, 28, 0.08);
    }}
    .badge {{
      display: inline-block;
      padding: 6px 14px;
      border-radius: 999px;
      background: rgba(43, 154, 91, 0.12);
      color: {accent};
      font-size: 12px;
      font-weight: 700;
      margin-bottom: 14px;
    }}
    h1 {{ font-size: 22px; margin: 0 0 10px 0; }}
    p {{ font-size: 14px; color: #54635b; line-height: 1.6; margin: 0 0 20px 0; }}
    .btn {{
      display: inline-block;
      padding: 12px 24px;
      border-radius: 999px;
      background: #2b9a5b;
      color: #ffffff;
      text-decoration: none;
      font-weight: 700;
      font-size: 14px;
    }}
  </style>
</head>
<body>
  <div class="card">
    <div class="badge">{safe_badge}</div>
    <h1>{safe_title}</h1>
    <p>{safe_subtitle}</p>
    {action_link}
  </div>
  {script_block}
</body>
</html>"""
    return HTMLResponse(content=content, status_code=200 if not is_error else 400)


@router.get("/google/login")
async def google_oauth_login(
    request: Request,
    state: Optional[str] = None,
    platform: str = "web",
    redirect_to: Optional[str] = None,
    response_mode: Optional[str] = None,
    session: AsyncSession = Depends(get_db),
):
    """
    Initiates a real Google OAuth 2.0 Authorization Code flow so the app can fetch
    the user's verified email, full name, and avatar directly from Google.
    """
    base_url = resolve_public_base_url(request)
    client_id = settings.GOOGLE_CLIENT_ID.strip()
    client_secret = settings.GOOGLE_CLIENT_SECRET.strip()
    callback_uri = settings.GOOGLE_REDIRECT_URI.strip() or f"{base_url}{settings.API_V1_STR}/auth/google/callback"

    if not client_id or not client_secret:
        msg = (
            f"Google OAuth 2.0 is not configured on this server yet. "
            f"Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET environment variables and add "
            f"{callback_uri} as an Authorized Redirect URI in Google Cloud Console."
        )
        if response_mode == "json":
            raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=msg)
        return _render_oauth_status_html(
            title="Google OAuth Setup Required",
            subtitle=msg,
            badge="Configuration Needed",
            is_error=True,
        )

    validated_redirect = _validate_redirect_target(redirect_to, base_url)
    oauth_state = state.strip() if state and len(state.strip()) >= 16 else secrets.token_urlsafe(24)

    now = datetime.now(timezone.utc)
    oauth_session = OAuthSessionDB(
        state=oauth_state,
        platform=(platform or "web").lower(),
        client_redirect=validated_redirect,
        callback_uri=callback_uri,
        status="pending",
        expires_at=now + timedelta(minutes=OAUTH_STATE_TTL_MINUTES),
    )
    session.add(oauth_session)
    await session.commit()

    query = urlencode(
        {
            "client_id": client_id,
            "redirect_uri": callback_uri,
            "response_type": "code",
            "scope": "openid email profile",
            "state": oauth_state,
            "access_type": "online",
            "prompt": "select_account",
        }
    )
    google_url = f"{GOOGLE_AUTH_URL}?{query}"

    if response_mode == "json":
        return {
            "auth_url": google_url,
            "state": oauth_state,
            "callback_uri": callback_uri,
        }
    return RedirectResponse(url=google_url, status_code=status.HTTP_302_FOUND)


@router.get("/google/callback")
async def google_oauth_callback(
    request: Request,
    code: Optional[str] = None,
    state: Optional[str] = None,
    error: Optional[str] = None,
    session: AsyncSession = Depends(get_db),
):
    """
    Google OAuth 2.0 callback handler. Exchanges Google's code for user info,
    creates/updates the user with their Google email, name, and avatar, and
    seals an encrypted one-time AuthResponse for the client to exchange.
    """
    if not state:
        return _render_oauth_status_html(
            title="Missing OAuth State",
            subtitle="Could not verify your Google Sign-In session. Please return to SortMyPlate and try again.",
            badge="Auth Error",
            is_error=True,
        )

    stmt = select(OAuthSessionDB).where(OAuthSessionDB.state == state)
    result = await session.execute(stmt)
    oauth_row = result.scalars().first()

    if not oauth_row or oauth_row.status != "pending" or _is_expired(oauth_row.expires_at):
        return _render_oauth_status_html(
            title="Sign-In Session Expired",
            subtitle="This Google sign-in link has expired or already been used. Please try again from SortMyPlate.",
            badge="Session Expired",
            is_error=True,
        )

    base_url = resolve_public_base_url(request)

    if error or not code:
        oauth_row.status = "error"
        oauth_row.error_message = error or "Google authorization was cancelled."
        await session.commit()

        if oauth_row.platform == "popup":
            return _render_oauth_status_html(
                title="Google Sign-In Cancelled",
                subtitle=oauth_row.error_message,
                badge="Cancelled",
                is_error=True,
                popup_origin=base_url,
                post_message_payload={
                    "type": "sortmyplate_google_auth",
                    "state": state,
                    "error": oauth_row.error_message,
                },
            )
        return _render_oauth_status_html(
            title="Google Sign-In Not Completed",
            subtitle=oauth_row.error_message,
            badge="Cancelled",
            is_error=True,
        )

    try:
        profile = await _exchange_google_code_for_profile(code=code, redirect_uri=oauth_row.callback_uri)
    except HTTPException as exc:
        oauth_row.status = "error"
        oauth_row.error_message = str(exc.detail)
        await session.commit()
        return _render_oauth_status_html(
            title="Google Verification Failed",
            subtitle=str(exc.detail),
            badge="Verification Error",
            is_error=True,
        )

    email = profile["email"]
    full_name = (
        profile.get("name")
        or " ".join(part for part in [profile.get("given_name"), profile.get("family_name")] if part).strip()
        or email.split("@")[0].capitalize()
    )
    picture = profile.get("picture")
    google_sub = profile.get("sub") or f"google_oauth2_{email.lower().strip()}"

    user = await user_repo.create_or_update_google_user(
        session=session,
        email=email,
        full_name=full_name,
        google_sub=google_sub,
        picture_url=picture,
    )

    jwt_token = create_access_token(subject=user.id)
    auth_payload = _build_auth_response(user, token=jwt_token)
    exchange_code = secrets.token_urlsafe(32)

    oauth_row.exchange_code = exchange_code
    oauth_row.encrypted_auth_payload = fle_service.encrypt_json(auth_payload.model_dump())
    oauth_row.status = "completed"
    await session.commit()

    if oauth_row.platform == "popup":
        return _render_oauth_status_html(
            title=f"Welcome, {full_name}",
            subtitle=f"Signed in as {email}. Returning you to SortMyPlate...",
            badge="Google Connected",
            popup_origin=base_url,
            post_message_payload={
                "type": "sortmyplate_google_auth",
                "state": state,
                "exchange_code": exchange_code,
            },
        )

    if oauth_row.platform in {"android", "ios"}:
        deep_link_base = oauth_row.client_redirect or "sortmyplate://auth/callback"
        separator = "&" if "?" in deep_link_base else "?"
        deep_link = f"{deep_link_base}{separator}{urlencode({'state': state, 'exchange_code': exchange_code})}"
        return _render_oauth_status_html(
            title=f"Welcome, {full_name}",
            subtitle=f"Connected {email}. Returning to the SortMyPlate app...",
            badge="Google Connected",
            deep_link_url=deep_link,
        )

    if oauth_row.platform == "wasm":
        return _render_oauth_status_html(
            title=f"Welcome, {full_name}",
            subtitle=f"Signed in as {email}. Return to your SortMyPlate tab — your session is synced automatically.",
            badge="Google Connected",
        )

    target_base = oauth_row.client_redirect or f"{base_url}/"
    separator = "&" if "?" in target_base else "?"
    redirect_url = f"{target_base}{separator}{urlencode({'oauth_state': state, 'oauth_code': exchange_code})}"
    return RedirectResponse(url=redirect_url, status_code=status.HTTP_302_FOUND)


@router.post("/google/exchange", response_model=AuthResponse)
async def exchange_google_oauth_session(
    body: OAuthExchangeRequest,
    session: AsyncSession = Depends(get_db),
):
    """
    Exchanges a completed OAuth state + one-time exchange_code for the user's
    AuthResponse (email, full_name, picture_url, access_token, subject_token).
    """
    stmt = select(OAuthSessionDB).where(OAuthSessionDB.state == body.state)
    result = await session.execute(stmt)
    oauth_row = result.scalars().first()

    if not oauth_row:
        raise HTTPException(status_code=404, detail="OAuth session not found")
    if _is_expired(oauth_row.expires_at):
        raise HTTPException(status_code=410, detail="OAuth session expired")
    if oauth_row.status == "error":
        raise HTTPException(status_code=401, detail=oauth_row.error_message or "Google sign-in failed")
    if oauth_row.status != "completed" or not oauth_row.encrypted_auth_payload:
        raise HTTPException(status_code=409, detail="OAuth session is not ready or already consumed")

    if oauth_row.exchange_code:
        if not body.exchange_code or not secrets.compare_digest(oauth_row.exchange_code, body.exchange_code):
            raise HTTPException(status_code=403, detail="Invalid OAuth exchange code")

    decrypted = fle_service.decrypt_json(oauth_row.encrypted_auth_payload)
    oauth_row.status = "consumed"
    oauth_row.encrypted_auth_payload = None
    oauth_row.exchange_code = None
    await session.commit()

    return AuthResponse(**decrypted)


@router.get("/google/session/{oauth_state}", response_model=OAuthSessionPollResponse)
async def poll_google_oauth_session(
    oauth_state: str,
    session: AsyncSession = Depends(get_db),
):
    """
    Polled by native/Wasm clients after opening the Google consent page in a system
    browser/tab. Consumes and clears the encrypted AuthResponse once picked up.
    """
    if len(oauth_state.strip()) < 16:
        raise HTTPException(status_code=400, detail="Invalid OAuth state parameter")

    stmt = select(OAuthSessionDB).where(OAuthSessionDB.state == oauth_state)
    result = await session.execute(stmt)
    oauth_row = result.scalars().first()

    if not oauth_row:
        raise HTTPException(status_code=404, detail="OAuth session not found")
    if _is_expired(oauth_row.expires_at):
        return OAuthSessionPollResponse(status="error", error="Google Sign-In session expired")
    if oauth_row.status == "pending":
        return OAuthSessionPollResponse(status="pending")
    if oauth_row.status == "error":
        return OAuthSessionPollResponse(status="error", error=oauth_row.error_message or "Google Sign-In failed")
    if oauth_row.status == "consumed":
        return OAuthSessionPollResponse(status="consumed")

    if oauth_row.status == "completed" and oauth_row.encrypted_auth_payload:
        decrypted = fle_service.decrypt_json(oauth_row.encrypted_auth_payload)
        oauth_row.status = "consumed"
        oauth_row.encrypted_auth_payload = None
        oauth_row.exchange_code = None
        await session.commit()
        return OAuthSessionPollResponse(status="completed", auth=AuthResponse(**decrypted))

    return OAuthSessionPollResponse(status="pending")


@router.post("/google", response_model=AuthResponse)
async def google_sign_in(body: GoogleAuthRequest, session: AsyncSession = Depends(get_db)):
    """
    Google Sign-In endpoint supporting Google Identity Services ID Tokens (`id_token`)
    or OAuth profile claims, extracting email, full name, and Google avatar picture.
    """
    email = body.email
    full_name = body.name
    picture = body.picture
    google_sub = None

    if body.id_token:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(GOOGLE_TOKENINFO_URL, params={"id_token": body.id_token})
            if resp.status_code != 200:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid Google ID Token",
                )
            token_info = resp.json()
            expected_client_id = settings.GOOGLE_CLIENT_ID.strip()
            if expected_client_id and token_info.get("aud") != expected_client_id:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Google ID Token audience mismatch",
                )
            if token_info.get("email_verified") is False or token_info.get("email_verified") == "false":
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Google email address is not verified",
                )
            email = token_info.get("email")
            full_name = token_info.get("name") or full_name
            picture = token_info.get("picture") or picture
            google_sub = token_info.get("sub")
    elif body.google_access_token:
        async with httpx.AsyncClient(timeout=8.0) as client:
            userinfo_resp = await client.get(
                GOOGLE_USERINFO_URL,
                headers={"Authorization": f"Bearer {body.google_access_token}"},
            )
            if userinfo_resp.status_code != 200:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid Google OAuth access token",
                )
            profile = userinfo_resp.json()
            if profile.get("email_verified") is False or profile.get("email_verified") == "false":
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Google email address is not verified",
                )
            email = profile.get("email")
            full_name = profile.get("name") or full_name
            picture = profile.get("picture") or picture
            google_sub = profile.get("sub")

    if not email:
        raise HTTPException(status_code=400, detail="Google email or valid id_token required")

    google_sub = google_sub or f"google_oauth2_{email.lower().strip()}"
    full_name = full_name or email.split("@")[0].capitalize()

    user = await user_repo.create_or_update_google_user(
        session=session,
        email=email,
        full_name=full_name,
        google_sub=google_sub,
        picture_url=picture,
        allergies=body.allergies,
        diet_preference=body.diet_preference,
    )

    token = create_access_token(subject=user.id)
    return _build_auth_response(user, token=token)


@router.get("/me", response_model=AuthResponse)
async def get_me(current_user: UserDB = Depends(get_current_user)):
    return _build_auth_response(current_user)


@router.put("/profile", response_model=AuthResponse)
async def update_profile(
    body: ProfileUpdateRequest,
    current_user: UserDB = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    if body.full_name is not None:
        current_user.full_name = body.full_name.strip() or current_user.full_name
    if body.allergies is not None:
        current_user.allergies = json.dumps([a.lower().strip() for a in body.allergies if a.strip()])
    if body.diet_preference is not None:
        current_user.diet_preference = body.diet_preference.strip()

    await session.commit()
    await session.refresh(current_user)
    return _build_auth_response(current_user)
