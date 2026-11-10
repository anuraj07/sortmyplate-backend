import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, Text, Integer, ForeignKey
from app.db.base import Base

class UserDB(Base):
    __tablename__ = "users"

    id = Column(String(64), primary_key=True, index=True, default=lambda: f"usr_{uuid.uuid4().hex[:8]}")
    email = Column(String(255), unique=True, index=True, nullable=False)
    full_name = Column(String(255), nullable=False)
    google_sub = Column(String(255), unique=True, index=True, nullable=True)
    picture_url = Column(String(512), nullable=True)
    subject_token = Column(String(64), unique=True, index=True, nullable=False)
    diet_preference = Column(String(64), default="omnivore")
    allergies = Column(Text, default="[]") # JSON serialized list of allergens
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

class GroupDB(Base):
    __tablename__ = "groups"

    id = Column(String(64), primary_key=True, index=True, default=lambda: f"grp_{uuid.uuid4().hex[:8]}")
    name = Column(String(255), nullable=False)
    invite_code = Column(String(16), unique=True, index=True, nullable=False)
    owner_id = Column(String(64), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

class GroupMemberDB(Base):
    __tablename__ = "group_members"

    id = Column(Integer, primary_key=True, autoincrement=True)
    group_id = Column(String(64), ForeignKey("groups.id"), index=True, nullable=False)
    user_id = Column(String(64), ForeignKey("users.id"), index=True, nullable=False)
    joined_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

class BiomarkerPanelDB(Base):
    """
    Zone B (Encrypted PHI Vault).
    Biomarker findings are tied strictly to the synthetic `subject_token`,
    and the actual clinical observations are stored as an AES-256-GCM encrypted payload.
    """
    __tablename__ = "biomarker_panels"

    id = Column(String(64), primary_key=True, index=True, default=lambda: f"panel_{uuid.uuid4().hex[:10]}")
    subject_token = Column(String(64), index=True, nullable=False)
    lab_provider = Column(String(255), default="Standard Diagnostics")
    report_date = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    encrypted_payload = Column(Text, nullable=False) # AES-256-GCM ciphertext (base64)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
