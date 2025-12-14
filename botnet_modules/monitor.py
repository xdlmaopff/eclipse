import asyncio
import os
import toml
from telethon import TelegramClient, events
from typing import Callable, Optional

_config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.toml")
with open(_config_path, "r", encoding="utf-8") as f:
    config = toml.load(f)

api_id = config["authorization"]["api_id"]
api_hash = config["authorization"]["api_hash"]


async def start_monitoring(
    acc_session: str,
    chat_id: str,
    callback: Optional[Callable] = None,
    keywords: Optional[list] = None
) -> bool:
    """Асинхронно запускает мониторинг канала/чата на новые сообщения"""
    try:
        if not acc_session.endswith('.session'):
            acc_session = acc_session + '.session'
        
        client = TelegramClient(acc_session.replace('.session', ''), api_id, api_hash)
        await client.connect()
        
        if not await client.is_user_authorized():
            await client.disconnect()
            return False
        
        peer = await client.get_entity(chat_id)
        
        @client.on(events.NewMessage(chats=peer))
        async def handler(event):
            if keywords:
                if any(keyword.lower() in (event.message.text or "").lower() for keyword in keywords):
                    if callback:
                        await callback({
                            "id": event.message.id,
                            "text": event.message.text,
                            "date": event.message.date.isoformat(),
                            "from_id": event.message.from_id.user_id if event.message.from_id else None
                        })
            else:
                if callback:
                    await callback({
                        "id": event.message.id,
                        "text": event.message.text,
                        "date": event.message.date.isoformat(),
                        "from_id": event.message.from_id.user_id if event.message.from_id else None
                    })
        
        # Keep client running
        await client.run_until_disconnected()
        return True
    except Exception as e:
        print(f"Monitor error: {e}")
        return False

