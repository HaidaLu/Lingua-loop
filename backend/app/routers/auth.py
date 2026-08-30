from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlmodel import Session, select

from app.auth import create_token, get_current_user, hash_password, verify_password
from app.db import get_session
from app.models import User
from app.schemas import AuthStatus, LoginRequest, RegisterRequest, TokenResponse

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _user_count(session: Session) -> int:
    return session.exec(select(func.count()).select_from(User)).one()


@router.get("/status", response_model=AuthStatus)
def status(session: Session = Depends(get_session)):
    return AuthStatus(registered=_user_count(session) > 0)


@router.post("/register", response_model=TokenResponse)
def register(req: RegisterRequest, session: Session = Depends(get_session)):
    if _user_count(session) > 0:
        raise HTTPException(
            status_code=403, detail="An account already exists; registration is closed (single-user mode)"
        )
    user = User(email=req.email.lower(), password_hash=hash_password(req.password))
    session.add(user)
    session.commit()
    return TokenResponse(access_token=create_token(user.email), email=user.email)


@router.post("/login", response_model=TokenResponse)
def login(req: LoginRequest, session: Session = Depends(get_session)):
    user = session.exec(select(User).where(User.email == req.email.lower())).first()
    if user is None or not verify_password(req.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Wrong email or password")
    return TokenResponse(access_token=create_token(user.email), email=user.email)


@router.get("/me", response_model=TokenResponse)
def me(user: User = Depends(get_current_user)):
    # reuse TokenResponse; issue a fresh token (sliding renewal)
    return TokenResponse(access_token=create_token(user.email), email=user.email)
