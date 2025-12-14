from fastapi import APIRouter, Depends, HTTPException, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select, func
from database import get_session
from models import User, SessionFile, Task, SubscriptionPlan, SubscriptionRequest, SubscriptionRequestStatus, SubscriptionTier
from dependencies import get_current_admin_user
from typing import List
from datetime import datetime, timedelta
import uuid

router = APIRouter()
templates = Jinja2Templates(directory="templates")


@router.get("/admin", response_class=HTMLResponse)
async def admin_dashboard(
    request: Request,
    current_user: User = Depends(get_current_admin_user),
    session: Session = Depends(get_session)
):
    # Get all users
    users = session.exec(select(User)).all()

    # Get all sessions
    all_sessions = session.exec(select(SessionFile)).all()

    # Get all tasks
    all_tasks = session.exec(select(Task)).all()

    # Get plans
    plans = session.exec(select(SubscriptionPlan)).all()

    # Get current plan
    current_plan = session.exec(
        select(SubscriptionPlan).where(SubscriptionPlan.tier == current_user.subscription_tier)
    ).first()

    # Get pending subscription requests with user info
    pending_requests_raw = session.exec(
        select(SubscriptionRequest)
        .where(SubscriptionRequest.status == SubscriptionRequestStatus.PENDING)
        .order_by(SubscriptionRequest.created_at.desc())
    ).all()

    # Enrich with user data
    pending_requests = []
    for req in pending_requests_raw:
        user = session.get(User, req.user_id)
        req.user = user  # Add user object to request
        pending_requests.append(req)

    # Calculate global stats
    total_users = len(users)
    total_sessions = len(all_sessions)
    total_tasks = len(all_tasks)
    total_reports = sum(task.total_reports for task in all_tasks)

    return templates.TemplateResponse(
        "admin.html",
        {
            "request": request,
            "current_plan": current_plan,
            "users": users,
            "sessions": all_sessions,
            "tasks": all_tasks,
            "plans": plans,
            "pending_requests": pending_requests,
            "stats": {
                "total_users": total_users,
                "total_sessions": total_sessions,
                "total_tasks": total_tasks,
                "total_reports": total_reports
            }
        }
    )


@router.post("/api/admin/ban-user/{user_id}")
async def ban_user(
    user_id: str,
    current_user: User = Depends(get_current_admin_user),
    session: Session = Depends(get_session)
):
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    user.is_active = False
    session.commit()
    return JSONResponse(content={"success": True})


@router.post("/api/admin/unban-user/{user_id}")
async def unban_user(
    user_id: str,
    current_user: User = Depends(get_current_admin_user),
    session: Session = Depends(get_session)
):
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    user.is_active = True
    session.commit()
    return JSONResponse(content={"success": True})


@router.post("/api/admin/update-plan-price")
async def update_plan_price(
    request: Request,
    current_user: User = Depends(get_current_admin_user),
    session: Session = Depends(get_session)
):
    data = await request.json()
    plan_tier = data.get("plan_tier")
    new_price = data.get("new_price")

    if not plan_tier or new_price is None:
        raise HTTPException(status_code=400, detail="Missing plan_tier or new_price")

    plan = session.exec(
        select(SubscriptionPlan).where(SubscriptionPlan.tier == plan_tier)
    ).first()

    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    plan.price_monthly = float(new_price)
    session.commit()
    return JSONResponse(content={"success": True})


@router.post("/api/admin/update-plan-name")
async def update_plan_name(
    request: Request,
    current_user: User = Depends(get_current_admin_user),
    session: Session = Depends(get_session)
):
    data = await request.json()
    plan_tier = data.get("plan_tier")
    new_name = data.get("new_name")

    if not plan_tier or not new_name:
        raise HTTPException(status_code=400, detail="Missing plan_tier or new_name")

    plan = session.exec(
        select(SubscriptionPlan).where(SubscriptionPlan.tier == plan_tier)
    ).first()

    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    plan.name = new_name
    session.commit()
    return JSONResponse(content={"success": True})


@router.post("/api/admin/change-subscription")
async def change_subscription(
    request: Request,
    current_user: User = Depends(get_current_admin_user),
    session: Session = Depends(get_session)
):
    data = await request.json()
    user_id = data.get("user_id")
    subscription_tier = data.get("subscription_tier")

    if not user_id or not subscription_tier:
        raise HTTPException(status_code=400, detail="Missing user_id or subscription_tier")

    user = session.get(User, uuid.UUID(user_id))
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    try:
        user.subscription_tier = SubscriptionTier(subscription_tier)
        session.commit()
        return JSONResponse(content={"success": True})
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid subscription tier")


@router.get("/api/admin/subscription-requests")
async def get_subscription_requests(
    current_user: User = Depends(get_current_admin_user),
    session: Session = Depends(get_session)
):
    """Получить все запросы на подписку"""
    requests = session.exec(
        select(SubscriptionRequest)
        .order_by(SubscriptionRequest.created_at.desc())
    ).all()
    
    return JSONResponse(content={
        "requests": [
            {
                "id": str(req.id),
                "user_id": str(req.user_id),
                "username": session.get(User, req.user_id).username if session.get(User, req.user_id) else "Unknown",
                "email": session.get(User, req.user_id).email if session.get(User, req.user_id) else "Unknown",
                "requested_tier": req.requested_tier,
                "message": req.message,
                "status": req.status,
                "created_at": req.created_at.isoformat(),
                "reviewed_at": req.reviewed_at.isoformat() if req.reviewed_at else None,
                "admin_notes": req.admin_notes
            }
            for req in requests
        ]
    })


@router.post("/api/admin/approve-subscription-request/{request_id}")
async def approve_subscription_request(
    request_id: str,
    admin_notes: str = Form(None),
    current_user: User = Depends(get_current_admin_user),
    session: Session = Depends(get_session)
):
    """Одобрить запрос на подписку"""
    subscription_request = session.get(SubscriptionRequest, uuid.UUID(request_id))
    if not subscription_request:
        raise HTTPException(status_code=404, detail="Request not found")
    
    if subscription_request.status != SubscriptionRequestStatus.PENDING:
        raise HTTPException(status_code=400, detail="Request is not pending")
    
    # Обновляем подписку пользователя
    user = session.get(User, subscription_request.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    user.subscription_tier = subscription_request.requested_tier
    # Устанавливаем срок подписки на 1 месяц от текущей даты
    now = datetime.utcnow()
    if now.month == 12:
        user.subscription_expires_at = datetime(now.year + 1, 1, min(now.day, 28))
    else:
        # Проверяем, что день существует в следующем месяце
        next_month = now.month + 1
        try:
            user.subscription_expires_at = datetime(now.year, next_month, now.day)
        except ValueError:
            # Если дня нет (например, 31 февраля), используем последний день месяца
            from calendar import monthrange
            last_day = monthrange(now.year, next_month)[1]
            user.subscription_expires_at = datetime(now.year, next_month, last_day)
    
    # Обновляем запрос
    subscription_request.status = SubscriptionRequestStatus.APPROVED
    subscription_request.reviewed_by = current_user.id
    subscription_request.reviewed_at = datetime.utcnow()
    if admin_notes:
        subscription_request.admin_notes = admin_notes
    
    session.commit()
    
    return JSONResponse(content={"success": True, "message": "Subscription approved"})


@router.post("/api/admin/reject-subscription-request/{request_id}")
async def reject_subscription_request(
    request_id: str,
    admin_notes: str = Form(None),
    current_user: User = Depends(get_current_admin_user),
    session: Session = Depends(get_session)
):
    """Отклонить запрос на подписку"""
    subscription_request = session.get(SubscriptionRequest, uuid.UUID(request_id))
    if not subscription_request:
        raise HTTPException(status_code=404, detail="Request not found")
    
    if subscription_request.status != SubscriptionRequestStatus.PENDING:
        raise HTTPException(status_code=400, detail="Request is not pending")
    
    # Обновляем запрос
    subscription_request.status = SubscriptionRequestStatus.REJECTED
    subscription_request.reviewed_by = current_user.id
    subscription_request.reviewed_at = datetime.utcnow()
    if admin_notes:
        subscription_request.admin_notes = admin_notes
    
    session.commit()
    
    return JSONResponse(content={"success": True, "message": "Subscription request rejected"})


@router.post("/api/admin/reset-statistics")
async def reset_statistics(
    current_user: User = Depends(get_current_admin_user),
    session: Session = Depends(get_session)
):
    """Сбросить всю статистику (удалить все задачи)"""
    try:
        # Получаем количество задач до удаления
        all_tasks = session.exec(select(Task)).all()
        deleted_count = len(all_tasks)
        
        # Удаляем все задачи
        for task in all_tasks:
            session.delete(task)
        
        # Также удаляем связанные данные парсинга
        from models import ParsedData
        all_parsed = session.exec(select(ParsedData)).all()
        parsed_count = len(all_parsed)
        
        for parsed in all_parsed:
            session.delete(parsed)
        
        session.commit()
        
        return JSONResponse(content={
            "success": True, 
            "message": f"Statistics reset: {deleted_count} tasks and {parsed_count} parsed data entries deleted"
        })
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=f"Error resetting statistics: {str(e)}")

