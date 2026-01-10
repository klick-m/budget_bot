#!/usr/bin/env python3
"""
Тестирование запуска бота с новыми изменениями
"""
import asyncio
import tempfile
import os
from unittest.mock import AsyncMock, MagicMock
from services.repository import TransactionRepository
from services.transaction_service import TransactionService
from services.analytics_service import AnalyticsService
from services.auth_service import AuthService
from utils.service_wrappers import AuthMiddleware


async def test_bot_startup():
    # Создаем временный файл базы данных для теста
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as temp_db:
        temp_db_path = temp_db.name

    try:
        # Имитируем части бота
        mock_bot = AsyncMock()
        mock_bot.delete_my_commands = AsyncMock()
        mock_bot.session = MagicMock()
        mock_bot.session.close = MagicMock()

        # Инициализация репозитория (теперь TransactionRepository наследует UserRepository)
        transaction_repository = TransactionRepository(db_path=temp_db_path)
        await transaction_repository.init_db()

        print("✅ TransactionRepository успешно инициализирован")

        # Создаем TransactionService с внедренным репозиторием
        transaction_service = TransactionService(repository=transaction_repository)
        await transaction_service.initialize()

        print("✅ TransactionService успешно создан и инициализирован")

        # Регистрируем middleware авторизации (теперь принимает TransactionRepository)
        auth_middleware = AuthMiddleware(repo=transaction_repository)

        print("✅ AuthMiddleware успешно создан с TransactionRepository")

        # Создаем AuthService (теперь принимает user_repo вместо repo)
        auth_service = AuthService(user_repo=transaction_repository)

        print("✅ AuthService успешно создан с TransactionRepository")

        # Внедрение зависимостей (как в main.py)
        analytics_service = AnalyticsService(repository=transaction_repository)
        
        workflow_data = {
            "transaction_service": transaction_service,
            "analytics_service": analytics_service,
            "auth_service": auth_service
        }

        print("✅ Все сервисы успешно созданы и связаны")

        # Проверяем, что все зависимости корректно установлены
        assert workflow_data["auth_service"].user_repo == transaction_repository
        assert workflow_data["transaction_service"].repository == transaction_repository
        assert workflow_data["analytics_service"].repository == transaction_repository
        
        print("✅ Все зависимости корректно внедрены")

        # Проверяем, что методы из UserRepository доступны через TransactionRepository
        assert hasattr(transaction_repository, 'get_user_by_telegram_id')
        assert hasattr(transaction_repository, 'create_user')
        assert hasattr(transaction_repository, 'get_user_by_id')
        
        print("✅ Все методы UserRepository доступны через TransactionRepository")

        print("\n🎉 Все тесты запуска пройдены! Бот должен запуститься без ошибок.")

    finally:
        # Удаляем временный файл базы данных
        if os.path.exists(temp_db_path):
            os.unlink(temp_db_path)


if __name__ == "__main__":
    asyncio.run(test_bot_startup())