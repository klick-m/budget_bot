#!/usr/bin/env python3
"""
Тестирование основных изменений связанных с наследованием репозиториев
"""
import asyncio
import tempfile
import os
from services.repository import TransactionRepository
from services.auth_service import AuthService
from utils.service_wrappers import AuthMiddleware


async def test_core_functionality():
    # Создаем временный файл базы данных для теста
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as temp_db:
        temp_db_path = temp_db.name

    try:
        # Инициализация репозитория (теперь TransactionRepository наследует UserRepository)
        transaction_repository = TransactionRepository(db_path=temp_db_path)
        await transaction_repository.init_db()

        print("✅ TransactionRepository успешно инициализирован")

        # Создаем AuthService (теперь принимает user_repo вместо repo)
        auth_service = AuthService(user_repo=transaction_repository)

        print("✅ AuthService успешно создан с TransactionRepository")

        # Регистрируем middleware авторизации (теперь принимает TransactionRepository)
        auth_middleware = AuthMiddleware(repo=transaction_repository)

        print("✅ AuthMiddleware успешно создан с TransactionRepository")

        # Проверяем, что все зависимости корректно установлены
        assert auth_service.user_repo == transaction_repository
        print("✅ Зависимость для AuthService корректно внедрена")

        # Проверяем, что методы из UserRepository доступны через TransactionRepository
        assert hasattr(transaction_repository, 'get_user_by_telegram_id')
        assert hasattr(transaction_repository, 'create_user')
        assert hasattr(transaction_repository, 'get_user_by_id')
        print("✅ Все методы UserRepository доступны через TransactionRepository")

        # Проверяем, что AuthMiddleware может вызвать метод get_user_by_telegram_id
        assert hasattr(auth_middleware.repo, 'get_user_by_telegram_id')
        print("✅ Метод get_user_by_telegram_id доступен для AuthMiddleware")

        print("\n🎉 Все основные тесты пройдены! Изменения в наследовании работают корректно.")

        # Дополнительно проверим, что при вызове init_db создаются обе таблицы
        import aiosqlite
        
        async with aiosqlite.connect(temp_db_path) as db:
            # Проверим, что таблица users существует
            cursor = await db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='users'"
            )
            users_table = await cursor.fetchone()
            
            # Проверим, что таблица transactions существует
            cursor = await db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='transactions'"
            )
            transactions_table = await cursor.fetchone()
            
            assert users_table is not None, "Таблица users не была создана"
            assert transactions_table is not None, "Таблица transactions не была создана"
            
            print("✅ Обе таблицы (users и transactions) успешно созданы при вызове init_db()")

    finally:
        # Удаляем временный файл базы данных
        if os.path.exists(temp_db_path):
            os.unlink(temp_db_path)


if __name__ == "__main__":
    asyncio.run(test_core_functionality())