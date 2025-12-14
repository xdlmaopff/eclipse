# Модули
from customtkinter import *
from PIL import Image
import os
from raidfunctions import register, tgraid, start_spam
import toml
import asyncio
from telethon import TelegramClient
from telethon.tl.functions.messages import ReportRequest
from telethon.tl.types import InputReportReasonSpam
from raidfunctions import report
from threading import Thread
from telethon import functions
import time
from tkinter import messagebox
import threading

# Загрузка конфигурации
with open("config.toml") as file:
    config = toml.load(file)

api_id = config["authorization"]["api_id"]
api_hash = config["authorization"]["api_hash"]

# Настройки главного окна
set_appearance_mode("dark")
set_default_color_theme("dark-blue")

root = CTk()
root.geometry("980x550")
root.title("LexaKRAIM")

# Количество аккаунтов и аккаунтов в спамблоке
acc_count = len(os.listdir("tgaccs"))
spamblock = len(os.listdir("spamblock"))

# --- Функции кнопок ---
def AddAccRoot(event=None):

    add_acc_window = CTkToplevel()
    add_acc_window.geometry("850x550")
    add_acc_window.title("Добавление аккаунта")

    CTkLabel(add_acc_window, text="Войти в аккаунт (Введите номер телефона)", font=("Arial", 15)).pack(pady=10)
    CTkLabel(add_acc_window, text="Аккаунт регистрируется/Авторизовывается только в консоли!", font=("Arial", 25)).pack(pady=10)
    CTkLabel(add_acc_window, text="Введите номер", font=("Arial", 25)).pack(pady=10)

    def ValueNumber():
        phone = player_name_entry.get()
        CTkLabel(add_acc_window, text=f"Номер = {phone}", font=("Arial", 20)).pack(pady=10)
        print(phone)
        # Запускаем регистрацию в отдельном потоке, чтобы не блокировать GUI
        def reg_thread():
            try:
                register.Register(phone, 1, None, None).regaccountreg()
            except Exception as e:
                print(f"Ошибка при регистрации: {e}")
        threading.Thread(target=reg_thread, daemon=True).start()

    player_name_entry = CTkEntry(add_acc_window)
    player_name_entry.pack(pady=20)
    CTkButton(add_acc_window, text="Подтвердить", command=ValueNumber).pack(pady=10)


def RaidSpamAcc(event=None):
    # Загрузка конфигурации
    with open("config.toml") as file:
        config = toml.load(file)
    raid_message = config["raid"]["message"]
    lang = config["locale"]["lang"]

    class Settings:
        def __init__(self, join_chat, username=""):
            self.join_chat = join_chat
            self.username = username

        def get_messages(self, msg_type):
            ms = ""
            if msg_type == 1:
                with open('args.txt', encoding='utf8') as a:
                    ms = a.read().split('\n')
                new_ms = [self.username + " " + m for m in ms if m]
                ms = new_ms
            elif msg_type == 2:
                ms = self.username + " " + raid_message
            return ms

        def start_spam(self, chat_id, spam_type, speed, msg_type, mentions, files=None):
            tg_accounts = [acc for acc in os.listdir('tgaccs') if acc.endswith(".session")]
            messages = self.get_messages(msg_type)
            for account in tg_accounts:
                print(f"Спам запущен с {account} аккаунта!")
                tgraid.RaidGroup(
                    session_name=account,
                    spam_type=spam_type,
                    files=files or [],
                    messages=messages,
                    chat_id=chat_id,
                    msg_tp=msg_type,
                    speed=speed,
                    mentions=mentions,
                ).start()

    # Окно настройки спам-атаки
    app = CTkToplevel()
    app.geometry("900x600")
    app.title("Спам-атака")

    CTkLabel(app, text="Настройка спам-атаки", font=("Arial", 30)).pack(pady=20)

    # Ввод ID чата
    CTkLabel(app, text="Введите ссылку чата:").pack(pady=10)
    chat_id_entry = CTkEntry(app, width=400)
    chat_id_entry.pack(pady=5)

    # Выбор типа спама
    CTkLabel(app, text="Выберите тип спама:").pack(pady=10)
    spam_type_var = StringVar(value="1")
    CTkRadioButton(app, text="1. Спам из args.txt", variable=spam_type_var, value="1").pack(pady=5)
    CTkRadioButton(app, text="2. Спам из config.toml", variable=spam_type_var, value="2").pack(pady=5)
    CTkRadioButton(app, text="3. Спам медиафайлами из raidfiles", variable=spam_type_var, value="3").pack(pady=5)

    # Выбор скорости спама
    CTkLabel(app, text="Введите скорость спама (мс):").pack(pady=10)
    speed_entry = CTkEntry(app, width=400)
    speed_entry.pack(pady=5)

    # Флаг упоминания пользователей
    mentions_var = BooleanVar(value=False)
    CTkCheckBox(app, text="Тег пользователей", variable=mentions_var).pack(pady=10)

    # Метка результата
    result_label = CTkLabel(app, text="", font=("Arial", 14))
    result_label.pack(pady=10)

    # Функция для запуска спама
    def start_spam_action():
        chat_id = chat_id_entry.get()
        spam_type = int(spam_type_var.get())
        speed = speed_entry.get()

        if not chat_id or not speed.isdigit():
            result_label.configure(text="Пожалуйста, заполните все поля корректно!", text_color="red")
            return

        mentions = mentions_var.get()
        result_label.configure(text="Спам выполняется...", text_color="green")

        try:
            files = os.listdir('raidfiles') if spam_type == 3 else None
            settings = Settings(join_chat=False)
            settings.start_spam(chat_id, spam_type, int(speed), spam_type, mentions, files)
            result_label.configure(text="Спамим", text_color="green")
        except Exception as e:
            result_label.configure(text=f"Ошибка: {e}", text_color="red")

    # Кнопка запуска
    CTkButton(app, text="Запустить рейд", command=start_spam_action).pack(pady=20)


# Функция захода / подписки
def JoinBot(event=None):
    join_window = CTkToplevel()
    join_window.geometry("850x550")
    join_window.title("Вход в группы")

    CTkLabel(join_window, text="Переключите раскладку на ENG для вставки (Cnrl+V)", font=("Arial", 24)).pack(pady=10)

    def create_captcha_radio_buttons():
        global captcha_var
        captcha_var = IntVar(value=0)
        CTkRadioButton(join_window, text="Есть капча", variable=captcha_var, value=1).pack(pady=5)
        CTkRadioButton(join_window, text="Нет капчи", variable=captcha_var, value=0).pack(pady=5)

    def JoinChatValue():
        link_to_chat = link_chat_entry.get()
        CTkLabel(join_window, text=f"Ссылка = {link_to_chat}", font=("Arial", 20)).pack(pady=10)
        print(link_to_chat)

        captcha = captcha_var.get()
        CTkLabel(join_window, text=f"Captcha = {captcha}", font=("Arial", 20)).pack(pady=10)
        print(captcha)

        for acc in accs:
            if acc.endswith(".session"):
                tgraid.ConfJoin(acc, link_to_chat, captcha).start()

    accs = [file for file in os.listdir("tgaccs") if file.endswith(".session")]
    CTkLabel(join_window, text="Введите ссылку на чат/канал:", font=("Arial", 16)).pack(pady=10)
    link_chat_entry = CTkEntry(join_window, width=500)
    link_chat_entry.pack(pady=10)
    CTkLabel(join_window, text="Выберите наличие капчи:", font=("Arial", 16)).pack(pady=10)
    create_captcha_radio_buttons()
    CTkButton(join_window, text="Подтвердить", command=JoinChatValue).pack(pady=10)

#Репорты
def Reports(event=None):
    lang = "ru"  # Установите нужный язык, например, 'ru' или 'en'
    global report_count
    report_count = 0
    def submit_report():
        def report_loop():
            global report_count
            try:
                delay = float(entry_delay.get().strip())
                if delay < 0:
                    raise ValueError("Задержка не может быть отрицательной!")
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                async def report_bulk():
                    while True:
                        msg_link = entry_link.get().strip().split("/")
                        if len(msg_link) < 5:
                            raise ValueError("Неверный формат ссылки!")
                        channel = msg_link[3]
                        post_id = msg_link[4]
                        # Убираем параметры запроса (всё после ?) из post_id
                        if "?" in post_id:
                            post_id = post_id.split("?")[0]
                        if msg_link[3] == "c":
                            # Убираем параметры запроса из channel ID
                            channel_id_str = msg_link[4]
                            if "?" in channel_id_str:
                                channel_id_str = channel_id_str.split("?")[0]
                            channel = (int(channel_id_str) + 1000000000000) * -1
                            post_id = msg_link[5]
                            # Убираем параметры запроса из post_id для приватных каналов
                            if "?" in post_id:
                                post_id = post_id.split("?")[0]
                        post_ids = [int(post_id)]
                        # Получаем выбранную причину (значение от 1 до 7, преобразуем в индекс 0-6)
                        selected_reason = reasons_var.get()
                        if selected_reason < 1 or selected_reason > 7:
                            raise ValueError("Неверно выбрана причина репорта!")
                        reason_num = selected_reason - 1
                        comment = comment_textbox.get("1.0", "end").strip()
                        
                        # Получаем список аккаунтов с .session расширением
                        accs = [acc for acc in os.listdir('tgaccs') if acc.endswith('.session')]
                        if not accs:
                            print("Не найдено аккаунтов с расширением .session")
                            await asyncio.sleep(delay)
                            continue
                        
                        tasks = []
                        for acc in accs:
                            tasks.append(report.send_report(acc, post_ids, reason_num, comment, channel))
                        results = await asyncio.gather(*tasks, return_exceptions=True)
                        # Фиксируем, если хотя бы 1 успешная отправка
                        success_count = sum(1 for r in results if r is True)
                        if success_count > 0:
                            report_count += success_count
                            # Проверяем, что окно еще существует перед обновлением
                            try:
                                if reports_window.winfo_exists():
                                    update_report_count()
                            except:
                                pass  # Окно закрыто, игнорируем обновление
                        await asyncio.sleep(delay)
                try:
                    loop.run_until_complete(report_bulk())
                except Exception as e:
                    messagebox.showerror("Ошибка", str(e))
                finally:
                    loop.close()
            except Exception as e:
                messagebox.showerror("Ошибка", str(e))
        thread = threading.Thread(target=report_loop, daemon=True)
        thread.start()
    def update_report_count():
        global report_count
        try:
            if reports_window.winfo_exists():
                label_report_count.configure(text=f"Отправлено репортов: {report_count}")
        except:
            pass  # Окно закрыто, игнорируем обновление
    reports_window = CTkToplevel()
    reports_window.geometry("850x750")
    reports_window.title("Репортинг (Жалобы)")
    CTkLabel(reports_window, text="Введите ссылку на пост или сообщение:", font=("Arial", 14)).pack(pady=10)
    entry_link = CTkEntry(reports_window, width=500)
    entry_link.pack(pady=10)
    CTkLabel(reports_window, text="Выберите причину для репорта:", font=("Arial", 14)).pack(pady=10)
    reasons_var = IntVar(value=1)
    reasons = [
        "ЦП",
        "Ворованный контент",
        "Фейковый аккаунт или канал",
        "Порнография",
        "Спам",
        "Жестокость",
        "Другое"
    ] if lang == "ru" else [
        "CP",
        "Stolen content",
        "Fake account or channel",
        "Pornography",
        "Spam",
        "Violence",
        "Other"
    ]
    for idx, reason in enumerate(reasons, start=1):
        CTkRadioButton(reports_window, text=reason, variable=reasons_var, value=idx).pack(anchor="w", padx=50)
    CTkLabel(reports_window, text="Комментарий к репорту:", font=("Arial", 14)).pack(pady=10)
    comment_textbox = CTkTextbox(reports_window, width=500, height=100)
    comment_textbox.pack(pady=10)
    CTkLabel(reports_window, text="Задержка (в секундах):", font=("Arial", 14)).pack(pady=10)
    entry_delay = CTkEntry(reports_window, width=200)
    entry_delay.insert(0, "1.0")
    entry_delay.pack(pady=10)
    label_report_count = CTkLabel(reports_window, text="Отправлено репортов: 0", font=("Arial", 14))
    label_report_count.pack(pady=10)
    send_button = CTkButton(reports_window, text="Подтвердить и начать автоматическую отправку", command=submit_report)
    send_button.pack(pady=20)

def PostVote(event=None):
    # Создание окна
    post_vote_window = CTkToplevel()
    post_vote_window.geometry("850x550")
    post_vote_window.title("Накрутка голосов")

    # Заголовок
    CTkLabel(post_vote_window, text="Накрутка голосов", font=("Arial", 24)).pack(pady=20)

    # Виджеты для ввода данных
    link_label = CTkLabel(post_vote_window, text="Введите ссылку на опрос:")
    link_label.pack(pady=10)
    link_entry = CTkEntry(post_vote_window, width=600)
    link_entry.pack(pady=5)

    variants_label = CTkLabel(post_vote_window, text="Введите варианты (например, 1,2 и тд.):")
    variants_label.pack(pady=10)
    variants_entry = CTkEntry(post_vote_window, width=600)
    variants_entry.pack(pady=5)

    # Метка для вывода результата
    result_label = CTkLabel(post_vote_window, text="", font=("Arial", 16))
    result_label.pack(pady=20)

    # Функция для запуска голосования
    def start_voting():
        poll_link = link_entry.get()
        input_variants = variants_entry.get()

        # Путь к папке с сессиями
        tgaccs_folder = "tgaccs"
        try:
            # Список всех аккаунтов с проверкой на ".session"
            accs = [acc for acc in os.listdir(tgaccs_folder) if acc.endswith(".session")]
        except FileNotFoundError:
            result_label.configure(text="Папка tgaccs не найдена!")
            return

        if poll_link and input_variants and accs:
            result_label.configure(text="Накрутка выполняется...")
            try:
                # Разбор ссылки
                variants = [str(int(variant) - 1) for variant in input_variants.split(",")]
                private = False
                channel = poll_link.split('/')[3]
                x = poll_link.split('/')
                if channel == "c":
                    private = True
                    poll_id_str = x[5]
                    # Убираем параметры запроса (всё после ?)
                    if "?" in poll_id_str:
                        poll_id_str = poll_id_str.split("?")[0]
                    poll_id = int(poll_id_str)
                else:
                    poll_id_str = x[4]
                    # Убираем параметры запроса (всё после ?)
                    if "?" in poll_id_str:
                        poll_id_str = poll_id_str.split("?")[0]
                    poll_id = int(poll_id_str)

                if private:
                    channel_str = poll_link.split('/')[4]
                    # Убираем параметры запроса (всё после ?)
                    if "?" in channel_str:
                        channel_str = channel_str.split("?")[0]
                    channel_id = -1000000000000 - int(channel_str)
                else:
                    channel_id = channel

                # Запуск голосования для каждого аккаунта
                for acc in accs:
                    try:
                        # Инициализация клиента для аккаунта
                        client = TelegramClient(f"{tgaccs_folder}/{acc.split('.')[0]}", api_id, api_hash)
                        client.connect()
                        if not client.is_user_authorized():
                            print(f"Аккаунт {acc} не авторизован!")
                            continue

                        # Отправка голоса
                        client(functions.messages.SendVoteRequest(
                            peer=channel_id,
                            msg_id=poll_id,
                            options=variants
                        ))
                        print(f"Голос отправлен с аккаунта {acc}")
                    except Exception as e:
                        print(f"Ошибка при голосовании с аккаунтом {acc}: {e}")
                    finally:
                        client.disconnect()

                result_label.configure(text="Голосование завершено!")
            except Exception as e:
                result_label.configure(text=f"Ошибка: {e}")
        else:
            result_label.configure(text="Заполните все поля.")

    # Кнопка для начала голосования
    vote_button = CTkButton(post_vote_window, text="Запуск накрутки", command=start_voting)
    vote_button.pack(pady=20)




def TestFun(event=None):
    snos_window = CTkToplevel()
    snos_window.geometry("850x550")
    snos_window.title("Тестовая функция")
    CTkLabel(snos_window, text="Снос через сессии", font=("Arial", 24)).pack(pady=20)
    CTkLabel(snos_window, text="Вставьте ссылку на сообщение (через ENG раскладку)", font=("Arial", 20)).pack(pady=20)

    # Асинхронная функция для сноса через сессии
    async def snos_session():
        message_link = snos_method.get()
        CTkLabel(snos_window, text=f"Ссылка = {message_link}", font=("Arial", 20)).pack(pady=10)
        print(message_link)
        parts = message_link.split("/")
        chat_username = parts[-2]
        message_id_str = parts[-1]
        # Убираем параметры запроса (всё после ?)
        if "?" in message_id_str:
            message_id_str = message_id_str.split("?")[0]
        message_id = int(message_id_str)

        session_folder = "tgaccs"
        session_files = [f for f in os.listdir(session_folder) if f.endswith(".session")]
        if not session_files:
            print("Ошибка: Нет доступных сессий.")
            return
        
        for session in session_files:
            session_name = os.path.splitext(session)[0]
            try:
                client = TelegramClient(os.path.join(session_folder, session_name), api_id, api_hash)
                await client.connect()

                if not await client.is_user_authorized():
                    print(f"Сессия {session_name} не авторизована.")
                    continue

                # Отправка жалобы на сообщение
                reason_obj = InputReportReasonSpam()
                await client(ReportRequest(
                    peer=chat_username,
                    id=[message_id],
                    option=reason_obj.__bytes__(),
                    message="Спам"
                ))
                print(f"Жалоба успешно отправлена с сессии: {session_name}")
            except Exception as e:
                print(f"Ошибка в сессии {session_name}: {e}")
            finally:
                await client.disconnect()

    # Поле для ввода ссылки
    snos_method = CTkEntry(snos_window, width=500)
    snos_method.pack(pady=10)

    # Функция для вызова асинхронного кода
    def TestAsyFun():
        # Создаем новый event loop в отдельном потоке, чтобы избежать конфликтов
        def run_async():
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(snos_session())
            except Exception as e:
                print(f"Ошибка: {e}")
            finally:
                loop.close()
        threading.Thread(target=run_async, daemon=True).start()

    # Кнопка для подтверждения
    CTkButton(snos_window, text="Подтвердить", command=TestAsyFun).pack(pady=10)

# --- Виджеты ---
# Заголовки
CTkLabel(root, text="LexaKRAIM", font=("Arial", 50)).grid(row=0, column=0, padx=20, pady=10, sticky="w")
#CTkLabel(root, text="-----------------by eski-----------------", font=("Arial", 14)).grid(row=1, column=0, padx=20, sticky="w")

# Рамка для функций (увеличена в 2 раза)
frame_functions = CTkFrame(root, border_width=3, border_color="black", width=600, height=1200)
frame_functions.grid(row=2, column=0, padx=20, pady=10, sticky="n")

# Заголовок для функций
CTkLabel(frame_functions, text="Функции", font=("Arial", 30)).pack(pady=10)


# Задание одинакового размера всем кнопкам
button_width = 500
button_height = 40
# Кнопки
AddAccBut = CTkButton(frame_functions, text="Добавить аккаунт", command=AddAccRoot, width=button_width, height=button_height)
RaidSpamBut = CTkButton(frame_functions, text="Рейд (спам-атака аккаунтами)", command=RaidSpamAcc, width=button_width, height=button_height)
JoinBotBut = CTkButton(frame_functions, text="Войти в группу/канал", command=JoinBot, width=button_width, height=button_height)
ReportsBut = CTkButton(frame_functions, text="Репортинг (Жалобы)", command=Reports, width=button_width, height=button_height)
PostVoteBut = CTkButton(frame_functions, text="Накрутка голосов", command=PostVote, width=button_width, height=button_height)
TestFunBut = CTkButton(frame_functions, text="Снос через сессии", command=TestFun, width=button_width, height=button_height)


AddAccBut.pack(pady=10, padx=20)
RaidSpamBut.pack(pady=10, padx=20)
JoinBotBut.pack(pady=10, padx=20)
ReportsBut.pack(pady=10, padx=20)
PostVoteBut.pack(pady=10, padx=20)
TestFunBut.pack(pady=10, padx=20)

# Рамка для информации (увеличена в 2 раза, фиксированные размеры)
frame_info = CTkFrame(root, border_width=3, border_color="black", width=400, height=800)  # Увеличенные фиксированные размеры
frame_info.grid(row=2, column=2, padx=20, pady=10, sticky="nw")  # Размещаем по правому краю

# Внутренний контейнер для отступов текста
inner_info_frame = CTkFrame(frame_info, fg_color="transparent")  # Прозрачный фон
inner_info_frame.pack(padx=20, pady=20, fill="both", expand=True)  # Отступы внутри рамки

# Заголовок для информации
info_title = CTkLabel(inner_info_frame, text="Информация", font=("Arial", 30))
info_title.pack(pady=10,padx=20)

# Информация о количестве аккаунтов
info_active_accounts = CTkLabel(inner_info_frame, text=f"Активные аккаунты : {acc_count}", font=("Arial", 27))
info_active_accounts.pack(pady=5,padx=20,anchor="w")


info_spamblock = CTkLabel(inner_info_frame, text=f"Спамблок : {spamblock}", font=("Arial", 27))
nonestr = CTkLabel(inner_info_frame, text=f"", font=("Arial", 30))
info_spamblock.pack(pady=5,padx=20,anchor="w")
nonestr.pack(pady=103,padx=20,anchor="w")

info_channel = CTkLabel(inner_info_frame, text="https://t.me/LexaKRAIM", font=("Arial", 25)).pack()

# Запуск
root.mainloop()
