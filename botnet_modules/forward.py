import asyncio
import os
import toml
from telethon import TelegramClient
from telethon.errors import FloodWaitError
from typing import List, Dict, Any

_config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.toml")
with open(_config_path, "r", encoding="utf-8") as f:
    config = toml.load(f)

api_id = config["authorization"]["api_id"]
api_hash = config["authorization"]["api_hash"]


async def forward_messages(
    acc_session: str,
    from_chat: str,
    to_chat: str,
    message_ids: List[int]
) -> bool:
    """Асинхронно пересылает сообщения из одного чата в другой"""
    try:
        # Telethon ожидает путь БЕЗ расширения .session
        normalized_path = os.path.normpath(acc_session)
        if normalized_path.endswith('.session'):
            session_path = normalized_path[:-8]  # Убираем .session
        else:
            session_path = normalized_path

        async with TelegramClient(session_path, api_id, api_hash) as client:
            if not await client.is_user_authorized():
                return False

            from_peer = await client.get_entity(from_chat)
            to_peer = await client.get_entity(to_chat)

            await client.forward_messages(to_peer, message_ids, from_peer)

        return True
    except Exception as e:
        print(f"Forward error: {e}")
        return False


async def forward_to_all_public_chats(
    acc_session: str,
    from_chat: str,
    message_ids: List[int]
) -> Dict[str, Any]:
    """Пересылает сообщения из канала во все публичные чаты аккаунта"""
    results = {}

    try:
        # Telethon ожидает путь БЕЗ расширения .session
        normalized_path = os.path.normpath(acc_session)
        if normalized_path.endswith('.session'):
            session_path = normalized_path[:-8]  # Убираем .session
        else:
            session_path = normalized_path

        async with TelegramClient(session_path, api_id, api_hash) as client:
            if not await client.is_user_authorized():
                print(f"Session not authorized: {session_path}")
                return {"error": "Session not authorized"}

            # Проверяем доступ к исходному чату
            try:
                from_entity = await client.get_entity(from_chat)
                print(f"From chat: {from_entity.title if hasattr(from_entity, 'title') else from_chat}")
            except Exception as e:
                print(f"Cannot access from_chat {from_chat}: {e}")
                return {"error": f"Cannot access from_chat: {e}"}

            # Получаем все диалоги
            dialogs = await client.get_dialogs()
            print(f"Found {len(dialogs)} dialogs")

            # Фильтруем публичные чаты (с username)
            public_chats = []
            for dialog in dialogs:
                entity = dialog.entity
                if hasattr(entity, 'username') and entity.username:
                    public_chats.append(entity.username)

            print(f"Found {len(public_chats)} public chats: {public_chats[:5]}...")  # Показываем первые 5

            if not public_chats:
                return {"error": "No public chats found"}

            # Пересылаем в каждый публичный чат
            success_count = 0
            for chat_username in public_chats:
                try:
                    peer = await client.get_entity(chat_username)

                    await client.forward_messages(peer, message_ids, from_entity)

                    results[chat_username] = True
                    success_count += 1
                    await asyncio.sleep(2.0)  # Увеличенная задержка чтобы избежать флуда
                except FloodWaitError as e:
                    print(f"FloodWait for {chat_username}: waiting {e.seconds} seconds")
                    await asyncio.sleep(e.seconds)
                    # Повторяем попытку после ожидания
                    try:
                        await client.forward_messages(peer, message_ids, from_entity)
                        results[chat_username] = True
                        success_count += 1
                    except Exception as retry_e:
                        print(f"Forward error after retry for {chat_username}: {retry_e}")
                        results[chat_username] = f"Error: {str(retry_e)}"
                except Exception as e:
                    print(f"Forward error for {chat_username}: {e}")
                    results[chat_username] = f"Error: {str(e)}"

            print(f"Successfully forwarded to {success_count}/{len(public_chats)} chats")
            return results

    except Exception as e:
        print(f"Forward setup error: {e}")
        return {"error": str(e)}

