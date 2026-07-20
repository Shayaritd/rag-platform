"""JWT issuing/verification and password hashing."""
import datetime as dt
from jose import jwt, JWTError
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from app.core.config import get_settings

settings = get_settings()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_PREFIX}/auth/login")


import hashlib
import base64

def hash_password(password: str) -> str:
    # Pre-hash with SHA-256 to handle arbitrary password lengths securely and prevent bcrypt ValueError
    pre_hashed = base64.b64encode(hashlib.sha256(password.encode("utf-8")).digest()).decode("utf-8")
    return pwd_context.hash(pre_hashed)


def verify_password(plain: str, hashed: str) -> bool:
    pre_hashed = base64.b64encode(hashlib.sha256(plain.encode("utf-8")).digest()).decode("utf-8")
    return pwd_context.verify(pre_hashed, hashed)


def _create_token(subject: str, expires_delta: dt.timedelta, token_type: str, **claims) -> str:
    now = dt.datetime.utcnow()
    payload = {"sub": subject, "type": token_type, "iat": now, "exp": now + expires_delta, **claims}
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def create_access_token(user_id: str, tenant_id: str, role: str) -> str:
    return _create_token(
        user_id,
        dt.timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        "access",
        tenant_id=tenant_id,
        role=role,
    )


def create_refresh_token(user_id: str) -> str:
    return _create_token(user_id, dt.timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS), "refresh")


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")


class CurrentUser:
    """Resolved from the access token; attached to request state by the auth dependency."""
    def __init__(self, user_id: str, tenant_id: str, role: str):
        self.user_id = user_id
        self.tenant_id = tenant_id
        self.role = role


def get_current_user(token: str = Depends(oauth2_scheme)) -> CurrentUser:
    payload = decode_token(token)
    if payload.get("type") != "access":
        raise HTTPException(status_code=401, detail="Expected access token")
    return CurrentUser(user_id=payload["sub"], tenant_id=payload["tenant_id"], role=payload["role"])


def require_role(*allowed_roles: str):
    def _check(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if user.role not in allowed_roles:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return user
    return _check
