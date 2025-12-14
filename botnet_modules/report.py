import asyncio
import os
import toml
from telethon import TelegramClient, functions, types

_config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.toml")
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


async def send_report(acc_session: str, post_ids: list[int], reason_num: int, comment: str, channel) -> bool:
    """Асинхронно отправляет репорт с поддержкой многошагового процесса"""
    if reason_num < 0 or reason_num >= len(REASONS):
        return False
    
    report_success = False
    
    try:
        # acc_session может быть полным путем или именем файла
        # Telethon ожидает путь БЕЗ расширения .session
        # Нормализуем путь (убираем обратные слэши, двойные слэши и т.д.)
        normalized_path = os.path.normpath(acc_session)
        
        # Убираем .session если есть
        if normalized_path.endswith('.session'):
            session_path = normalized_path[:-8]  # Убираем .session
        else:
            session_path = normalized_path
        
        async with TelegramClient(session_path, api_id, api_hash) as client:
            if not await client.is_user_authorized():
                return False
            
            try:
                if isinstance(channel, str):
                    peer_entity = await client.get_entity(channel)
                else:
                    peer_entity = channel
            except Exception as e:
                print(f"Report error: Failed to get entity: {e}")
                return False
            
            # Получаем объект причины репорта
            reason_obj = REASONS[reason_num]
            
            # Убеждаемся, что message не пустой
            full_message = comment if comment else " "

            # Отправляем репорт - используем только reason (без option)
            # В новых версиях Telethon используется reason напрямую
            try:
                result = await client(
                    functions.messages.ReportRequest(
                        peer=peer_entity,
                        id=post_ids,
                        reason=reason_obj,
                        message=full_message
                    )
                )
                
                if result:
                    report_success = True
            except Exception as e:
                print(f"Report error: {e}")
                return False
        
        return report_success
    except Exception as e:
        print(f"Report error: {e}")
        return False

