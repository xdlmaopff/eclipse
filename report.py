import asyncio
import os
import toml
from telethon import TelegramClient, functions, types

# ====== CONFIG ======
_config_path = os.path.join(os.path.dirname(__file__), "config.toml")
with open(_config_path, "r", encoding="utf-8") as f:
    config = toml.load(f)

api_id = config["authorization"]["api_id"]
api_hash = config["authorization"]["api_hash"]
lang = config["locale"].get("lang", "ru")

REASONS = [
    types.InputReportReasonChildAbuse(),
    types.InputReportReasonCopyright(),
    types.InputReportReasonFake(),
    types.InputReportReasonPornography(),
    types.InputReportReasonSpam(),
    types.InputReportReasonViolence(),
    types.InputReportReasonOther()
]


async def send_report(
    session_path: str,
    post_ids: list[int],
    reason_num: int,
    comment: str,
    channel: str
) -> bool:
    """
    Асинхронно отправляет репорт с указанного аккаунта.
    
    :param session_path: Полный путь к .session файлу
    :param post_ids: Список id сообщений
    :param reason_num: Индекс причины из REASONS (0-6)
    :param comment: Сопроводительный текст
    :param channel: username или id канала/чата
    :return: True если репорт успешно отправлен, False иначе
    """
    if reason_num < 0 or reason_num >= len(REASONS):
        return False
    
    base_name = os.path.splitext(os.path.basename(session_path))[0]
    
    try:
        async with TelegramClient(session_path, api_id, api_hash) as client:
            if not await client.is_user_authorized():
                return False
            
            try:
                if isinstance(channel, str):
                    peer_entity = await client.get_entity(channel)
                else:
                    peer_entity = channel
            except Exception:
                return False
            
            reason_obj = REASONS[reason_num]
            option_bytes = reason_obj.__bytes__()
            full_message = comment if comment else " "
            
            result = await client(
                functions.messages.ReportRequest(
                    peer=peer_entity,
                    id=post_ids,
                    option=option_bytes,
                    message=full_message
                )
            )
            
            return bool(result)
    except Exception:
        return False

