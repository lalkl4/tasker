"""Регистрация, вход и сведения о себе."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from config import get_settings
from database import get_db
from deps import current_user
from models import User
from schemas import LoginIn, RegisterIn, TokenOut, UserOut
from security import create_token, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


def _token_response(user: User) -> TokenOut:
    token, ttl = create_token(user.id)
    return TokenOut(
        access_token=token, expires_in=ttl, user=UserOut.model_validate(user)
    )


@router.post("/register", response_model=TokenOut, status_code=201)
def register(payload: RegisterIn, db: Session = Depends(get_db)):
    if not get_settings().allow_registration:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Регистрация на этом сервере закрыта")

    email = payload.email.lower()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(status.HTTP_409_CONFLICT, "Такой email уже зарегистрирован")

    user = User(
        email=email,
        password_hash=hash_password(payload.password),
        display_name=payload.display_name or email.split("@")[0],
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return _token_response(user)


@router.post("/login", response_model=TokenOut)
def login(payload: LoginIn, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == payload.email.lower()))
    # Один и тот же ответ на неверный email и неверный пароль — чтобы нельзя было
    # перебором выяснить, кто зарегистрирован на сервере
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Неверный email или пароль")
    return _token_response(user)


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(current_user)):
    return user
