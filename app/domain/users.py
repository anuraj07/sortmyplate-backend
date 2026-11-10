import uuid
from datetime import datetime, timezone
from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict

class UserBase(BaseModel):
    email: str
    full_name: str
    diet_preference: str = "omnivore" # omnivore, vegetarian, vegan, pescatarian
    allergies: List[str] = Field(default_factory=list) # e.g. ["peanuts", "shellfish", "dairy", "gluten"]

class UserCreate(UserBase):
    password: str

class UserLogin(BaseModel):
    email: str
    password: str

class UserResponse(UserBase):
    model_config = ConfigDict(from_attributes=True)
    id: str
    subject_token: str
    created_at: datetime

class UserInDB(UserBase):
    id: str
    hashed_password: str
    subject_token: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class GroupCreate(BaseModel):
    name: str # e.g. "Flat 4B", "Smith Family", "Solo Mode"

class GroupJoin(BaseModel):
    invite_code: str

class GroupResponse(BaseModel):
    id: str
    name: str
    invite_code: str
    owner_id: str
    member_ids: List[str]
    created_at: datetime

class GroupInDB(BaseModel):
    id: str = Field(default_factory=lambda: f"grp_{uuid.uuid4().hex[:8]}")
    name: str
    invite_code: str = Field(default_factory=lambda: uuid.uuid4().hex[:6].upper())
    owner_id: str
    member_ids: List[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
