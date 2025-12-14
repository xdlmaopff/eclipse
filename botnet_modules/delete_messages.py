import asyncio
import os
import sys
from telethon import TelegramClient, functions
import toml

async def delete_messages(session_path: str, chat_id: str, message_ids: list):
    """Delete own messages"""
    try:
        config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.toml")
        with open(config_path) as f:
            config = toml.load(f)
        api_id = config["authorization"]["api_id"]
        api_hash = config["authorization"]["api_hash"]

        client = TelegramClient(session_path.replace(".session", ""), api_id, api_hash)
        await client.connect()

        if not await client.is_user_authorized():
            return False

        # Delete messages
        await client.delete_messages(chat_id, message_ids)

        await client.disconnect()
        return True
    except Exception as e:
        print(f"Delete messages error: {e}")
        return False