from fastapi import APIRouter, Depends, HTTPException, status, Form, Request
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select
from database import get_session
from models import User
from dependencies import (
    verify_password, get_password_hash, create_access_token,
    get_current_active_user
)
from datetime import timedelta
import uuid

router = APIRouter()
templates = Jinja2Templates(directory="templates")


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@router.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})


@router.post("/login")
async def login(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    session: Session = Depends(get_session)
):
    user = session.exec(select(User).where(User.email == email)).first()
    if not user or not verify_password(password, user.hashed_password):
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "Invalid email or password"},
            status_code=status.HTTP_401_UNAUTHORIZED
        )
    
    if not user.is_active:
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "Account is disabled"},
            status_code=status.HTTP_403_FORBIDDEN
        )
    
    access_token_expires = timedelta(minutes=30 * 24 * 60)
    access_token = create_access_token(
        data={"sub": str(user.id)}, expires_delta=access_token_expires
    )
    
    response = RedirectResponse(url="/dashboard", status_code=status.HTTP_303_SEE_OTHER)
    response.set_cookie(
        key="access_token", 
        value=access_token, 
        httponly=True, 
        max_age=30*24*60*60,
        samesite="lax",
        secure=False  # Установите True для HTTPS
    )
    return response


@router.post("/register", response_class=HTMLResponse)
async def register(
    request: Request,
    email: str = Form(...),
    username: str = Form(...),
    password: str = Form(...),
    session: Session = Depends(get_session)
):
    try:
        # Проверяем длину пароля для отладки
        print(f"DEBUG: Password length: {len(password)}, bytes: {len(password.encode('utf-8'))}")
        
        # Check if user exists
        existing_user = session.exec(
            select(User).where((User.email == email) | (User.username == username))
        ).first()
        if existing_user:
            return templates.TemplateResponse(
                "register.html",
                {"request": request, "error": "Email or username already registered"},
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        # Хешируем пароль
        try:
            # Дополнительная проверка длины перед хешированием
            password_bytes = password.encode('utf-8')
            if len(password_bytes) > 72:
                # Обрезаем до 72 байт безопасно
                truncated = password_bytes[:72]
                # Удаляем неполные UTF-8 последовательности
                while truncated and (truncated[-1] & 0x80) and not (truncated[-1] & 0x40):
                    truncated = truncated[:-1]
                password = truncated.decode('utf-8', errors='ignore')
            
            hashed_password = get_password_hash(password)
        except Exception as hash_error:
            print(f"DEBUG: Hash error: {hash_error}")
            print(f"DEBUG: Password length: {len(password)}, bytes: {len(password.encode('utf-8'))}")
            # Последняя попытка - обрезать до 72 символов
            if len(password) > 72:
                password = password[:72]
                hashed_password = get_password_hash(password)
            else:
                raise hash_error
        
        # Create new user
        user = User(
            email=email,
            username=username,
            hashed_password=hashed_password,
            is_active=True,
            is_verified=False
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        
        # Auto login
        access_token_expires = timedelta(minutes=30 * 24 * 60)
        access_token = create_access_token(
            data={"sub": str(user.id)}, expires_delta=access_token_expires
        )
        
        response = RedirectResponse(url="/dashboard", status_code=status.HTTP_303_SEE_OTHER)
        response.set_cookie(key="access_token", value=access_token, httponly=True, max_age=30*24*60*60)
        return response
    except Exception as e:
        import traceback
        print(f"Registration error: {e}")
        print(traceback.format_exc())
        return templates.TemplateResponse(
            "register.html",
            {"request": request, "error": f"Registration failed: {str(e)}"},
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@router.get("/logout")
async def logout():
    response = RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    response.delete_cookie(key="access_token")
    return response

