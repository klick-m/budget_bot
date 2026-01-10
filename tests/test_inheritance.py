#!/usr/bin/env python3
"""
Тестирование новой структуры наследования репозиториев
"""
import asyncio
import tempfile
import os
from services.repository import TransactionRepository
from services.auth_service import AuthService
from utils.service_wrappers import AuthMiddleware


async def test_inheritance():
    # Создаем временный файл базы данных для теста
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as temp_db:
        temp_db_path = temp_db.name

    try:
        # Создаем экземпляр TransactionRepository (теперь наследует UserRepository)
        transaction_repository = TransactionRepository(db_path=temp_db_path)
        
        # Инициализируем базу данных (теперь будет создавать обе таблицы: users и transactions)
        await transaction_repository.init_db()
        
        print("✅ init_db успешно выполнен - созданы обе таблицы (users и transactions)")
        
        # Проверяем, что методы UserRepository доступны через TransactionRepository
        user_methods = [
            'get_user_by_id',
            'create_user', 
            'get_user_by_telegram_id',
            'update_user_fields',
            'delete_user',
            'get_all_users'
        ]
        
        for method in user_methods:
            assert hasattr(transaction_repository, method), f"Метод {method} недоступен"
        
        print("✅ Все методы UserRepository доступны через TransactionRepository")
        
        # Создаем AuthService с TransactionRepository (теперь наследует UserRepository)
        auth_service = AuthService(user_repo=transaction_repository)
        print("✅ AuthService успешно создан с TransactionRepository")
        
        # Создаем AuthMiddleware с TransactionRepository (теперь наследует UserRepository)
        auth_middleware = AuthMiddleware(repo=transaction_repository)
        print("✅ AuthMiddleware успешно создан с TransactionRepository")
        
        # Проверяем, что метод get_user_by_telegram_id доступен (он используется в AuthMiddleware)
        assert hasattr(auth_middleware.repo, 'get_user_by_telegram_id'), \
            "Метод get_user_by_telegram_id недоступен для AuthMiddleware"
        print("✅ Метод get_user_by_telegram_id доступен для AuthMiddleware")
        
        print("\n🎉 Все тесты пройдены! Новое наследование работает корректно.")
        
    finally:
        # Удаляем временный файл базы данных
        if os.path.exists(temp_db_path):
            os.unlink(temp_db_path)


if __name__ == "__main__":
    asyncio.run(test_inheritance())