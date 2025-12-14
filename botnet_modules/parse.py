import asyncio
import os
import toml
from telethon import TelegramClient
from typing import List, Dict, Optional

_config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.toml")
with open(_config_path, "r", encoding="utf-8") as f:
    config = toml.load(f)

api_id = config["authorization"]["api_id"]
api_hash = config["authorization"]["api_hash"]


async def parse_users(acc_session: str, chat_id: str, limit: int = 100) -> List[Dict]:
    """Асинхронно парсит пользователей из чата/канала"""
    try:
        # Telethon ожидает путь БЕЗ расширения .session
        normalized_path = os.path.normpath(acc_session)
        if normalized_path.endswith('.session'):
            session_path = normalized_path[:-8]  # Убираем .session
        else:
            session_path = normalized_path
        
        async with TelegramClient(session_path, api_id, api_hash) as client:
            if not await client.is_user_authorized():
                return []
            
            peer = await client.get_entity(chat_id)
            users = []
            
            async for user in client.iter_participants(peer, limit=limit):
                if user and not user.bot:
                    users.append({
                        "id": user.id,
                        "username": user.username or "",
                        "first_name": user.first_name or "",
                        "last_name": user.last_name or "",
                        "phone": user.phone or "",
                        "is_premium": getattr(user, 'premium', False)
                    })
        
        return users
    except Exception as e:
        print(f"Parse users error: {e}")
        return []


async def parse_messages(acc_session: str, chat_id: str, limit: int = 100) -> List[Dict]:
    """Асинхронно парсит сообщения из чата/канала"""
    try:
        # Telethon ожидает путь БЕЗ расширения .session
        normalized_path = os.path.normpath(acc_session)
        if normalized_path.endswith('.session'):
            session_path = normalized_path[:-8]  # Убираем .session
        else:
            session_path = normalized_path
        
        async with TelegramClient(session_path, api_id, api_hash) as client:
            if not await client.is_user_authorized():
                return []
            
            peer = await client.get_entity(chat_id)
            messages = []
            
            async for msg in client.iter_messages(peer, limit=limit):
                if msg:
                    messages.append({
                        "id": msg.id,
                        "date": msg.date.isoformat() if msg.date else "",
                        "text": msg.text or "",
                        "from_id": msg.from_id.user_id if msg.from_id else None,
                        "views": msg.views or 0,
                        "forwards": msg.forwards or 0
                    })
        
        return messages
    except Exception as e:
        print(f"Parse messages error: {e}")
        return []


async def parse_chats(acc_session: str, limit: int = 100) -> List[Dict]:
    """Асинхронно парсит список чатов/каналов пользователя"""
    try:
        # Telethon ожидает путь БЕЗ расширения .session
        normalized_path = os.path.normpath(acc_session)
        if normalized_path.endswith('.session'):
            session_path = normalized_path[:-8]  # Убираем .session
        else:
            session_path = normalized_path
        
        async with TelegramClient(session_path, api_id, api_hash) as client:
            if not await client.is_user_authorized():
                return []
            
            dialogs = []
            async for dialog in client.iter_dialogs(limit=limit):
                if dialog.entity:
                    from telethon.tl.types import Channel, Chat
                    dialogs.append({
                        "id": dialog.entity.id,
                        "title": dialog.entity.title if hasattr(dialog.entity, 'title') else "",
                        "username": dialog.entity.username if hasattr(dialog.entity, 'username') else "",
                        "participants_count": getattr(dialog.entity, 'participants_count', 0),
                        "is_channel": isinstance(dialog.entity, Channel),
                        "is_group": isinstance(dialog.entity, Chat)
                    })
        
        return dialogs
    except Exception as e:
        print(f"Parse chats error: {e}")
        return []

