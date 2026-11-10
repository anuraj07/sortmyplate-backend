import json
from typing import Optional, List
from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.base import get_db
from app.db.models import UserDB
from app.repositories.user_repo import user_repo
from app.core.security import create_access_token
from app.api.deps import get_current_user

router = APIRouter()

class GoogleAuthRequest(BaseModel):
    id_token: Optional[str] = None
    email: Optional[str] = None
    name: Optional[str] = None
    picture: Optional[str] = None

class GoogleDevLoginRequest(BaseModel):
    email: str = "alex.demo@gmail.com"
    full_name: str = "Alex Demo"
    allergies: List[str] = []
    diet_preference: str = "omnivore"

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
    Accepts Google OAuth2 payload and maps it to an isolated account with a synthetic medical subject_token.
    """
    if not body.email:
        raise HTTPException(status_code=400, detail="Google email required")
    
    google_sub = f"google_oauth2_{body.email.lower()}"
    full_name = body.name or body.email.split("@")[0].capitalize()
    
    user = await user_repo.create_or_update_google_user(
        session=session,
        email=body.email,
        full_name=full_name,
        google_sub=google_sub,
        picture_url=body.picture
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

@router.post("/google/dev-login", response_model=AuthResponse)
async def google_dev_login(
    body: GoogleDevLoginRequest,
    session: AsyncSession = Depends(get_db)
):
    """
    1-Click Google Sign-In Simulation for easy frontend and automated testing.
    Defaults to the pre-seeded Dummy User (Alex Demo).
    """
    google_sub = f"google_oauth2_{body.email.lower()}"
    user = await user_repo.create_or_update_google_user(
        session=session,
        email=body.email,
        full_name=body.full_name,
        google_sub=google_sub,
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
