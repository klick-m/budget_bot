#!/usr/bin/env python3
"""
Скрипт для обновления роли пользователя в базе данных budget_bot
Используется для изменения роли существующего пользователя (например, сделать администратором)
"""

import asyncio
import sys
from services.repository import TransactionRepository
from services.auth_service import AuthService


async def update_user_role_in_db(telegram_id: int, new_role: str):
    """
    Обновляет роль пользователя в таблице users базы данных
    """
    print(f"Обновляем роль пользователя в базе данных...")
    print(f"Telegram ID: {telegram_id}")
    print(f"Новая роль: {new_role}")
    
    # Создаем репозиторий и инициализируем базу данных
    repo = TransactionRepository()
    await repo.init_db()
    
    # Создаем сервис авторизации
    auth_service = AuthService(repo)
    
    try:
        # Обновляем роль пользователя
        success = await auth_service.update_user_role(telegram_id, new_role)
        
        if success:
            print(f"✅ Роль пользователя с Telegram ID {telegram_id} успешно обновлена на '{new_role}'")
            
            # Получаем обновленные данные пользователя
            user = await auth_service.get_user_by_telegram_id(telegram_id)
            if user:
                print(f"   ID: {user.id}")
                print(f"   Telegram ID: {user.telegram_id}")
                print(f"   Username: {user.username}")
                print(f"   Роль: {user.role}")
            else:
            print(f"❌ Пользователь с Telegram ID {telegram_id} не найден в базе данных")
            return False
            
        return success
        
    except Exception as e:
        print(f"❌ Произошла ошибка при обновлении роли пользователя: {e}")
        return False
    finally:
        await repo.close()


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Использование: python update_user_role.py <telegram_id> <role>")
        print("Пример: python update_user_role.py 123456789 admin")
        print("Пример: python update_user_role.py 123456789 user")
        sys.exit(1)
    
    telegram_id = int(sys.argv[1])
    role = sys.argv[2]
    
    print("=" * 60)
    print("СКРИПТ ОБНОВЛЕНИЯ РОЛИ ПОЛЬЗОВАТЕЛЯ В БАЗЕ ДАННЫХ BUDGET_BOT")
    print("=" * 60)
    
    # Обновляем роль пользователя
    success = asyncio.run(update_user_role_in_db(telegram_id, role))
    
    print("=" * 60)
    if success:
        print("✅ Скрипт выполнен успешно!")
        print("Роль пользователя обновлена в системе.")
    else:
        print("❌ Скрипт завершен с ошибками!")
    print("=" * 60)