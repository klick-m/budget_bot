import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
from aiogram import types
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, User, Chat

from handlers.smart_input import process_smart_input
from services.transaction_service import TransactionService
from models.transaction import TransactionData


@pytest.mark.asyncio
async def test_process_smart_input_success():
    """Тест: успешная обработка умного ввода транзакции"""
    # Подготовка mock объектов
    mock_user = MagicMock()
    mock_user.id = 123456789
    mock_user.username = "testuser"
    mock_user.full_name = "Test User"
    
    mock_message = MagicMock()
    mock_message.text = "кофе 300"
    mock_message.from_user = mock_user
    mock_message.answer = AsyncMock()
    
    mock_state = AsyncMock()
    mock_state.clear = AsyncMock()
    mock_state.update_data = AsyncMock()
    mock_state.set_state = AsyncMock()
    
    mock_service = AsyncMock(spec=TransactionService)
    mock_service.load_categories = AsyncMock()
    mock_service.classifier = MagicMock()
    mock_service.classifier.predict_category = MagicMock(return_value=("Продукты", 0.8))
    mock_service.finalize_transaction = AsyncMock()
    
    data = {
        "current_user": {
            "id": 1,
            "telegram_id": 123456789,
            "username": "testuser",
            "role": "user"
        },
        "transaction_service": mock_service
    }
    
    # Выполнение
    await process_smart_input(mock_message, mock_state, data, mock_service)
    
    # Проверка
    mock_state.clear.assert_called_once()
    mock_service.load_categories.assert_called_once()
    mock_state.update_data.assert_called_once()
    mock_state.set_state.assert_called_once()
    mock_message.answer.assert_called_once()


@pytest.mark.asyncio
async def test_process_smart_input_invalid_format():
    """Тест: обработка некорректного формата ввода"""
    # Подготовка mock объектов
    mock_user = MagicMock()
    mock_user.id = 123456789
    mock_user.username = "testuser"
    mock_user.full_name = "Test User"
    
    mock_message = MagicMock()
    mock_message.text = "некорректный ввод"
    mock_message.from_user = mock_user
    mock_message.answer = AsyncMock()
    
    mock_state = AsyncMock()
    mock_state.clear = AsyncMock()
    mock_state.update_data = AsyncMock()
    mock_state.set_state = AsyncMock()
    
    mock_service = AsyncMock(spec=TransactionService)
    mock_service.load_categories = AsyncMock()
    mock_service.classifier = MagicMock()
    mock_service.classifier.predict_category = MagicMock(return_value=("Продукты", 0.8))
    mock_service.finalize_transaction = AsyncMock()
    
    data = {
        "current_user": {
            "id": 1,
            "telegram_id": 123456789,
            "username": "testuser",
            "role": "user"
        },
        "transaction_service": mock_service
    }
    
    # Выполнение
    await process_smart_input(mock_message, mock_state, data, mock_service)
    
    # Проверка - должно быть сообщение об ошибке парсинга
    # Так как ввод "некорректный ввод" не содержит числовую сумму, InputParser должен вернуть None
    # и вызваться MSG.error_parsing_no_amount
    mock_message.answer.assert_called()


@pytest.mark.asyncio
async def test_process_smart_input_missing_user_data():
    """Тест: обработка случая, когда данные пользователя отсутствуют"""
    # Подготовка mock объектов
    mock_user = MagicMock()
    mock_user.id = 123456789
    mock_user.username = "testuser"
    mock_user.full_name = "Test User"
    
    mock_message = MagicMock()
    mock_message.text = "кофе 300"
    mock_message.from_user = mock_user
    mock_message.answer = AsyncMock()
    
    mock_state = AsyncMock()
    mock_state.clear = AsyncMock()
    mock_state.update_data = AsyncMock()
    mock_state.set_state = AsyncMock()
    
    mock_service = AsyncMock(spec=TransactionService)
    mock_service.load_categories = AsyncMock()
    mock_service.classifier = MagicMock()
    mock_service.classifier.predict_category = MagicMock(return_value=("Продукты", 0.8))
    mock_service.finalize_transaction = AsyncMock()
    
    data = {
        "current_user": None,  # Нет данных пользователя
        "transaction_service": mock_service
    }
    
    # Выполнение
    await process_smart_input(mock_message, mock_state, data, mock_service)
    
    # Проверка
    mock_message.answer.assert_called_once_with("❌ Ошибка: невозможно получить информацию о пользователе.")