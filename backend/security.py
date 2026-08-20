"""Хеширование паролей и выдача/разбор JWT."""

from datetime import datetime, timedelta, timezone

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError, InvalidHashError

from config import get_settings

_hasher = PasswordHasher()
_settings = get_settings()
ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def create_token(user_id: int) -> tuple[str, int]:
    """Возвращает подписанный токен и его срок жизни в секундах."""
    ttl = timedelta(hours=_settings.jwt_ttl_hours)
    now = datetime.now(timezone.utc)
    payload = {"sub": str(user_id), "iat": now, "exp": now + ttl}
    token = jwt.encode(payload, _settings.resolved_jwt_secret(), algorithm=ALGORITHM)
    return token, int(ttl.total_seconds())


def decode_token(token: str) -> int | None:
    """Достаёт id пользователя из токена; None, если токен негоден."""
    try:
        payload = jwt.decode(
            token, _settings.resolved_jwt_secret(), algorithms=[ALGORITHM]
        )
        return int(payload["sub"])
    except (jwt.InvalidTokenError, KeyError, ValueError):
        return None
