import asyncio
import os
import random
import toml
from telethon import TelegramClient, functions
from typing import List, Optional

_config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.toml")
with open(_config_path, "r", encoding="utf-8") as f:
    config = toml.load(f)

api_id = config["authorization"]["api_id"]
api_hash = config["authorization"]["api_hash"]
raid_message = config["raid"].get("message", "")


async def send_spam(
    acc_session: str,
    chat_id: str,
    spam_type: int,
    speed: int,
    mentions: bool = False,
    messages: Optional[List[str]] = None
) -> bool:
    """Асинхронно отправляет спам в чат/канал"""
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
            
            if spam_type == 1:  # Text from args.txt
                args_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "args.txt")
                if os.path.exists(args_path):
                    with open(args_path, 'r', encoding='utf-8') as f:
                        msg_list = [line.strip() for line in f if line.strip()]
                else:
                    msg_list = [raid_message]
                
                for msg in msg_list[:10]:  # Limit to 10 messages
                    try:
                        if mentions:
                            await client.send_message(peer, msg, parse_mode='md')
                        else:
                            await client.send_message(peer, msg)
                        await asyncio.sleep(speed / 1000.0)
                    except Exception as e:
                        print(f"Spam error: {e}")
                        continue
            
            elif spam_type == 2:  # Text from config
                msg = raid_message
                try:
                    await client.send_message(peer, msg)
                except Exception as e:
                    print(f"Spam error: {e}")
                    return False
            
            elif spam_type == 3:  # Media files
                raidfiles_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "raidfiles")
                if os.path.exists(raidfiles_path):
                    files = [f for f in os.listdir(raidfiles_path) if os.path.isfile(os.path.join(raidfiles_path, f))]
                    if files:
                        file_path = os.path.join(raidfiles_path, random.choice(files))
                        try:
                            await client.send_file(peer, file_path)
                            await asyncio.sleep(speed / 1000.0)
                        except Exception as e:
                            print(f"Media spam error: {e}")
                            return False
        
        return True
    except Exception as e:
        print(f"Spam error: {e}")
        return False

