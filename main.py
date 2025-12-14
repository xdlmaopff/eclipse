from fastapi import FastAPI, Request, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from contextlib import asynccontextmanager
from database import init_db, get_session
from models import User
from dependencies import get_current_active_user
from routers import auth, dashboard, subscriptions, admin, profile
import traceback
import os
import json

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield

app = FastAPI(lifespan=lifespan, title="HellNet Pro")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")
templates.env.filters['load_json'] = lambda x: json.loads(x)

app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(dashboard.router, tags=["dashboard"])
app.include_router(subscriptions.router, tags=["subscriptions"])
app.include_router(admin.router, tags=["admin"])
app.include_router(profile.router, tags=["profile"])


# Middleware для проверки токена из cookie
@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    public_paths = ["/", "/health", "/login", "/register", "/auth/login", "/auth/register", "/auth/logout"]
    if request.url.path.startswith("/static") or request.url.path in public_paths:
        response = await call_next(request)
        return response
    
    token = request.cookies.get("access_token")
    if token:
        request.state.token = token
        try:
            from dependencies import SECRET_KEY, ALGORITHM
            from jose import jwt
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            request.state.user_id = payload.get("sub")
        except:
            pass
    
    response = await call_next(request)
    return response


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/login", response_class=HTMLResponse)
async def login_redirect(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@app.get("/register", response_class=HTMLResponse)
async def register_redirect(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Глобальный обработчик ошибок для отладки"""
    import traceback
    error_trace = traceback.format_exc()
    print(f"Error on {request.url.path}:")
    print(error_trace)
    return JSONResponse(
        status_code=500,
        content={
            "error": str(exc),
            "detail": error_trace,
            "path": str(request.url.path)
        }
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

