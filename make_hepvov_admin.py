"""
Скрипт для назначения админки пользователю hepvov
Использование: python make_hepvov_admin.py
"""
from database import get_session, init_db
from models import User, UserRole
from sqlmodel import Session, select

def make_hepvov_admin():
    init_db()
    session = next(get_session())
    
    username = "hepvov"
    
    # Ищем пользователя
    user = session.exec(select(User).where(User.username == username)).first()
    
    if not user:
        print(f"❌ Пользователь '{username}' не найден!")
        print("Сначала зарегистрируйтесь на сайте, затем запустите этот скрипт снова.")
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
    print(f"\nТеперь вы можете зайти на /admin")

if __name__ == "__main__":
    make_hepvov_admin()

