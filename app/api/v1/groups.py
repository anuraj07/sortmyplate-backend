import json
from typing import List, Optional
from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.base import get_db
from app.db.models import UserDB
from app.repositories.group_repo import group_repo
from app.api.deps import get_current_user

router = APIRouter()

class GroupCreate(BaseModel):
    name: str

class GroupJoin(BaseModel):
    invite_code: str

class GroupMemberResponse(BaseModel):
    id: str
    full_name: str
    email: str
    picture_url: Optional[str] = None
    allergies: List[str] = []
    diet_preference: str

class GroupResponse(BaseModel):
    id: str
    name: str
    invite_code: str
    owner_id: str
    members: List[GroupMemberResponse] = []

@router.post("/create", response_model=GroupResponse, status_code=status.HTTP_201_CREATED)
async def create_group(
    body: GroupCreate,
    current_user: UserDB = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    group = await group_repo.create_group(session, owner_id=current_user.id, name=body.name)
    members_db = await group_repo.get_group_members(session, group.id)
    
    members = [
        GroupMemberResponse(
            id=m.id,
            full_name=m.full_name,
            email=m.email,
            picture_url=m.picture_url,
            allergies=json.loads(m.allergies) if m.allergies else [],
            diet_preference=m.diet_preference
        )
        for m in members_db
    ]

    return GroupResponse(
        id=group.id,
        name=group.name,
        invite_code=group.invite_code,
        owner_id=group.owner_id,
        members=members
    )

@router.post("/join", response_model=GroupResponse)
async def join_group(
    body: GroupJoin,
    current_user: UserDB = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    group = await group_repo.join_group(session, user_id=current_user.id, invite_code=body.invite_code)
    if not group:
        raise HTTPException(status_code=404, detail="Invalid invite code")
    
    members_db = await group_repo.get_group_members(session, group.id)
    members = [
        GroupMemberResponse(
            id=m.id,
            full_name=m.full_name,
            email=m.email,
            picture_url=m.picture_url,
            allergies=json.loads(m.allergies) if m.allergies else [],
            diet_preference=m.diet_preference
        )
        for m in members_db
    ]

    return GroupResponse(
        id=group.id,
        name=group.name,
        invite_code=group.invite_code,
        owner_id=group.owner_id,
        members=members
    )

@router.get("/my", response_model=List[GroupResponse])
async def get_my_groups(
    current_user: UserDB = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    groups_db = await group_repo.get_user_groups(session, current_user.id)
    out = []
    for g in groups_db:
        members_db = await group_repo.get_group_members(session, g.id)
        members = [
            GroupMemberResponse(
                id=m.id,
                full_name=m.full_name,
                email=m.email,
                picture_url=m.picture_url,
                allergies=json.loads(m.allergies) if m.allergies else [],
                diet_preference=m.diet_preference
            )
            for m in members_db
        ]
        out.append(GroupResponse(
            id=g.id,
            name=g.name,
            invite_code=g.invite_code,
            owner_id=g.owner_id,
            members=members
        ))
    return out

@router.get("/{group_id}/members", response_model=List[GroupMemberResponse])
async def get_group_members(
    group_id: str,
    current_user: UserDB = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    group = await group_repo.get_by_id(session, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    
    members_db = await group_repo.get_group_members(session, group_id)
    if not any(m.id == current_user.id for m in members_db):
        raise HTTPException(status_code=403, detail="Not a member of this group")
        
    return [
        GroupMemberResponse(
            id=m.id,
            full_name=m.full_name,
            email=m.email,
            picture_url=m.picture_url,
            allergies=json.loads(m.allergies) if m.allergies else [],
            diet_preference=m.diet_preference
        )
        for m in members_db
    ]
