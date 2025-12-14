from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlmodel import Session, select
from database import get_session
from models import User, UserRole
from jose import JWTError, jwt
from typing import Optional
from fastapi import Request
import os
import uuid
import bcrypt
from datetime import datetime, timedelta

SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30 * 24 * 60  # 30 days

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Проверка пароля с использованием bcrypt напрямую"""
    # Обрезаем пароль до 72 байт если нужно
    password_bytes = plain_password.encode('utf-8')
    if len(password_bytes) > 72:
        password_bytes = password_bytes[:72]
    
    # Проверяем пароль
    try:
        return bcrypt.checkpw(password_bytes, hashed_password.encode('utf-8'))
    except Exception:
        return False


def get_password_hash(password: str) -> str:
    """Хеширование пароля с использованием bcrypt напрямую"""
    # Убеждаемся, что пароль - это строка
    if not isinstance(password, str):
        password = str(password)
    
    # Убираем лишние пробелы
    password = password.strip()
    
    # Обрезаем пароль до 72 байт (ограничение bcrypt)
    password_bytes = password.encode('utf-8')
    if len(password_bytes) > 72:
        # Обрезаем до 72 байт, удаляя неполные UTF-8 последовательности
        truncated_bytes = password_bytes[:72]
        # Удаляем неполные UTF-8 последовательности в конце
        while truncated_bytes and (truncated_bytes[-1] & 0x80) and not (truncated_bytes[-1] & 0x40):
            truncated_bytes = truncated_bytes[:-1]
        password_bytes = truncated_bytes
    
    # Хешируем пароль используя bcrypt напрямую
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode('utf-8')


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


async def get_current_user(
    request: Request,
    session: Session = Depends(get_session)
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    # Получаем токен из cookie (установлен в middleware)
    token = None
    if hasattr(request.state, "token"):
        token = request.state.token
    elif "access_token" in request.cookies:
        token = request.cookies.get("access_token")
    
    if not token:
        print(f"DEBUG: No token found. Cookies: {list(request.cookies.keys())}, State: {hasattr(request.state, 'token')}")
        raise credentials_exception
    
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    try:
        user_uuid = uuid.UUID(user_id)
    except (ValueError, TypeError):
        raise credentials_exception
    
    user = session.get(User, user_uuid)
    if user is None:
        raise credentials_exception
    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user


async def get_current_admin_user(
    current_user: User = Depends(get_current_active_user)
) -> User:
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    return current_user


def get_user_limits(tier: str):
    limits = {
        "free": {"max_accounts": 5, "max_actions_per_day": 100},
        "pro": {"max_accounts": None, "max_actions_per_day": 5000},
        "elite": {"max_accounts": None, "max_actions_per_day": None}
    }
    return limits.get(tier, limits["free"])


async def check_subscription_limits(
    current_user: User = Depends(get_current_active_user),
    session: Session = Depends(get_session)
):
    # Лимиты отключены - все могут добавлять неограниченное количество сессий
    return current_user

