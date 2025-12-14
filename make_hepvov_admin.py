"""
Скрипт для назначения админки пользователю
Использование: python make_hepvov_admin.py [username]
Если username не указан, используется 'hepvov'
"""
import sys
from database import get_session, init_db
from models import User, UserRole
from sqlmodel import Session, select

def make_user_admin(username: str):
    init_db()
    session = next(get_session())

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
    username = sys.argv[1] if len(sys.argv) > 1 else "hepvov"
    make_user_admin(username)
