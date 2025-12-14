import asyncio
import os
import toml
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError, PhoneCodeInvalidError, PhoneNumberInvalidError

_config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.toml")
with open(_config_path, "r", encoding="utf-8") as f:
    config = toml.load(f)

api_id = config["authorization"]["api_id"]
api_hash = config["authorization"]["api_hash"]


async def send_code_request(phone: str, session_name: str) -> dict:
    """
    Отправляет код подтверждения на номер телефона
    Возвращает: {"success": True/False, "phone_code_hash": str, "error": str}
    """
    client = None
    try:
        # Создаем временную сессию (Telethon ожидает путь БЕЗ .session)
        session_path = os.path.join("user_sessions", "temp", session_name)
        os.makedirs(os.path.dirname(session_path), exist_ok=True)
        
        client = TelegramClient(session_path, api_id, api_hash)
        await client.connect()
        
        # Отправляем код
        result = await client.send_code_request(phone)
        
        # Закрываем клиент, но сессия уже сохранена
        await client.disconnect()
        
        return {
            "success": True,
            "phone_code_hash": result.phone_code_hash
        }
    except PhoneNumberInvalidError:
        if client:
            await client.disconnect()
        return {"success": False, "error": "Invalid phone number"}
    except Exception as e:
        if client:
            await client.disconnect()
        return {"success": False, "error": str(e)}


async def sign_in_with_code(phone: str, code: str, phone_code_hash: str, session_name: str, user_id: str) -> dict:
    """
    Авторизуется с кодом подтверждения
    Возвращает: {"success": True/False, "requires_2fa": bool, "session_path": str, "error": str}
    """
    try:
        temp_session_path = os.path.join("user_sessions", "temp", session_name)
        final_session_path = os.path.join("user_sessions", user_id, session_name)
        os.makedirs(os.path.dirname(final_session_path), exist_ok=True)
        
        client = TelegramClient(temp_session_path, api_id, api_hash)
        await client.connect()
        
        try:
            # Пытаемся войти с кодом
            await client.sign_in(phone, code, phone_code_hash=phone_code_hash)
            
            # Если успешно, перемещаем сессию в финальную папку
            await client.disconnect()
            
            if os.path.exists(temp_session_path + ".session"):
                os.rename(temp_session_path + ".session", final_session_path + ".session")
            # Также перемещаем .session-journal если есть
            if os.path.exists(temp_session_path + ".session-journal"):
                if os.path.exists(final_session_path + ".session-journal"):
                    os.remove(final_session_path + ".session-journal")
                os.rename(temp_session_path + ".session-journal", final_session_path + ".session-journal")
            
            return {
                "success": True,
                "requires_2fa": False,
                "session_path": final_session_path + ".session"
            }
        except SessionPasswordNeededError:
            # Требуется 2FA пароль - не закрываем клиент
            return {
                "success": True,
                "requires_2fa": True,
                "temp_session_path": temp_session_path
            }
        except PhoneCodeInvalidError:
            await client.disconnect()
            return {"success": False, "error": "Invalid code"}
        except Exception as e:
            await client.disconnect()
            raise e
    except Exception as e:
        return {"success": False, "error": str(e)}


async def sign_in_with_2fa(phone: str, password: str, temp_session_path: str, session_name: str, user_id: str) -> dict:
    """
    Завершает авторизацию с 2FA паролем
    Возвращает: {"success": True/False, "session_path": str, "error": str}
    """
    try:
        final_session_path = os.path.join("user_sessions", user_id, session_name)
        os.makedirs(os.path.dirname(final_session_path), exist_ok=True)
        
        client = TelegramClient(temp_session_path, api_id, api_hash)
        await client.connect()
        
        try:
            # Вводим 2FA пароль
            await client.sign_in(password=password)
            
            # Закрываем клиент перед перемещением файлов
            await client.disconnect()
            
            # Перемещаем сессию в финальную папку
            if os.path.exists(temp_session_path + ".session"):
                os.rename(temp_session_path + ".session", final_session_path + ".session")
            if os.path.exists(temp_session_path + ".session-journal"):
                if os.path.exists(final_session_path + ".session-journal"):
                    os.remove(final_session_path + ".session-journal")
                os.rename(temp_session_path + ".session-journal", final_session_path + ".session-journal")
            
            # Удаляем временную папку
            try:
                os.rmdir(os.path.dirname(temp_session_path))
            except:
                pass
            
            return {
                "success": True,
                "session_path": final_session_path + ".session"
            }
        except Exception as e:
            await client.disconnect()
            raise e
    except Exception as e:
        return {"success": False, "error": str(e)}
