import asyncio
import os
import toml
from telethon import TelegramClient
from telethon.errors import FloodWaitError
from typing import List, Optional, Dict
from telethon.tl.types import Poll, PollAnswer, InputGeoPoint, InputPhoneContact

_config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.toml")
with open(_config_path, "r", encoding="utf-8") as f:
    config = toml.load(f)

api_id = config["authorization"]["api_id"]
api_hash = config["authorization"]["api_hash"]


async def broadcast_message(
    acc_session: str,
    chat_ids: List[str],
    message_text: str = "",
    media_type: str = 'text',
    media_path: Optional[str] = None,
    poll_question: Optional[str] = None,
    poll_options: Optional[List[str]] = None,
    lat: Optional[float] = None,
    lon: Optional[float] = None,
    contact_phone: Optional[str] = None,
    contact_first_name: Optional[str] = None,
    contact_last_name: Optional[str] = None,
    delay: float = 1.0
) -> Dict[str, bool]:
    """Асинхронно рассылает сообщение или медиа в несколько чатов/каналов. Поддерживает текст, фото, видео, аудио, документы, опросы, геолокации, контакты."""
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
                return {chat_id: False for chat_id in chat_ids}
            
            for chat_id in chat_ids:
                try:
                    peer = await client.get_entity(chat_id)
                    
                    if media_type == 'text':
                        await client.send_message(peer, message_text)
                    elif media_type in ['photo', 'video', 'audio', 'document']:
                        if media_path and os.path.exists(media_path):
                            await client.send_file(peer, media_path, caption=message_text)
                        else:
                            results[chat_id] = False
                            continue
                    elif media_type == 'poll':
                        if poll_question and poll_options:
                            poll = Poll(
                                id=0,
                                question=poll_question,
                                answers=[PollAnswer(text=opt, option=bytes([i])) for i, opt in enumerate(poll_options)]
                            )
                            await client.send_message(peer, file=poll)
                        else:
                            results[chat_id] = False
                            continue
                    elif media_type == 'location':
                        if lat is not None and lon is not None:
                            await client.send_message(peer, file=InputGeoPoint(lat, lon))
                        else:
                            results[chat_id] = False
                            continue
                    elif media_type == 'contact':
                        if contact_phone and contact_first_name:
                            contact = InputPhoneContact(client_id=0, phone=contact_phone, first_name=contact_first_name, last_name=contact_last_name or "")
                            await client.send_message(peer, file=contact)
                        else:
                            results[chat_id] = False
                            continue
                    else:
                        results[chat_id] = False
                        continue
                    
                    results[chat_id] = True
                    await asyncio.sleep(delay)
                except FloodWaitError as e:
                    print(f"FloodWait for {chat_id}: waiting {e.seconds} seconds")
                    await asyncio.sleep(e.seconds)
                    # Повторяем попытку после ожидания
                    try:
                        if media_type == 'text':
                            await client.send_message(peer, message_text)
                        elif media_type in ['photo', 'video', 'audio', 'document']:
                            if media_path and os.path.exists(media_path):
                                await client.send_file(peer, media_path, caption=message_text)
                            else:
                                results[chat_id] = False
                                continue
                        elif media_type == 'poll':
                            if poll_question and poll_options:
                                poll = Poll(
                                    id=0,
                                    question=poll_question,
                                    answers=[PollAnswer(text=opt, option=bytes([i])) for i, opt in enumerate(poll_options)]
                                )
                                await client.send_message(peer, file=poll)
                            else:
                                results[chat_id] = False
                                continue
                        elif media_type == 'location':
                            if lat is not None and lon is not None:
                                await client.send_message(peer, file=InputGeoPoint(lat, lon))
                            else:
                                results[chat_id] = False
                                continue
                        elif media_type == 'contact':
                            if contact_phone and contact_first_name:
                                contact = InputPhoneContact(client_id=0, phone=contact_phone, first_name=contact_first_name, last_name=contact_last_name or "")
                                await client.send_message(peer, file=contact)
                            else:
                                results[chat_id] = False
                                continue
                        else:
                            results[chat_id] = False
                            continue
                        results[chat_id] = True
                    except Exception as retry_e:
                        print(f"Broadcast error after retry for {chat_id}: {retry_e}")
                        results[chat_id] = False
                except Exception as e:
                    print(f"Broadcast error for {chat_id}: {e}")
                    results[chat_id] = False
        
        return results
    except Exception as e:
        print(f"Broadcast error: {e}")
        return {chat_id: False for chat_id in chat_ids}
