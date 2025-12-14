import asyncio
import os
import toml
from telethon import TelegramClient, functions, types

# ====== CONFIG ======
_config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.toml")
with open(_config_path, "r", encoding="utf-8") as f:
    config = toml.load(f)

api_id = config["authorization"]["api_id"]
api_hash = config["authorization"]["api_hash"]
lang = config["locale"].get("lang", "ru")


async def send_report(
    acc_session: str,
    post_ids: list[int],
    reason_num: int,
    comment: str,
    channel
) -> bool:
    """
    Асинхронно отправляет репорт (полная совместимость с test3.py + актуальный динамический flow).
    """
    report_success = False

    base_acc = acc_session[:-8] if acc_session.endswith(".session") else acc_session
    session_path = os.path.join("tgaccs", base_acc)

    try:
        async with TelegramClient(session_path, api_id, api_hash) as client:
            if not await client.is_user_authorized():
                print(f"\033[91m❌ Сессия {base_acc} не авторизована\033[0m")
                return False

            # Получаем entity
            try:
                if isinstance(channel, str):
                    peer_entity = await client.get_entity(channel)
                else:
                    peer_entity = channel
            except Exception as e:
                print(f"\033[91m[ERROR] Не удалось получить entity: {e}\033[0m")
                return False

            full_message = comment if comment else " "

            # Начинаем с пустой опции (bytes)
            current_option_bytes = b''

            result = await client(functions.messages.ReportRequest(
                peer=peer_entity,
                id=post_ids,
                option=current_option_bytes,
                message=full_message
            ))

            while True:
                if isinstance(result, types.ReportResultReported):
                    msg = f"Жалоба успешно отправлена с аккаунта {base_acc}!" if lang == "ru" else f"Report sent from {base_acc}!"
                    print(f"\033[92m{msg}\033[0m")
                    report_success = True
                    break

                elif isinstance(result, types.ReportResultChooseOption):
                    if not result.options:
                        print(f"\033[91m[ERROR] {base_acc}: Нет доступных опций для жалобы\033[0m")
                        break

                    # Берём .option (это bytes) из первого MessageReportOption
                    chosen_option_obj = result.options[0]
                    current_option_bytes = chosen_option_obj.option

                    # Здесь можно добавить выбор по chosen_option_obj.text (например, искать "spam")

                elif isinstance(result, types.ReportResultAddComment):
                    # Если требуется комментарий — опция может быть обновлена
                    if result.option:
                        current_option_bytes = result.option.option or current_option_bytes

                else:
                    print(f"\033[91m[ERROR] {base_acc}: Неожиданный ответ: {type(result)}\033[0m")
                    break

                # Отправляем следующий шаг
                result = await client(functions.messages.ReportRequest(
                    peer=peer_entity,
                    id=post_ids,
                    option=current_option_bytes,
                    message=full_message
                ))

    except Exception as error:
        print(f"\033[91m[ERROR] {base_acc}: {error}\033[0m")

    return report_success