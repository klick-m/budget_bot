#!/usr/bin/env python3
"""
Скрипт для добавления пользователя в базу данных budget_bot
Используется для решения проблемы с авторизацией, когда пользователь не может использовать бота
"""

import asyncio
import sys
from services.repository import TransactionRepository
from services.auth_service import AuthService


async def add_user_to_db(telegram_id: int, username: str = None, role: str = "user", monthly_limit: float = 0.0):
    """
    Добавляет пользователя в таблицу users базы данных
    """
    print(f"Добавляем пользователя в базу данных...")
    print(f"Telegram ID: {telegram_id}")
    print(f"Username: {username}")
    print(f"Role: {role}")
    print(f"Monthly limit: {monthly_limit}")
    
    # Создаем репозиторий и инициализируем базу данных
    repo = TransactionRepository()
    await repo.init_db()
    
    # Создаем сервис авторизации
    auth_service = AuthService(repo)
    
    try:
        # Пытаемся создать пользователя
        user = await auth_service.create_user(
            telegram_id=telegram_id,
            username=username,
            role=role,
            monthly_limit=monthly_limit
        )
        
        print(f"✅ Пользователь успешно добавлен:")
        print(f"   ID: {user.id}")
        print(f"   Telegram ID: {user.telegram_id}")
        print(f"   Username: {user.username}")
        print(f"   Role: {user.role}")
        print(f"   Monthly limit: {user.monthly_limit}")
        
        return True
        
    except ValueError as e:
        print(f"❌ Ошибка: {e}")
        print("Пользователь с таким telegram_id уже существует в базе данных.")
        return False
    except Exception as e:
        print(f"❌ Произошла ошибка при добавлении пользователя: {e}")
        return False
    finally:
        await repo.close()


async def check_user_exists(telegram_id: int):
    """
    Проверяет, существует ли пользователь в базе данных
    """
    repo = TransactionRepository()
    await repo.init_db()
    
    auth_service = AuthService(repo)
    
    user = await auth_service.get_user_by_telegram_id(telegram_id)
    
    await repo.close()
    
    return user is not None


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Использование: python add_user.py <telegram_id> [username]")
        print("Пример: python add_user.py 123456789 myusername")
        print("Пример: python add_user.py 123456789")
        sys.exit(1)
    
    telegram_id = int(sys.argv[1])
    username = sys.argv[2] if len(sys.argv) > 2 else None
    
    print("=" * 60)
    print("СКРИПТ ДОБАВЛЕНИЯ ПОЛЬЗОВАТЕЛЯ В БАЗУ ДАННЫХ BUDGET_BOT")
    print("=" * 60)
    
    # Проверяем, существует ли уже пользователь
    user_exists = asyncio.run(check_user_exists(telegram_id))
    
    if user_exists:
        print(f"⚠️  Пользователь с telegram_id {telegram_id} уже существует в базе данных!")
        print("Если вы хотите обновить данные пользователя, используйте соответствующий скрипт.")
        sys.exit(0)
    
    # Добавляем пользователя
    success = asyncio.run(add_user_to_db(telegram_id, username))
    
    print("=" * 60)
    if success:
        print("✅ Скрипт выполнен успешно!")
        print("Теперь вы можете использовать бота - ваш telegram_id зарегистрирован в системе.")
    else:
        print("❌ Скрипт завершен с ошибками!")
    print("=" * 60)