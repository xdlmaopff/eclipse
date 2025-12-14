import asyncio
import os
import toml
from telethon import TelegramClient, functions, events
from typing import Optional

_config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.toml")
with open(_config_path, "r", encoding="utf-8") as f:
    config = toml.load(f)

api_id = config["authorization"]["api_id"]
api_hash = config["authorization"]["api_hash"]


async def join_chat(acc_session: str, chat_link: str, has_captcha: bool = False) -> bool:
    """Асинхронно присоединяется к чату/каналу"""
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
            
            try:
                # Обработка разных форматов ссылок
                if chat_link.startswith('@'):
                    chat = await client.get_entity(chat_link[1:])
                    await client(functions.channels.JoinChannelRequest(chat))
                elif chat_link.startswith('https://t.me/'):
                    chat_username = chat_link[13:]
                    if chat_username.startswith('+') or chat_username.startswith('joinchat/'):
                        # Приватная ссылка-приглашение
                        if chat_username.startswith('+'):
                            hash_str = chat_username[1:]
                        else:  # joinchat/
                            hash_str = chat_username[9:]
                        await client(functions.messages.ImportChatInviteRequest(hash=hash_str))
                    else:
                        # Публичный канал/группа
                        chat = await client.get_entity(chat_username)
                        await client(functions.channels.JoinChannelRequest(chat))
                
                # Обработка капчи, если требуется
                if has_captcha:
                    # Ждем сообщение с капчей (таймаут 10 секунд)
                    try:
                        @client.on(events.NewMessage)
                        async def captcha_handler(event):
                            if hasattr(event, 'reply_markup') and event.reply_markup:
                                kb = event.reply_markup
                                if hasattr(kb, 'rows') and kb.rows:
                                    for row in kb.rows:
                                        if hasattr(row, 'buttons') and row.buttons:
                                            try:
                                                await event.click(0)
                                                return True
                                            except:
                                                pass
                            return False
                        
                        # Ждем капчу максимум 10 секунд
                        await asyncio.wait_for(
                            asyncio.sleep(0.1),  # Просто ждем немного
                            timeout=10.0
                        )
                    except asyncio.TimeoutError:
                        pass  # Капча не пришла или уже обработана
                
                return True
            except Exception as e:
                print(f"Join error: {e}")
                return False
    except Exception as e:
        print(f"Join error: {e}")
        return False
