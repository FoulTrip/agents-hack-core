# core/auth.py
import jwt
from datetime import datetime, timedelta, timezone
from passlib.context import CryptContext
from typing import Optional, Any
from core.config import settings

# Contexto para hashing de contraseñas
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

SECRET_KEY = settings.JWT_SECRET
ALGORITHM = settings.JWT_ALGORITHM
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7 # 1 semana

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Crea un nuevo token JWT para sesión."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifica si la contraseña plana coincide con el hash."""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """Genera hash de contraseña con bcrypt."""
    return pwd_context.hash(password)

def decode_access_token(token: str) -> Optional[dict]:
    """Decodifica un token JWT o retorna None si es inválido."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except Exception:
        return None
