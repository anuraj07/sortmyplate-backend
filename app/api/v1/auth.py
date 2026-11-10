import json
from typing import Optional, List
import httpx
from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.base import get_db
from app.db.models import UserDB
from app.repositories.user_repo import user_repo
from app.core.security import create_access_token
from app.core.config import settings
from app.api.deps import get_current_user

router = APIRouter()

class GoogleAuthRequest(BaseModel):
    id_token: Optional[str] = None
    email: Optional[str] = None
    name: Optional[str] = None
    picture: Optional[str] = None
    allergies: Optional[List[str]] = None
    diet_preference: str = "omnivore"

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

@router.post("/google", response_model=AuthResponse)
async def google_sign_in(body: GoogleAuthRequest, session: AsyncSession = Depends(get_db)):
    """
    Production Google Sign-In endpoint.
    Verifies Google ID Token (when provided with GOOGLE_CLIENT_ID configured) or OAuth payload,
    and maps the user to an isolated account with a synthetic medical subject_token.
    """
    email = body.email
    full_name = body.name
    picture = body.picture
    google_sub = None

    if body.id_token:
        # Verify Google ID Token via Google's tokeninfo endpoint
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(
                "https://oauth2.googleapis.com/tokeninfo",
                params={"id_token": body.id_token}
            )
            if resp.status_code != 200:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid Google ID Token"
                )
            token_info = resp.json()
            if settings.GOOGLE_CLIENT_ID and token_info.get("aud") != settings.GOOGLE_CLIENT_ID:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Google ID Token audience mismatch"
                )
            email = token_info.get("email")
            full_name = token_info.get("name") or full_name
            picture = token_info.get("picture") or picture
            google_sub = token_info.get("sub")

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
        diet_preference=body.diet_preference
    )

    token = create_access_token(subject=user.id)
    allergies_list = json.loads(user.allergies) if user.allergies else []

    return AuthResponse(
        access_token=token,
        user_id=user.id,
        email=user.email,
        full_name=user.full_name,
        picture_url=user.picture_url,
        subject_token=user.subject_token,
        allergies=allergies_list,
        diet_preference=user.diet_preference
    )

@router.get("/me", response_model=AuthResponse)
async def get_me(current_user: UserDB = Depends(get_current_user)):
    allergies_list = json.loads(current_user.allergies) if current_user.allergies else []
    return AuthResponse(
        access_token="",
        user_id=current_user.id,
        email=current_user.email,
        full_name=current_user.full_name,
        picture_url=current_user.picture_url,
        subject_token=current_user.subject_token,
        allergies=allergies_list,
        diet_preference=current_user.diet_preference
    )

@router.put("/profile", response_model=AuthResponse)
async def update_profile(
    body: ProfileUpdateRequest,
    current_user: UserDB = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    if body.full_name is not None:
        current_user.full_name = body.full_name
    if body.allergies is not None:
        current_user.allergies = json.dumps([a.lower().strip() for a in body.allergies if a.strip()])
    if body.diet_preference is not None:
        current_user.diet_preference = body.diet_preference

    await session.commit()
    await session.refresh(current_user)

    allergies_list = json.loads(current_user.allergies) if current_user.allergies else []
    return AuthResponse(
        access_token="",
        user_id=current_user.id,
        email=current_user.email,
        full_name=current_user.full_name,
        picture_url=current_user.picture_url,
        subject_token=current_user.subject_token,
        allergies=allergies_list,
        diet_preference=current_user.diet_preference
    )
