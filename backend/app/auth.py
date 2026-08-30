from __future__ import annotations

from datetime import timedelta

import bcrypt
import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlmodel import Session, select

from app.config import settings
from app.db import get_session
from app.models import User
from app.time_utils import utcnow

_ALGO = "HS256"
_bearer = HTTPBearer(auto_error=False)


def hash_password(pw: str) -> str:
    return bcrypt.hashpw(pw.encode()[:72], bcrypt.gensalt()).decode()


def verify_password(pw: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(pw.encode()[:72], hashed.encode())
    except ValueError:
        return False


def create_token(email: str) -> str:
    payload = {
        "sub": email,
        "iat": utcnow(),
        "exp": utcnow() + timedelta(hours=settings.auth_token_ttl_hours),
    }
    return jwt.encode(payload, settings.auth_secret, algorithm=_ALGO)


def _decode(token: str) -> str | None:
    try:
        return jwt.decode(token, settings.auth_secret, algorithms=[_ALGO]).get("sub")
    except jwt.PyJWTError:
        return None


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    session: Session = Depends(get_session),
) -> User:
    if creds is None:
        raise HTTPException(status_code=401, detail="Not signed in")
    email = _decode(creds.credentials)
    if email is None:
        raise HTTPException(status_code=401, detail="Session expired, please sign in again")
    user = session.exec(select(User).where(User.email == email)).first()
    if user is None:
        raise HTTPException(status_code=401, detail="Account not found")
    return user
