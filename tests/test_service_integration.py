import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from aiogram import Bot, types
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram import Dispatcher

from main import main
from services.transaction_service import TransactionService
from services.repository import TransactionRepository
from services.auth_service import AuthService
from services.analytics_service import AnalyticsService
from handlers import register_all_handlers
from utils.service_wrappers import AuthMiddleware


@pytest.mark.asyncio
async def test_service_integration():
    """Тест интеграции сервисов: AuthService, TransactionService, AnalyticsService"""
    
    # Создаем репозиторий
    transaction_repository = TransactionRepository()
    await transaction_repository.init_db()
    
    # Создаем все сервисы
    transaction_service = TransactionService(repository=transaction_repository)
    await transaction_service.initialize()
    
    auth_service = AuthService(repo=transaction_repository)
    analytics_service = AnalyticsService(repository=transaction_repository)
    
    # Проверяем, что все сервисы были созданы
    assert transaction_service is not None
    assert auth_service is not None
    assert analytics_service is not None
    
    # Проверяем внедрение зависимостей в диспетчер
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)
    
    # Регистрируем middleware авторизации
    auth_middleware = AuthMiddleware(repo=transaction_repository)
    dp.message.middleware(auth_middleware)
    dp.callback_query.middleware(auth_middleware)
    
    # Внедрение зависимостей
    dp.workflow_data.update({
        "transaction_service": transaction_service,
        "auth_service": auth_service,
        "analytics_service": analytics_service
    })
    
    # Регистрируем обработчики
    register_all_handlers(dp)
    
    # Проверяем, что все сервисы доступны в контексте
    assert dp.workflow_data.get("transaction_service") == transaction_service
    assert dp.workflow_data.get("auth_service") == auth_service
    assert dp.workflow_data.get("analytics_service") == analytics_service
    
    # Закрываем соединение с БД
    await transaction_repository.close()


@pytest.mark.asyncio
async def test_auth_service_injection_in_handlers():
    """Тест: AuthService корректно внедряется в хендлеры"""
    
    # Создаем репозиторий
    transaction_repository = TransactionRepository()
    await transaction_repository.init_db()
    
    # Создаем сервисы
    auth_service = AuthService(repo=transaction_repository)
    transaction_service = TransactionService(repository=transaction_repository)
    await transaction_service.initialize()
    analytics_service = AnalyticsService(repository=transaction_repository)
    
    # Создаем диспетчер
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)
    
    # Регистрируем middleware авторизации
    auth_middleware = AuthMiddleware(repo=transaction_repository)
    dp.message.middleware(auth_middleware)
    dp.callback_query.middleware(auth_middleware)
    
    # Внедрение зависимостей
    dp.workflow_data.update({
        "transaction_service": transaction_service,
        "auth_service": auth_service,
        "analytics_service": analytics_service
    })
    
    # Регистрируем хендлеры
    register_all_handlers(dp)
    
    # Проверяем, что в диспетчере есть нужные хендлеры
    assert len(dp.message.handlers) > 0
    assert len(dp.callback_query.handlers) > 0
    
    # Проверяем, что AuthService внедрен в хендлеры
    found_admin_handler = False
    for handler in dp.message.handlers:
        # Проверяем, есть ли среди зарегистрированных хендлеров те, которые принимают auth_service
        if hasattr(handler.callback, '__name__'):
            if handler.callback.__name__ in ['admin_command_handler', 'add_user_command_handler', 
                                          'remove_user_command_handler', 'set_role_command_handler', 
                                          'list_users_command_handler']:
                found_admin_handler = True
                break
    
    assert found_admin_handler, "Хендлеры администрирования не найдены"
    
    # Закрываем соединение с БД
    await transaction_repository.close()


@pytest.mark.asyncio
async def test_analytics_service_injection():
    """Тест: AnalyticsService корректно внедряется в хендлеры"""
    
    # Создаем репозиторий
    transaction_repository = TransactionRepository()
    await transaction_repository.init_db()
    
    # Создаем сервисы
    auth_service = AuthService(repo=transaction_repository)
    transaction_service = TransactionService(repository=transaction_repository)
    await transaction_service.initialize()
    analytics_service = AnalyticsService(repository=transaction_repository)
    
    # Создаем диспетчер
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)
    
    # Регистрируем middleware авторизации
    auth_middleware = AuthMiddleware(repo=transaction_repository)
    dp.message.middleware(auth_middleware)
    dp.callback_query.middleware(auth_middleware)
    
    # Внедрение зависимостей
    dp.workflow_data.update({
        "transaction_service": transaction_service,
        "auth_service": auth_service,
        "analytics_service": analytics_service
    })
    
    # Регистрируем хендлеры
    register_all_handlers(dp)
    
    # Проверяем, что AnalyticsService внедрен в хендлеры
    found_report_handler = False
    for handler in dp.message.handlers:
        # Проверяем, есть ли среди зарегистрированных хендлеров те, которые принимают analytics_service
        if hasattr(handler.callback, '__name__'):
            if handler.callback.__name__ == 'report_command_handler':
                found_report_handler = True
                break
    
    assert found_report_handler, "Хендлер отчетов не найден"
    
    # Закрываем соединение с БД
    await transaction_repository.close()