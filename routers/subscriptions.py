from fastapi import APIRouter, Depends, HTTPException, Form, Request
from fastapi.responses import JSONResponse, HTMLResponse
from starlette.templating import Jinja2Templates
from sqlmodel import Session, select
from database import get_session
from models import User, SubscriptionRequest, SubscriptionTier, SubscriptionRequestStatus, SubscriptionPlan
from dependencies import get_current_active_user
from datetime import datetime
import uuid

router = APIRouter()

templates = Jinja2Templates(directory="./templates")


@router.post("/api/request-subscription")
async def request_subscription(
    request: Request,
    tier: str = Form(...),
    message: str = Form(...),
    current_user: User = Depends(get_current_active_user),
    session: Session = Depends(get_session)
):
    """Создать запрос на подписку"""
    try:
        requested_tier = SubscriptionTier(tier)
    except ValueError:
        return JSONResponse(
            status_code=400,
            content={"error": "Invalid subscription tier"}
        )
    
    # Проверяем, что тариф существует
    plan = session.exec(
        select(SubscriptionPlan).where(SubscriptionPlan.tier == requested_tier)
    ).first()
    
    if not plan:
        return JSONResponse(
            status_code=404,
            content={"error": "Subscription plan not found"}
        )
    
    # Проверяем, нет ли уже активного запроса
    existing_request = session.exec(
        select(SubscriptionRequest).where(
            SubscriptionRequest.user_id == current_user.id,
            SubscriptionRequest.status == SubscriptionRequestStatus.PENDING
        )
    ).first()
    
    if existing_request:
        return JSONResponse(
            status_code=400,
            content={"error": "You already have a pending subscription request"}
        )
    
    # Создаем запрос
    subscription_request = SubscriptionRequest(
        user_id=current_user.id,
        requested_tier=requested_tier,
        message=message,
        status=SubscriptionRequestStatus.PENDING
    )
    
    session.add(subscription_request)
    session.commit()
    
    return JSONResponse(content={
        "success": True,
        "message": "Subscription request submitted successfully. The owner will review it soon."
    })


@router.get("/api/my-subscription-requests")
async def get_my_requests(
    current_user: User = Depends(get_current_active_user),
    session: Session = Depends(get_session)
):
    """Получить все запросы пользователя"""
    requests = session.exec(
        select(SubscriptionRequest)
        .where(SubscriptionRequest.user_id == current_user.id)
        .order_by(SubscriptionRequest.created_at.desc())
    ).all()
    
    return JSONResponse(content={
        "requests": [
            {
                "id": str(req.id),
                "tier": req.requested_tier,
                "message": req.message,
                "status": req.status,
                "created_at": req.created_at.isoformat(),
                "reviewed_at": req.reviewed_at.isoformat() if req.reviewed_at else None,
                "admin_notes": req.admin_notes
            }
            for req in requests
        ]
    })


@router.get("/subscriptions/request", response_class=HTMLResponse)
async def subscription_request_page(
    request: Request,
    current_user: User = Depends(get_current_active_user),
    session: Session = Depends(get_session)
):
    plans = session.exec(select(SubscriptionPlan).where(SubscriptionPlan.is_active == True)).all()

    current_plan = session.exec(
        select(SubscriptionPlan).where(SubscriptionPlan.tier == current_user.subscription_tier)
    ).first()

    return templates.TemplateResponse("subscription_request.html", {
        "request": request,
        "user": current_user,
        "current_plan": current_plan,
        "plans": plans
    })

