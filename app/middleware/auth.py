from datetime import datetime, timezone
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import settings

_bearer = HTTPBearer()
_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain: str, stored: str) -> bool:
    """
    Accept either a bcrypt hash (starts with $2b$) or a plain-text password.
    Plain-text is convenient for local dev; always use a bcrypt hash in production.
    """
    if stored.startswith("$2b$") or stored.startswith("$2a$"):
        return _pwd_context.verify(plain, stored)
    return plain == stored


def create_access_token(sub: str = "admin") -> tuple[str, datetime]:
    """Return (encoded_jwt, expiry_datetime)."""
    from datetime import timedelta

    expiry = datetime.now(timezone.utc) + timedelta(days=settings.jwt_expire_days)
    token = jwt.encode(
        {"sub": sub, "exp": expiry},
        settings.jwt_secret,
        algorithm="HS256",
    )
    return token, expiry


def require_auth(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(_bearer)],
) -> str:
    """FastAPI dependency — verifies the Bearer JWT and returns the subject claim."""
    exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.jwt_secret,
            algorithms=["HS256"],
        )
        sub: str | None = payload.get("sub")
        if sub is None:
            raise exc
        return sub
    except JWTError:
        raise exc
