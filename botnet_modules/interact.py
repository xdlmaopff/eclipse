import asyncio
import os
import toml
from telethon import TelegramClient, functions, types
from typing import List, Optional

_config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.toml")
with open(_config_path, "r", encoding="utf-8") as f:
    config = toml.load(f)

api_id = config["authorization"]["api_id"]
api_hash = config["authorization"]["api_hash"]


async def like_message(acc_session: str, chat_id: str, message_id: int) -> bool:
    """Асинхронно ставит лайк на сообщение"""
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
            
            peer = await client.get_entity(chat_id)
            
            try:
                await client(functions.messages.SendReactionRequest(
                    peer=peer,
                    msg_id=message_id,
                    reaction=[types.ReactionEmoji(emoticon="👍")]
                ))
                return True
            except Exception as e:
                print(f"Like error: {e}")
                return False
    except Exception as e:
        print(f"Like error: {e}")
        return False


async def comment_message(acc_session: str, chat_id: str, message_id: int, comment_text: str) -> bool:
    """Асинхронно комментирует сообщение"""
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
            
            peer = await client.get_entity(chat_id)
            
            try:
                await client.send_message(peer, comment_text, reply_to=message_id)
                return True
            except Exception as e:
                print(f"Comment error: {e}")
                return False
    except Exception as e:
        print(f"Comment error: {e}")
        return False

