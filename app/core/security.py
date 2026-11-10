import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Union
import bcrypt
from jose import jwt
from app.core.config import settings

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))

def get_password_hash(password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")

def create_access_token(subject: Union[str, Any], expires_delta: timedelta = None) -> str:
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode = {"exp": expire, "sub": str(subject)}
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

def decode_access_token(token: str) -> dict:
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])

def generate_subject_token() -> str:
    """
    Generates a synthetic, decoupled medical subject token.
    Health records are stored against this token, isolating them from PII.
    """
    return f"sub_{uuid.uuid4()}"

def resolve_public_base_url(request) -> str:
    """
    Resolves the external HTTPS base URL safely behind reverse proxies (e.g. RamNaym Cloud).
    """
    forwarded_host = request.headers.get("x-forwarded-host")
    forwarded_proto = (request.headers.get("x-forwarded-proto") or "").lower()
    if forwarded_host:
        host = forwarded_host.split(",")[0].strip()
        scheme = "https" if ("https" in forwarded_proto or "ramnaymcloud.com" in host) else request.url.scheme
        return f"{scheme}://{host}".rstrip("/")

    base_url = str(request.base_url).rstrip("/")
    if ("https" in forwarded_proto or "ramnaymcloud.com" in base_url) and base_url.startswith("http://"):
        base_url = base_url.replace("http://", "https://", 1)
    return base_url
