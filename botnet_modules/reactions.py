import asyncio
import os
import sys
from telethon import TelegramClient, functions
import toml

async def add_reactions(session_path: str, chat_id: str, message_ids: list, reaction: str):
    """Add reactions to messages"""
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

        # Add reactions
        for msg_id in message_ids:
            await client(functions.messages.SendReactionRequest(
                peer=chat_id,
                msg_id=msg_id,
                reaction=reaction
            ))

        await client.disconnect()
        return True
    except Exception as e:
        print(f"Reaction error: {e}")
        return False