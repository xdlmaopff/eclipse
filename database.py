from sqlmodel import SQLModel, create_engine, Session, select
# Импортируем все модели для регистрации в метаданных
from models import User, SubscriptionPlan, SubscriptionTier, SessionFile, Task, SubscriptionRequest, ParsedData
import os
import sqlite3

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./botnet.db")
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False}, echo=False)


def migrate_db():
    """Добавляет недостающие столбцы в существующие таблицы"""
    if DATABASE_URL.startswith("sqlite"):
        # Получаем путь к файлу базы данных
        db_path = DATABASE_URL.replace("sqlite:///", "")
        if not os.path.exists(db_path):
            return  # База данных еще не создана

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        try:
            # Проверяем наличие столбцов в таблице task
            cursor.execute("PRAGMA table_info(task)")
            columns = [column[1] for column in cursor.fetchall()]

            if "result_data" not in columns:
                cursor.execute("ALTER TABLE task ADD COLUMN result_data TEXT")
                conn.commit()
                print("Migration: Added result_data column to task table")

            if "total_reports" not in columns:
                cursor.execute("ALTER TABLE task ADD COLUMN total_reports INTEGER DEFAULT 0")
                conn.commit()
                print("Migration: Added total_reports column to task table")

            if "successful_reports" not in columns:
                cursor.execute("ALTER TABLE task ADD COLUMN successful_reports INTEGER DEFAULT 0")
                conn.commit()
                print("Migration: Added successful_reports column to task table")

            if "failed_reports" not in columns:
                cursor.execute("ALTER TABLE task ADD COLUMN failed_reports INTEGER DEFAULT 0")
                conn.commit()
                print("Migration: Added failed_reports column to task table")
        except Exception as e:
            print(f"Migration error: {e}")
        finally:
            conn.close()


def init_db():
    # Убеждаемся, что все модели импортированы
    SQLModel.metadata.create_all(engine)
    
    # Выполняем миграции
    migrate_db()
    
    # Создаем планы подписки по умолчанию
    with Session(engine) as session:
        plans = [
            SubscriptionPlan(
                tier=SubscriptionTier.FREE,
                name="Free",
                price_monthly=0.0,
                max_accounts=5,
                max_reports_per_day=100
            ),
            SubscriptionPlan(
                tier=SubscriptionTier.PRO,
                name="Pro",
                price_monthly=29.99,
                max_accounts=None,
                max_reports_per_day=5000
            ),
            SubscriptionPlan(
                tier=SubscriptionTier.ELITE,
                name="Elite",
                price_monthly=99.99,
                max_accounts=None,
                max_reports_per_day=None,
                priority_support=True
            )
        ]
        
        for plan in plans:
            existing = session.exec(
                select(SubscriptionPlan).where(SubscriptionPlan.tier == plan.tier)
            ).first()
            if not existing:
                session.add(plan)
        
        session.commit()


def get_session():
    with Session(engine) as session:
        yield session

