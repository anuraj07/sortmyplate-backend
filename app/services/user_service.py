import uuid
from typing import Dict, List, Optional
from app.domain.users import UserCreate, UserInDB, GroupInDB
from app.core.security import get_password_hash, generate_subject_token

class UserService:
    def __init__(self):
        self.reset()

    def reset(self):
        self._users_by_id: Dict[str, UserInDB] = {}
        self._users_by_email: Dict[str, UserInDB] = {}
        self._groups_by_id: Dict[str, GroupInDB] = {}
        self._groups_by_code: Dict[str, GroupInDB] = {}

    def create_user(self, user_in: UserCreate) -> UserInDB:
        if user_in.email.lower() in self._users_by_email:
            raise ValueError("Email already registered")
        
        user_id = f"usr_{uuid.uuid4().hex[:8]}"
        subject_token = generate_subject_token()
        hashed_password = get_password_hash(user_in.password)
        
        user_db = UserInDB(
            id=user_id,
            email=user_in.email.lower(),
            full_name=user_in.full_name,
            hashed_password=hashed_password,
            diet_preference=user_in.diet_preference,
            allergies=[a.lower().strip() for a in user_in.allergies],
            subject_token=subject_token
        )
        
        self._users_by_id[user_id] = user_db
        self._users_by_email[user_db.email] = user_db
        return user_db

    def get_by_email(self, email: str) -> Optional[UserInDB]:
        return self._users_by_email.get(email.lower())

    def get_by_id(self, user_id: str) -> Optional[UserInDB]:
        return self._users_by_id.get(user_id)

    def create_group(self, owner_id: str, name: str) -> GroupInDB:
        group = GroupInDB(
            name=name,
            owner_id=owner_id,
            member_ids=[owner_id]
        )
        self._groups_by_id[group.id] = group
        self._groups_by_code[group.invite_code] = group
        return group

    def join_group(self, user_id: str, invite_code: str) -> Optional[GroupInDB]:
        group = self._groups_by_code.get(invite_code.strip().upper())
        if not group:
            return None
        if user_id not in group.member_ids:
            group.member_ids.append(user_id)
        return group

    def leave_group(self, user_id: str, group_id: str) -> bool:
        group = self._groups_by_id.get(group_id)
        if not group or user_id not in group.member_ids:
            return False
        group.member_ids.remove(user_id)
        return True

    def get_group(self, group_id: str) -> Optional[GroupInDB]:
        return self._groups_by_id.get(group_id)

    def get_group_members(self, group_id: str) -> List[UserInDB]:
        group = self.get_group(group_id)
        if not group:
            return []
        return [self._users_by_id[m_id] for m_id in group.member_ids if m_id in self._users_by_id]

user_service = UserService()
