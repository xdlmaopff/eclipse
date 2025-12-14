from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List
from sqlalchemy.orm import Mapped, relationship
from datetime import datetime
from enum import Enum
import uuid


class SubscriptionTier(str, Enum):
    FREE = "free"
    PRO = "pro"
    ELITE = "elite"


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class SessionStatus(str, Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    BANNED = "banned"


class UserRole(str, Enum):
    USER = "user"
    ADMIN = "admin"


class TaskType(str, Enum):
    report = "report"
    spam = "spam"
    broadcast = "broadcast"
    parse = "parse"
    invite = "invite"
    react = "react"
    delete_messages = "delete_messages"
    monitor = "monitor"
    custom_script = "custom_script"
    join = "join"
    vote = "vote"
    forward = "forward"
    interact = "interact"
    delete = "delete"


class Proxy(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    ip: str
    port: int
    username: Optional[str] = None
    password: Optional[str] = None
    type: str = "http"  # http, socks5
    status: str = "active"  # active, banned
    last_used: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class User(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    email: str = Field(unique=True, index=True)
    username: str = Field(unique=True, index=True)
    hashed_password: str
    is_active: bool = True
    is_verified: bool = False
    role: UserRole = UserRole.USER
    subscription_tier: SubscriptionTier = SubscriptionTier.FREE
    subscription_expires_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

    sessions: "SessionFile" = Relationship(back_populates="owner")
    tasks: "Task" = Relationship(back_populates="owner")
    subscription_requests: "SubscriptionRequest" = Relationship(back_populates="user")
    task_logs: "TaskLog" = Relationship(back_populates="user")
    custom_scripts: "CustomScript" = Relationship(back_populates="owner")


class SessionFile(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    filename: str
    file_path: str
    status: SessionStatus = SessionStatus.OFFLINE
    proxy_id: Optional[uuid.UUID] = Field(foreign_key="proxy.id")
    reliability: int = 100  # 0-100
    owner_id: uuid.UUID = Field(foreign_key="user.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_used: Optional[datetime] = None

    owner: User = Relationship(back_populates="sessions")
    proxy: Optional[Proxy] = Relationship()


class Task(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    task_type: TaskType
    status: TaskStatus = TaskStatus.PENDING
    params: Optional[str] = None  # JSON string of additional parameters
    channel: Optional[str] = None  # Chat/channel identifier
    post_ids: Optional[str] = None  # JSON string of post/message IDs or parameters
    comment: Optional[str] = None  # Comment text for reports
    reason_num: Optional[int] = None  # Report reason number
    progress: int = 0
    priority: int = 1  # 1-10, higher for Elite
    threads: int = 1
    total_actions: int = 0
    successful_actions: int = 0
    failed_actions: int = 0
    total_reports: int = 0
    successful_reports: int = 0
    failed_reports: int = 0
    logs: Optional[str] = None  # JSON string of logs
    result_data: Optional[str] = None  # JSON string for parsed data, etc.
    owner_id: uuid.UUID = Field(foreign_key="user.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    owner: User = Relationship(back_populates="tasks")


class TaskLog(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="user.id")
    task_id: Optional[uuid.UUID] = Field(foreign_key="task.id")
    action: str
    details: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

    user: User = Relationship(back_populates="task_logs")
    task: Optional[Task] = Relationship()


class ParsedData(SQLModel, table=True):
    """Хранение результатов парсинга"""
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    task_id: uuid.UUID = Field(foreign_key="task.id")
    data_type: str  # "users", "messages", "chats"
    data: str  # JSON string of parsed data
    created_at: datetime = Field(default_factory=datetime.utcnow)


class CustomScript(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str
    code: str  # Python code
    owner_id: uuid.UUID = Field(foreign_key="user.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)

    owner: User = Relationship(back_populates="custom_scripts")


class SubscriptionPlan(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    tier: SubscriptionTier = Field(unique=True)
    name: str
    price_monthly: float
    max_accounts: Optional[int] = None  # None = unlimited
    max_reports_per_day: Optional[int] = None  # None = unlimited
    priority_support: bool = False
    is_active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)


class PromoCode(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    code: str = Field(unique=True)
    discount_percent: int = 0
    max_uses: Optional[int] = None
    used_count: int = 0
    expires_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Blacklist(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    type: str  # "user", "channel", "chat"
    identifier: str  # username, id, etc.
    reason: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class SubscriptionRequestStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class SubscriptionRequest(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="user.id")
    requested_tier: SubscriptionTier
    message: str
    status: SubscriptionRequestStatus = SubscriptionRequestStatus.PENDING
    admin_notes: Optional[str] = None
    reviewed_by: Optional[uuid.UUID] = None
    reviewed_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

    user: User = Relationship(back_populates="subscription_requests")

