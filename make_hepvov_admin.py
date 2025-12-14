"""
Скрипт для создания или назначения админки пользователю hepvov
Использование: python make_hepvov_admin.py
"""
from database import get_session, init_db
from models import User, UserRole
from dependencies import get_password_hash
from sqlmodel import Session, select

def create_or_make_hepvov_admin():
    init_db()
    session = next(get_session())

    username = "hepvov"
    email = "hepvov@mail.ru"
    password = "241209"

    # Ищем пользователя
    user = session.exec(select(User).where(User.username == username)).first()

    if not user:
        # Создаем пользователя
        hashed_password = get_password_hash(password)
        user = User(
            email=email,
            username=username,
            hashed_password=hashed_password,
            role=UserRole.ADMIN,
            is_active=True,
            is_verified=True
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        print(f"✅ Пользователь '{username}' создан и назначен администратором!")
        print(f"   Email: {user.email}")
        print(f"   ID: {user.id}")
        print(f"   Пароль: {password}")
        print(f"\nТеперь вы можете зайти на /admin с логином {email} и паролем {password}")
    else:
        if user.role != UserRole.ADMIN:
            user.role = UserRole.ADMIN
            session.add(user)
            session.commit()
            print(f"✅ Пользователь '{username}' теперь администратор!")
        else:
            print(f"ℹ️ Пользователь '{username}' уже является администратором!")

if __name__ == "__main__":
    create_or_make_hepvov_admin()
