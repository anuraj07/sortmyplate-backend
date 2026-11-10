import json
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.models import UserDB
from app.core.security import generate_subject_token

class UserRepository:
    async def get_by_id(self, session: AsyncSession, user_id: str) -> Optional[UserDB]:
        stmt = select(UserDB).where(UserDB.id == user_id)
        result = await session.execute(stmt)
        return result.scalars().first()

    async def get_by_email(self, session: AsyncSession, email: str) -> Optional[UserDB]:
        stmt = select(UserDB).where(UserDB.email == email.lower().strip())
        result = await session.execute(stmt)
        return result.scalars().first()

    async def get_by_google_sub(self, session: AsyncSession, google_sub: str) -> Optional[UserDB]:
        stmt = select(UserDB).where(UserDB.google_sub == google_sub)
        result = await session.execute(stmt)
        return result.scalars().first()

    async def create_or_update_google_user(
        self,
        session: AsyncSession,
        email: str,
        full_name: str,
        google_sub: str,
        picture_url: Optional[str] = None,
        allergies: Optional[List[str]] = None,
        diet_preference: Optional[str] = None
    ) -> UserDB:
        user = await self.get_by_google_sub(session, google_sub)
        if not user:
            user = await self.get_by_email(session, email)

        allergies_json = json.dumps([a.lower().strip() for a in (allergies or [])])

        if user:
            user.full_name = full_name
            user.google_sub = google_sub
            if picture_url:
                user.picture_url = picture_url
            if allergies is not None:
                user.allergies = allergies_json
            if diet_preference is not None:
                user.diet_preference = diet_preference
        else:
            user = UserDB(
                email=email.lower().strip(),
                full_name=full_name,
                google_sub=google_sub,
                picture_url=picture_url,
                subject_token=generate_subject_token(),
                diet_preference=diet_preference or "omnivore",
                allergies=allergies_json
            )
            session.add(user)

        await session.commit()
        await session.refresh(user)
        return user

user_repo = UserRepository()
