from datetime import datetime, timedelta, timezone
from uuid import uuid4
from jose import jwt, JWTError, ExpiredSignatureError
from passlib.context import CryptContext
from app.core.config import settings

pwd_context = CryptContext(
    schemes = ["bcrypt"],
    deprecated = "auto"
)

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(data: dict) -> str:
    to_encode = data.copy()

    expire = (
        datetime.now(timezone.utc)
        + timedelta(
            minutes=settings.access_token_expire_minutes
        )
    )

    jti = str(uuid4())

    to_encode.update({
        "exp": expire,
        "jti": jti
    })

    return jwt.encode(
        to_encode,
        settings.secret_key,
        algorithm=settings.algorithm
    )

class TokenExpiredError(Exception):
    pass

def decode_access_token(token: str) -> dict | None:
    """Retourne le payload, lève TokenExpiredError si expiré, None si invalide."""
    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.algorithm]
        )
        return payload
    except ExpiredSignatureError:
        raise TokenExpiredError("Token expiré")
    except JWTError:
        return None