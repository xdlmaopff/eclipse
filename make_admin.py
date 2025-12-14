"""
Скрипт для назначения админки существующему пользователю
Использование: python make_admin.py
"""
from database import get_session, init_db
from models import User, UserRole
from sqlmodel import Session, select

def make_admin():
    init_db()
    session = next(get_session())
    
    username = input("Username пользователя для назначения админки: ")
    
    # Ищем пользователя
    user = session.exec(select(User).where(User.username == username)).first()
    
    if not user:
        print(f"❌ Пользователь '{username}' не найден!")
        return
    
    if user.role == UserRole.ADMIN:
        print(f"ℹ️ Пользователь '{username}' уже является администратором!")
        return
    
    # Назначаем админку
    user.role = UserRole.ADMIN
    session.add(user)
    session.commit()
    
    print(f"✅ Пользователь '{username}' теперь администратор!")
    print(f"   Email: {user.email}")
    print(f"   ID: {user.id}")

if __name__ == "__main__":
    make_admin()

