import uuid
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from app.db.models import GroupDB, GroupMemberDB, UserDB

class GroupRepository:
    async def create_group(self, session: AsyncSession, owner_id: str, name: str) -> GroupDB:
        invite_code = uuid.uuid4().hex[:6].upper()
        group = GroupDB(
            name=name,
            invite_code=invite_code,
            owner_id=owner_id
        )
        session.add(group)
        await session.flush()

        member = GroupMemberDB(group_id=group.id, user_id=owner_id)
        session.add(member)

        await session.commit()
        await session.refresh(group)
        return group

    async def get_by_id(self, session: AsyncSession, group_id: str) -> Optional[GroupDB]:
        stmt = select(GroupDB).where(GroupDB.id == group_id)
        result = await session.execute(stmt)
        return result.scalars().first()

    async def get_by_invite_code(self, session: AsyncSession, invite_code: str) -> Optional[GroupDB]:
        stmt = select(GroupDB).where(GroupDB.invite_code == invite_code.strip().upper())
        result = await session.execute(stmt)
        return result.scalars().first()

    async def join_group(self, session: AsyncSession, user_id: str, invite_code: str) -> Optional[GroupDB]:
        group = await self.get_by_invite_code(session, invite_code)
        if not group:
            return None

        # Check if already joined
        stmt = select(GroupMemberDB).where(
            GroupMemberDB.group_id == group.id,
            GroupMemberDB.user_id == user_id
        )
        existing = (await session.execute(stmt)).scalars().first()
        if not existing:
            member = GroupMemberDB(group_id=group.id, user_id=user_id)
            session.add(member)
            await session.commit()

        return group

    async def leave_group(self, session: AsyncSession, user_id: str, group_id: str) -> bool:
        stmt = delete(GroupMemberDB).where(
            GroupMemberDB.group_id == group_id,
            GroupMemberDB.user_id == user_id
        )
        result = await session.execute(stmt)
        await session.commit()
        return result.rowcount > 0

    async def get_group_members(self, session: AsyncSession, group_id: str) -> List[UserDB]:
        stmt = (
            select(UserDB)
            .join(GroupMemberDB, GroupMemberDB.user_id == UserDB.id)
            .where(GroupMemberDB.group_id == group_id)
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def get_user_groups(self, session: AsyncSession, user_id: str) -> List[GroupDB]:
        stmt = (
            select(GroupDB)
            .join(GroupMemberDB, GroupMemberDB.group_id == GroupDB.id)
            .where(GroupMemberDB.user_id == user_id)
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())

group_repo = GroupRepository()
