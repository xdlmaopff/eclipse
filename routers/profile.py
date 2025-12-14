from fastapi import APIRouter, Depends, HTTPException, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select
from database import get_session
from models import User, SubscriptionRequest, SubscriptionPlan
from dependencies import get_current_active_user, get_password_hash, verify_password
from datetime import datetime
import uuid

router = APIRouter()
templates = Jinja2Templates(directory="templates")


@router.get("/profile", response_class=HTMLResponse)
async def profile(
    request: Request,
    current_user: User = Depends(get_current_active_user),
    session: Session = Depends(get_session)
):
    subscription_requests = session.exec(
        select(SubscriptionRequest).where(SubscriptionRequest.user_id == current_user.id)
        .order_by(SubscriptionRequest.created_at.desc())
    ).all()

    current_plan = session.exec(
        select(SubscriptionPlan).where(SubscriptionPlan.tier == current_user.subscription_tier)
    ).first()

    return templates.TemplateResponse("profile.html", {
        "request": request,
        "user": current_user,
        "subscription_requests": subscription_requests,
        "current_plan": current_plan
    })


@router.get("/profile/edit", response_class=HTMLResponse)
async def edit_profile(
    request: Request,
    current_user: User = Depends(get_current_active_user)
):
    return templates.TemplateResponse("profile_edit.html", {
        "request": request,
        "user": current_user
    })


@router.post("/api/profile/update")
async def update_profile(
    request: Request,
    email: str = Form(None),
    password: str = Form(None),
    current_user: User = Depends(get_current_active_user),
    session: Session = Depends(get_session)
):
    if email and email != current_user.email:
        existing = session.exec(select(User).where(User.email == email)).first()
        if existing:
            return JSONResponse(status_code=400, content={"error": "Email already in use"})
        current_user.email = email
    
    if password:
        if len(password) < 6:
            return JSONResponse(status_code=400, content={"error": "Password must be at least 6 characters"})
        current_user.hashed_password = get_password_hash(password)
    
    session.add(current_user)
    session.commit()
    
    return JSONResponse(content={"success": True, "message": "Profile updated"})


@router.get("/subscription-history", response_class=HTMLResponse)
async def subscription_history(
    request: Request,
    current_user: User = Depends(get_current_active_user),
    session: Session = Depends(get_session)
):
    subscription_requests = session.exec(
        select(SubscriptionRequest).where(SubscriptionRequest.user_id == current_user.id)
        .order_by(SubscriptionRequest.created_at.desc())
    ).all()

    current_plan = session.exec(
        select(SubscriptionPlan).where(SubscriptionPlan.tier == current_user.subscription_tier)
    ).first()

    return templates.TemplateResponse("subscription_history.html", {
        "request": request,
        "user": current_user,
        "requests": subscription_requests,
        "current_plan": current_plan
    })

