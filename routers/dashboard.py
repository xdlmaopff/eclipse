from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Request, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select
from sqlalchemy.orm import joinedload
from database import get_session, engine
from models import User, SessionFile, Task, TaskStatus, SessionStatus, SubscriptionTier, SubscriptionPlan
from dependencies import get_current_active_user
from datetime import datetime
import os
import uuid
import json
import shutil
import asyncio
from typing import List

router = APIRouter()
templates = Jinja2Templates(directory="templates")
templates.env.filters['load_json'] = lambda x: json.loads(x)

UPLOAD_DIR = "user_sessions"


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    current_user: User = Depends(get_current_active_user),
    session: Session = Depends(get_session)
):
    # Get user sessions
    user_sessions = session.exec(
        select(SessionFile).where(SessionFile.owner_id == current_user.id)
    ).all()
    
    # Get recent tasks
    recent_tasks = session.exec(
        select(Task)
        .where(Task.owner_id == current_user.id)
        .order_by(Task.created_at.desc())
        .limit(10)
    ).all()
    
    # Calculate stats
    total_tasks = session.exec(
        select(Task).where(Task.owner_id == current_user.id)
    ).all()
    total_reports = sum(task.total_reports for task in total_tasks)
    successful_reports = sum(task.successful_reports for task in total_tasks)
    failed_reports = sum(task.failed_reports for task in total_tasks)
    
    # Get subscription plans
    plans = session.exec(
        select(SubscriptionPlan).where(SubscriptionPlan.is_active == True)
    ).all()
    
    # Get current plan
    current_plan = session.exec(
        select(SubscriptionPlan).where(SubscriptionPlan.tier == current_user.subscription_tier)
    ).first()
    
    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "user": current_user,
            "sessions": user_sessions,
            "tasks": recent_tasks,
            "plans": plans,
            "current_plan": current_plan,
            "stats": {
                "total_reports": total_reports,
                "successful": successful_reports,
                "failed": failed_reports,
                "sessions_count": len(user_sessions)
            }
        }
    )


@router.post("/api/upload-sessions")
async def upload_sessions(
    files: List[UploadFile] = File(...),
    current_user: User = Depends(get_current_active_user),
    session: Session = Depends(get_session)
):
    if not files:
        return JSONResponse(status_code=400, content={"error": "No files provided"})
    # No subscription limits - unlimited sessions
    
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    uploaded = []
    
    for file in files:
        if not file.filename.endswith('.session'):
            continue
        
        user_dir = os.path.join(UPLOAD_DIR, str(current_user.id))
        os.makedirs(user_dir, exist_ok=True)
        
        file_path = os.path.join(user_dir, file.filename)
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # Create database record
        session_file = SessionFile(
            filename=file.filename,
            file_path=file_path,
            owner_id=current_user.id,
            status=SessionStatus.OFFLINE
        )
        session.add(session_file)
        uploaded.append(file.filename)
    
    session.commit()
    
    return JSONResponse(content={"success": True, "uploaded": uploaded, "message": f"Uploaded {len(uploaded)} session(s)"})


@router.delete("/api/session/{session_id}")
async def delete_session(
    session_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    session: Session = Depends(get_session)
):
    session_file = session.get(SessionFile, session_id)
    if not session_file or session_file.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Session not found")

    file_deleted = False
    if os.path.exists(session_file.file_path):
        try:
            os.remove(session_file.file_path)
            file_deleted = True
        except PermissionError:
            # File is in use, delete from DB but warn user
            pass

    session.delete(session_file)
    session.commit()

    message = "Session deleted successfully"
    if not file_deleted:
        message += " (file in use, will be cleaned up later)"

    return JSONResponse(content={"success": True, "message": message})


# Временное хранилище для авторизации (phone_code_hash, temp_session_path)
_auth_sessions = {}  # {user_id: {phone: str, phone_code_hash: str, temp_session_path: str, session_name: str}}


@router.post("/api/auth-session/start")
async def start_auth_session(
    request: Request,
    current_user: User = Depends(get_current_active_user),
    session: Session = Depends(get_session)
):
    """Начать авторизацию - отправить код на номер телефона"""
    try:
        data = await request.json()
        phone = data.get("phone", "").strip()
        
        if not phone:
            return JSONResponse(status_code=400, content={"error": "Phone number required"})

        # No subscription limits for sessions
        
        # Генерируем имя сессии из номера телефона
        session_name = phone.replace("+", "").replace(" ", "").replace("-", "")
        
        # Импортируем модуль авторизации
        from botnet_modules import auth_session as auth_module
        
        # Отправляем код
        result = await auth_module.send_code_request(phone, session_name)
        
        if result["success"]:
            # Сохраняем промежуточные данные
            _auth_sessions[str(current_user.id)] = {
                "phone": phone,
                "phone_code_hash": result["phone_code_hash"],
                "session_name": session_name
            }
            
            return JSONResponse(content={
                "success": True,
                "message": "Code sent to phone"
            })
        else:
            return JSONResponse(
                status_code=400,
                content={"error": result.get("error", "Failed to send code")}
            )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        )


@router.post("/api/auth-session/verify")
async def verify_auth_session(
    request: Request,
    current_user: User = Depends(get_current_active_user),
    session: Session = Depends(get_session)
):
    """Подтвердить код и завершить авторизацию (или запросить 2FA)"""
    try:
        data = await request.json()
        code = data.get("code", "").strip()
        
        if not code:
            return JSONResponse(status_code=400, content={"error": "Code required"})
        
        # Получаем сохраненные данные
        auth_data = _auth_sessions.get(str(current_user.id))
        if not auth_data:
            return JSONResponse(status_code=400, content={"error": "No active auth session. Please start again."})
        
        phone = auth_data["phone"]
        phone_code_hash = auth_data["phone_code_hash"]
        session_name = auth_data["session_name"]
        
        # Импортируем модуль авторизации
        from botnet_modules import auth_session as auth_module
        
        # Пытаемся войти с кодом
        result = await auth_module.sign_in_with_code(
            phone, code, phone_code_hash, session_name, str(current_user.id)
        )
        
        if result["success"]:
            if result.get("requires_2fa"):
                # Требуется 2FA
                _auth_sessions[str(current_user.id)]["temp_session_path"] = result["temp_session_path"]
                return JSONResponse(content={
                    "success": True,
                    "requires_2fa": True,
                    "message": "2FA password required"
                })
            else:
                # Успешно авторизовано, создаем запись в БД
                session_path = result["session_path"]
                filename = os.path.basename(session_path)
                
                session_file = SessionFile(
                    filename=filename,
                    file_path=session_path,
                    owner_id=current_user.id,
                    status=SessionStatus.OFFLINE
                )
                session.add(session_file)
                session.commit()
                
                # Удаляем временные данные
                _auth_sessions.pop(str(current_user.id), None)
                
                return JSONResponse(content={
                    "success": True,
                    "requires_2fa": False,
                    "message": "Session added successfully"
                })
        else:
            return JSONResponse(
                status_code=400,
                content={"error": result.get("error", "Failed to verify code")}
            )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        )


@router.post("/api/auth-session/2fa")
async def verify_2fa(
    request: Request,
    current_user: User = Depends(get_current_active_user),
    session: Session = Depends(get_session)
):
    """Подтвердить 2FA пароль и завершить авторизацию"""
    try:
        data = await request.json()
        password = data.get("password", "").strip()
        
        if not password:
            return JSONResponse(status_code=400, content={"error": "2FA password required"})
        
        # Получаем сохраненные данные
        auth_data = _auth_sessions.get(str(current_user.id))
        if not auth_data or "temp_session_path" not in auth_data:
            return JSONResponse(status_code=400, content={"error": "No active 2FA session. Please start again."})
        
        phone = auth_data["phone"]
        temp_session_path = auth_data["temp_session_path"]
        session_name = auth_data["session_name"]
        
        # Импортируем модуль авторизации
        from botnet_modules import auth_session as auth_module
        
        # Вводим 2FA пароль
        result = await auth_module.sign_in_with_2fa(
            phone, password, temp_session_path, session_name, str(current_user.id)
        )
        
        if result["success"]:
            # Успешно авторизовано, создаем запись в БД
            session_path = result["session_path"]
            filename = os.path.basename(session_path)
            
            session_file = SessionFile(
                filename=filename,
                file_path=session_path,
                owner_id=current_user.id,
                status=SessionStatus.OFFLINE
            )
            session.add(session_file)
            session.commit()
            
            # Удаляем временные данные
            _auth_sessions.pop(str(current_user.id), None)
            
            return JSONResponse(content={
                "success": True,
                "message": "Session added successfully"
            })
        else:
            return JSONResponse(
                status_code=400,
                content={"error": result.get("error", "Failed to verify 2FA password")}
            )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        )


@router.post("/api/create-task")
async def create_task(
    request: Request,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_active_user),
    session: Session = Depends(get_session)
):
    # Получаем данные из JSON или Form
    try:
        data = await request.json()
    except:
        from fastapi import Form
        data = {
            "task_type": await request.form().get("task_type"),
            "channel": await request.form().get("channel"),
            "post_ids": await request.form().get("post_ids"),
            "comment": await request.form().get("comment"),
            "reason_num": await request.form().get("reason_num"),
            "threads": await request.form().get("threads", 1)
        }
    
    task_type = data.get("task_type")
    
    # Check daily limit (только для репортов)
    if task_type == "report":
        today = datetime.utcnow().date()
        today_tasks = session.exec(
            select(Task).where(
                Task.owner_id == current_user.id,
                Task.task_type == "report",
                Task.created_at >= datetime.combine(today, datetime.min.time())
            )
        ).all()
        
        plan = session.exec(
            select(SubscriptionPlan).where(SubscriptionPlan.tier == current_user.subscription_tier)
        ).first()
        
        if plan and plan.max_reports_per_day:
            total_today = sum(task.total_reports for task in today_tasks)
            if total_today >= plan.max_reports_per_day:
                return JSONResponse(
                    status_code=400,
                    content={"error": f"Daily limit reached: {plan.max_reports_per_day} reports/day"}
                )
    
    # Подготовка данных задачи в зависимости от типа
    if task_type == "report":
        channel = data.get("channel")
        post_ids = data.get("post_ids")
        comment = data.get("comment")
        reason_num = data.get("reason_num")
        
        # Обрабатываем post_ids - может быть строка, список или одно число
        if isinstance(post_ids, str):
            try:
                # Пытаемся распарсить как JSON
                post_ids_parsed = json.loads(post_ids)
            except:
                # Если не JSON, возможно это одно число в строке
                try:
                    post_ids_parsed = [int(post_ids)]
                except:
                    post_ids_parsed = [post_ids]
        elif isinstance(post_ids, list):
            post_ids_parsed = post_ids
        elif post_ids is not None:
            post_ids_parsed = [post_ids]
        else:
            post_ids_parsed = []
        
        task_data = {
            "task_type": task_type,
            "status": TaskStatus.PENDING,
            "channel": channel,
            "post_ids": json.dumps(post_ids_parsed),
            "comment": comment,
            "reason_num": reason_num,
            "threads": data.get("threads", 1),
            "owner_id": current_user.id
        }
    elif task_type == "spam":
        task_data = {
            "task_type": task_type,
            "status": TaskStatus.PENDING,
            "channel": data.get("chat_id", ""),
            "post_ids": json.dumps({
                "spam_type": data.get("spam_type", 1),
                "speed": data.get("speed", 1000),
                "mentions": data.get("mentions", False)
            }),
            "comment": None,
            "reason_num": None,
            "threads": 1,
            "owner_id": current_user.id
        }
    elif task_type == "vote":
        task_data = {
            "task_type": task_type,
            "status": TaskStatus.PENDING,
            "channel": data.get("poll_link", ""),
            "post_ids": json.dumps({
                "options": data.get("options", "")
            }),
            "comment": None,
            "reason_num": None,
            "threads": 1,
            "owner_id": current_user.id
        }
    elif task_type == "join":
        task_data = {
            "task_type": task_type,
            "status": TaskStatus.PENDING,
            "channel": data.get("chat_link", ""),
            "post_ids": json.dumps({
                "has_captcha": data.get("has_captcha", False)
            }),
            "comment": None,
            "reason_num": None,
            "threads": 1,
            "owner_id": current_user.id
        }
    elif task_type == "broadcast":
        task_data = {
            "task_type": task_type,
            "status": TaskStatus.PENDING,
            "channel": json.dumps(data.get("chat_ids", [])),
            "post_ids": json.dumps({
                "message_text": data.get("message_text", ""),
                "file": data.get("file", ""),
                "delay": data.get("delay", 1.0)
            }),
            "comment": None,
            "reason_num": None,
            "threads": 1,
            "owner_id": current_user.id
        }
    elif task_type == "forward":
        task_data = {
            "task_type": task_type,
            "status": TaskStatus.PENDING,
            "channel": data.get("from_chat", ""),
            "post_ids": json.dumps(data.get("message_ids", [])),
            "comment": None,
            "reason_num": None,
            "threads": 1,
            "owner_id": current_user.id
        }
    elif task_type == "interact":
        task_data = {
            "task_type": task_type,
            "status": TaskStatus.PENDING,
            "channel": data.get("chat_id", ""),
            "post_ids": json.dumps({
                "message_ids": data.get("message_ids", []),
                "action_type": data.get("action_type", "like"),
                "comment_text": data.get("comment_text", "")
            }),
            "comment": None,
            "reason_num": None,
            "threads": 1,
            "owner_id": current_user.id
        }
    elif task_type == "parse":
        task_data = {
            "task_type": task_type,
            "status": TaskStatus.PENDING,
            "channel": data.get("chat_id", ""),
            "post_ids": json.dumps({
                "parse_type": data.get("parse_type", "users"),
                "limit": data.get("limit", 100)
            }),
            "comment": None,
            "reason_num": None,
            "threads": 1,
            "owner_id": current_user.id
        }
    elif task_type == "monitor":
        task_data = {
            "task_type": task_type,
            "status": TaskStatus.PENDING,
            "channel": data.get("chat_id", ""),
            "post_ids": json.dumps({
                "keywords": data.get("keywords", [])
            }),
            "comment": None,
            "reason_num": None,
            "threads": 1,
            "owner_id": current_user.id
        }
    elif task_type == "invite":
        task_data = {
            "task_type": task_type,
            "status": TaskStatus.PENDING,
            "channel": data.get("chat_id", ""),
            "post_ids": json.dumps({
                "user_ids": data.get("user_ids", [])
            }),
            "comment": None,
            "reason_num": None,
            "threads": 1,
            "owner_id": current_user.id
        }
    elif task_type == "react":
        task_data = {
            "task_type": task_type,
            "status": TaskStatus.PENDING,
            "channel": data.get("chat_id", ""),
            "post_ids": json.dumps({
                "message_ids": data.get("message_ids", []),
                "reaction": data.get("reaction", "👍")
            }),
            "comment": None,
            "reason_num": None,
            "threads": 1,
            "owner_id": current_user.id
        }
    elif task_type == "delete":
        task_data = {
            "task_type": task_type,
            "status": TaskStatus.PENDING,
            "channel": data.get("chat_id", ""),
            "post_ids": json.dumps({
                "message_ids": data.get("message_ids", [])
            }),
            "comment": None,
            "reason_num": None,
            "threads": 1,
            "owner_id": current_user.id
        }
    else:
        return JSONResponse(status_code=400, content={"error": "Invalid task type"})
    
    # Create task
    task = Task(**task_data)
    session.add(task)
    session.commit()
    session.refresh(task)
    
    # Start task in background
    background_tasks.add_task(run_task, str(task.id))
    
    return JSONResponse(content={"success": True, "task_id": str(task.id), "message": f"{task_type} task created"})


def run_task(task_id: str):
    """Универсальная функция для выполнения задач разных типов"""
    with Session(engine) as session:
        task = session.get(Task, uuid.UUID(task_id))
        if not task:
            return
        
        task.status = TaskStatus.RUNNING
        task.started_at = datetime.utcnow()
        session.add(task)
        session.commit()
        session.refresh(task)
        
        try:
            if task.task_type == "report":
                run_report_task_internal(task, session)
            elif task.task_type == "spam":
                run_spam_task(task, session)
            elif task.task_type == "vote":
                run_vote_task(task, session)
            elif task.task_type == "join":
                run_join_task(task, session)
            elif task.task_type == "broadcast":
                run_broadcast_task(task, session)
            elif task.task_type == "forward":
                run_forward_task(task, session)
            elif task.task_type == "interact":
                run_interact_task(task, session)
            elif task.task_type == "parse":
                run_parse_task(task, session)
            elif task.task_type == "monitor":
                run_monitor_task(task, session)
            else:
                task.status = TaskStatus.FAILED
                task.logs = json.dumps({"error": f"Unknown task type: {task.task_type}"})
        except Exception as e:
            import traceback
            error_trace = traceback.format_exc()
            task.status = TaskStatus.FAILED
            task.logs = json.dumps({"error": str(e), "traceback": error_trace})
        
        session.add(task)
        session.commit()


def run_report_task_internal(task: Task, session: Session):
    """Выполнение задачи репорта"""
    try:
        # Обрабатываем post_ids - может быть строка или уже список
        if isinstance(task.post_ids, str):
            post_ids_list = json.loads(task.post_ids)
        else:
            post_ids_list = task.post_ids
        
        # Убеждаемся, что это список
        if not isinstance(post_ids_list, list):
            post_ids_list = [post_ids_list] if post_ids_list else []
        
        if not post_ids_list:
            task.status = TaskStatus.FAILED
            task.logs = json.dumps({"error": "No post IDs provided"})
            session.add(task)
            session.commit()
            return
        
        user_sessions = session.exec(
            select(SessionFile).where(SessionFile.owner_id == task.owner_id)
        ).all()
        
        if not user_sessions:
            task.status = TaskStatus.FAILED
            task.logs = json.dumps({"error": "No sessions available"})
            session.add(task)
            session.commit()
            return
        
        import sys
        import os
        sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
        from botnet_modules import report as report_module
        
        async def run_reports():
            tasks_list = []
            for session_file in user_sessions:
                tasks_list.append(
                    report_module.send_report(
                        session_file.file_path,
                        post_ids_list,
                        task.reason_num or 4,
                        task.comment or "",
                        task.channel
                    )
                )
            
            results = await asyncio.gather(*tasks_list, return_exceptions=True)
            return results
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        results = loop.run_until_complete(run_reports())
        loop.close()
        
        successful = sum(1 for r in results if r is True)
        failed = len(results) - successful
        
        task.status = TaskStatus.COMPLETED
        task.total_reports = len(results)
        task.successful_reports = successful
        task.failed_reports = failed
        task.completed_at = datetime.utcnow()
        task.logs = json.dumps({"successful": successful, "failed": failed})
        session.add(task)
        session.commit()
        
    except Exception as e:
        task.status = TaskStatus.FAILED
        task.logs = json.dumps({"error": str(e)})
        session.add(task)
        session.commit()


def run_spam_task(task: Task, session: Session):
    """Выполнение задачи спама"""
    try:
        task_params = json.loads(task.post_ids)
        spam_type = task_params.get("spam_type", 1)
        speed = task_params.get("speed", 1000)
        mentions = task_params.get("mentions", False)
        chat_id = task.channel
        
        user_sessions = session.exec(
            select(SessionFile).where(SessionFile.owner_id == task.owner_id)
        ).all()
        
        import sys
        import os
        sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
        from botnet_modules import spam as spam_module
        
        async def run_spams():
            tasks_list = []
            for session_file in user_sessions:
                tasks_list.append(
                    spam_module.send_spam(
                        session_file.file_path,
                        chat_id,
                        spam_type,
                        speed,
                        mentions
                    )
                )
            results = await asyncio.gather(*tasks_list, return_exceptions=True)
            return results
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        results = loop.run_until_complete(run_spams())
        loop.close()
        
        successful = sum(1 for r in results if r is True)
        failed = len(results) - successful
        
        task.status = TaskStatus.COMPLETED
        task.total_reports = len(results)
        task.successful_reports = successful
        task.failed_reports = failed
        task.completed_at = datetime.utcnow()
        session.add(task)
        session.commit()
        
    except Exception as e:
        task.status = TaskStatus.FAILED
        task.logs = json.dumps({"error": str(e)})
        session.add(task)
        session.commit()


def run_vote_task(task: Task, session: Session):
    """Выполнение задачи голосования"""
    try:
        task_params = json.loads(task.post_ids)
        options_str = task_params.get("options", "")
        options = [str(int(opt.strip()) - 1) for opt in options_str.split(",") if opt.strip()]
        
        user_sessions = session.exec(
            select(SessionFile).where(SessionFile.owner_id == task.owner_id)
        ).all()
        
        import sys
        import os
        sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
        from raidfunctions import polls
        from telethon import TelegramClient, functions
        import toml
        
        # Парсим ссылку на опрос
        poll_link = task.channel
        link_parts = poll_link.split("/")
        channel = link_parts[3] if len(link_parts) > 3 else ""
        private = False
        
        if channel == "c":
            private = True
            poll_id_str = link_parts[5] if len(link_parts) > 5 else link_parts[4]
            if "?" in poll_id_str:
                poll_id_str = poll_id_str.split("?")[0]
            poll_id = int(poll_id_str)
            channel_id_str = link_parts[4]
            if "?" in channel_id_str:
                channel_id_str = channel_id_str.split("?")[0]
            channel_id = -1000000000000 - int(channel_id_str)
        else:
            poll_id_str = link_parts[4] if len(link_parts) > 4 else ""
            if "?" in poll_id_str:
                poll_id_str = poll_id_str.split("?")[0]
            poll_id = int(poll_id_str)
            channel_id = channel
        
        # Загружаем конфиг
        config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.toml")
        with open(config_path) as f:
            config = toml.load(f)
        api_id = config["authorization"]["api_id"]
        api_hash = config["authorization"]["api_hash"]
        
        successful = 0
        failed = 0
        
        async def vote_for_session(session_file):
            try:
                client = TelegramClient(session_file.file_path.replace(".session", ""), api_id, api_hash)
                await client.connect()
                if not await client.is_user_authorized():
                    return False
                
                await client(functions.messages.SendVoteRequest(
                    peer=channel_id,
                    msg_id=poll_id,
                    options=options
                ))
                await client.disconnect()
                return True
            except Exception as e:
                print(f"Vote error: {e}")
                return False
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        tasks_list = [vote_for_session(sf) for sf in user_sessions]
        results = loop.run_until_complete(asyncio.gather(*tasks_list, return_exceptions=True))
        loop.close()
        
        successful = sum(1 for r in results if r is True)
        failed = len(results) - successful
        
        task.status = TaskStatus.COMPLETED
        task.total_reports = len(results)
        task.successful_reports = successful
        task.failed_reports = failed
        task.completed_at = datetime.utcnow()
        session.add(task)
        session.commit()
        
    except Exception as e:
        task.status = TaskStatus.FAILED
        task.logs = json.dumps({"error": str(e)})
        session.add(task)
        session.commit()


def run_join_task(task: Task, session: Session):
    """Выполнение задачи join/leave"""
    try:
        task_params = json.loads(task.post_ids)
        has_captcha = task_params.get("has_captcha", False)
        chat_link = task.channel
        
        user_sessions = session.exec(
            select(SessionFile).where(SessionFile.owner_id == task.owner_id)
        ).all()
        
        import sys
        import os
        sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
        from botnet_modules import join as join_module
        
        async def run_joins():
            tasks_list = []
            for session_file in user_sessions:
                tasks_list.append(
                    join_module.join_chat(
                        session_file.file_path,
                        chat_link,
                        has_captcha
                    )
                )
            results = await asyncio.gather(*tasks_list, return_exceptions=True)
            return results
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        results = loop.run_until_complete(run_joins())
        loop.close()
        
        successful = sum(1 for r in results if r is True)
        failed = len(results) - successful
        
        task.status = TaskStatus.COMPLETED
        task.total_reports = len(results)
        task.successful_reports = successful
        task.failed_reports = failed
        task.completed_at = datetime.utcnow()
        session.add(task)
        session.commit()
        
    except Exception as e:
        task.status = TaskStatus.FAILED
        task.logs = json.dumps({"error": str(e)})
        session.add(task)
        session.commit()


def run_broadcast_task(task: Task, session: Session):
    """Выполнение задачи рассылки"""
    try:
        task_params = json.loads(task.post_ids)
        chat_ids = json.loads(task.channel)
        message_text = task_params.get("message_text", "")
        delay = task_params.get("delay", 1.0)
        
        user_sessions = session.exec(
            select(SessionFile).where(SessionFile.owner_id == task.owner_id)
        ).all()
        
        import sys
        import os
        sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
        from botnet_modules import broadcast as broadcast_module
        
        async def run_broadcasts():
            tasks_list = []
            for session_file in user_sessions:
                tasks_list.append(
                    broadcast_module.broadcast_message(
                        session_file.file_path,
                        chat_ids,
                        message_text,
                        None,  # file_path
                        delay
                    )
                )
            results = await asyncio.gather(*tasks_list, return_exceptions=True)
            return results
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        results = loop.run_until_complete(run_broadcasts())
        loop.close()
        
        successful = sum(1 for r in results if isinstance(r, dict) and any(r.values()))
        failed = len(results) - successful
        
        task.status = TaskStatus.COMPLETED
        task.total_reports = len(results)
        task.successful_reports = successful
        task.failed_reports = failed
        task.completed_at = datetime.utcnow()
        session.add(task)
        session.commit()
        
    except Exception as e:
        task.status = TaskStatus.FAILED
        task.logs = json.dumps({"error": str(e)})
        session.add(task)
        session.commit()


def run_forward_task(task: Task, session: Session):
    """Выполнение задачи пересылки в публичные чаты"""
    try:
        from_chat = task.channel  # Теперь channel содержит from_chat
        message_ids = json.loads(task.post_ids)

        user_sessions = session.exec(
            select(SessionFile).where(SessionFile.owner_id == task.owner_id)
        ).all()

        import sys
        import os
        sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
        from botnet_modules import forward as forward_module

        async def run_forwards():
            tasks_list = []
            for session_file in user_sessions:
                tasks_list.append(
                    forward_module.forward_to_all_public_chats(
                        session_file.file_path,
                        from_chat,
                        message_ids
                    )
                )
            results = await asyncio.gather(*tasks_list, return_exceptions=True)
            return results

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        results = loop.run_until_complete(run_forwards())
        loop.close()

        # Подсчет успешных пересылок
        total_forwards = 0
        successful_forwards = 0
        errors = []

        print(f"Forward task results for {len(results)} sessions:")
        for i, result in enumerate(results):
            print(f"Session {i+1}: {result}")
            if isinstance(result, dict):
                if "error" in result:
                    errors.append(result["error"])
                    print(f"  Error: {result['error']}")
                else:
                    total_forwards += len(result)
                    successful_forwards += sum(1 for v in result.values() if v is True)
                    print(f"  Forwarded to {len(result)} chats")

        if errors and total_forwards == 0:
            task.status = TaskStatus.FAILED
            task.logs = json.dumps({"errors": errors})
        else:
            task.status = TaskStatus.COMPLETED
            logs = {"message": f"Forwarded to {successful_forwards}/{total_forwards} chats across {len(results)} accounts"}
            if errors:
                logs["errors"] = errors
            task.logs = json.dumps(logs)

        task.total_reports = total_forwards
        task.successful_reports = successful_forwards
        task.failed_reports = total_forwards - successful_forwards
        task.completed_at = datetime.utcnow()
        session.add(task)
        session.commit()

    except Exception as e:
        task.status = TaskStatus.FAILED
        task.logs = json.dumps({"error": str(e)})
        session.add(task)
        session.commit()


def run_interact_task(task: Task, session: Session):
    """Выполнение задачи лайков/комментариев"""
    try:
        task_params = json.loads(task.post_ids)
        chat_id = task.channel
        message_ids = task_params.get("message_ids", [])
        action_type = task_params.get("action_type", "like")
        comment_text = task_params.get("comment_text", "")
        
        user_sessions = session.exec(
            select(SessionFile).where(SessionFile.owner_id == task.owner_id)
        ).all()
        
        import sys
        import os
        sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
        from botnet_modules import interact as interact_module
        
        async def run_interactions():
            tasks_list = []
            for session_file in user_sessions:
                for msg_id in message_ids:
                    if action_type in ["like", "both"]:
                        tasks_list.append(interact_module.like_message(session_file.file_path, chat_id, msg_id))
                    if action_type in ["comment", "both"]:
                        tasks_list.append(interact_module.comment_message(session_file.file_path, chat_id, msg_id, comment_text))
            results = await asyncio.gather(*tasks_list, return_exceptions=True)
            return results
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        results = loop.run_until_complete(run_interactions())
        loop.close()
        
        successful = sum(1 for r in results if r is True)
        failed = len(results) - successful
        
        task.status = TaskStatus.COMPLETED
        task.total_reports = len(results)
        task.successful_reports = successful
        task.failed_reports = failed
        task.completed_at = datetime.utcnow()
        session.add(task)
        session.commit()
        
    except Exception as e:
        task.status = TaskStatus.FAILED
        task.logs = json.dumps({"error": str(e)})
        session.add(task)
        session.commit()


def run_parse_task(task: Task, session: Session):
    """Выполнение задачи парсинга"""
    try:
        task_params = json.loads(task.post_ids)
        parse_type = task_params.get("parse_type", "users")
        chat_id = task.channel
        limit = task_params.get("limit", 100)
        
        user_sessions = session.exec(
            select(SessionFile).where(SessionFile.owner_id == task.owner_id)
        ).all()
        
        if not user_sessions:
            task.status = TaskStatus.FAILED
            task.logs = json.dumps({"error": "No sessions available"})
            session.add(task)
            session.commit()
            return
        
        import sys
        import os
        sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
        from botnet_modules import parse as parse_module
        from models import ParsedData
        
        async def run_parse():
            session_file = user_sessions[0]  # Use first session
            if parse_type == "users":
                return await parse_module.parse_users(session_file.file_path, chat_id, limit)
            elif parse_type == "messages":
                return await parse_module.parse_messages(session_file.file_path, chat_id, limit)
            elif parse_type == "chats":
                return await parse_module.parse_chats(session_file.file_path, limit)
            return []
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        parsed_data = loop.run_until_complete(run_parse())
        loop.close()
        
        # Save parsed data
        parsed = ParsedData(
            task_id=task.id,
            data_type=parse_type,
            data=json.dumps(parsed_data)
        )
        session.add(parsed)
        
        task.status = TaskStatus.COMPLETED
        task.total_reports = len(parsed_data)
        task.successful_reports = len(parsed_data)
        task.failed_reports = 0
        task.result_data = json.dumps(parsed_data)
        task.completed_at = datetime.utcnow()
        
    except Exception as e:
        task.status = TaskStatus.FAILED
        task.logs = json.dumps({"error": str(e)})


def run_monitor_task(task: Task, session: Session):
    """Выполнение задачи мониторинга (запускается в фоне)"""
    try:
        task_params = json.loads(task.post_ids)
        chat_id = task.channel
        keywords = task_params.get("keywords", [])
        
        user_sessions = session.exec(
            select(SessionFile).where(SessionFile.owner_id == task.owner_id)
        ).all()
        
        if not user_sessions:
            task.status = TaskStatus.FAILED
            task.logs = json.dumps({"error": "No sessions available"})
            session.add(task)
            session.commit()
            return
        
        # Monitor runs in background, mark as running
        task.status = TaskStatus.RUNNING
        task.logs = json.dumps({"message": "Monitoring started", "chat_id": chat_id, "keywords": keywords})
        # Note: Actual monitoring would need a separate background process
        
    except Exception as e:
        task.status = TaskStatus.FAILED
        task.logs = json.dumps({"error": str(e)})


@router.get("/api/user-stats")
async def get_user_stats(
    current_user: User = Depends(get_current_active_user),
    session: Session = Depends(get_session)
):
    """Получить статистику пользователя за сегодня"""
    from datetime import date
    today = date.today()
    
    today_tasks = session.exec(
        select(Task).where(
            Task.owner_id == current_user.id,
            Task.created_at >= datetime.combine(today, datetime.min.time())
        )
    ).all()
    
    today_actions = sum(task.total_reports for task in today_tasks)
    total_success = sum(task.successful_reports for task in today_tasks)
    total_failed = sum(task.failed_reports for task in today_tasks)
    total = total_success + total_failed
    success_rate = int((total_success / total * 100) if total > 0 else 0)
    
    return JSONResponse(content={
        "today_actions": today_actions,
        "success_rate": success_rate
    })


@router.get("/api/task/{task_id}/export")
async def export_task_data(
    task_id: uuid.UUID,
    format: str = "json",
    current_user: User = Depends(get_current_active_user),
    session: Session = Depends(get_session)
):
    """Экспорт данных задачи в JSON или CSV"""
    task = session.get(Task, task_id)
    if not task or task.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Task not found")
    
    if task.task_type == "parse" and task.result_data:
        data = json.loads(task.result_data)
        
        if format == "csv":
            import csv
            from io import StringIO
            output = StringIO()
            if data:
                writer = csv.DictWriter(output, fieldnames=data[0].keys())
                writer.writeheader()
                writer.writerows(data)
            return Response(
                content=output.getvalue(),
                media_type="text/csv",
                headers={"Content-Disposition": f"attachment; filename=task_{task_id}.csv"}
            )
        else:
            return JSONResponse(content=data)
    
    return JSONResponse(content={"error": "No data to export"})


@router.get("/api/task/{task_id}")
async def get_task_status(
    task_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    session: Session = Depends(get_session)
):
    task = session.get(Task, task_id)
    if not task or task.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Task not found")
    
    return JSONResponse(content={
        "id": str(task.id),
        "status": task.status,
        "total_reports": task.total_reports,
        "successful_reports": task.successful_reports,
        "failed_reports": task.failed_reports,
        "logs": json.loads(task.logs) if task.logs else None
    })

