"""Скрипт для добавления столбцов total_reports, successful_reports, failed_reports в таблицу task"""
import sqlite3
import os

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./botnet.db")
db_path = DATABASE_URL.replace("sqlite:///", "")

if not os.path.exists(db_path):
    print(f"База данных {db_path} не найдена!")
    exit(1)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

try:
    # Проверяем наличие столбцов
    cursor.execute("PRAGMA table_info(task)")
    columns = [column[1] for column in cursor.fetchall()]
    
    columns_to_add = []
    if "total_reports" not in columns:
        columns_to_add.append("total_reports")
    if "successful_reports" not in columns:
        columns_to_add.append("successful_reports")
    if "failed_reports" not in columns:
        columns_to_add.append("failed_reports")
    
    if not columns_to_add:
        print("Все необходимые столбцы уже существуют в таблице task")
    else:
        for col in columns_to_add:
            cursor.execute(f"ALTER TABLE task ADD COLUMN {col} INTEGER DEFAULT 0")
            print(f"✓ Столбец {col} успешно добавлен в таблицу task")
        conn.commit()
        
except Exception as e:
    print(f"Ошибка при миграции: {e}")
finally:
    conn.close()