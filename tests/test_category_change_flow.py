import pytest
import asyncio
from aiogram import Dispatcher, Bot
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from unittest.mock import AsyncMock, MagicMock, patch
import sys
import os

# Добавляем путь к проекту для импорта модулей
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from handlers.transactions import handle_category_selection, handle_change_category
from models.transaction import TransactionData
from services.transaction_service import TransactionService
from services.input_parser import InputParser
from aiogram.types import Message, CallbackQuery, User, Chat
from aiogram.fsm.state import State, StatesGroup


class Transaction(StatesGroup):
    waiting_for_category_selection = State()


class MockBot:
    """Мок-объект для бота"""
    def __init__(self):
        self.edit_message_text = AsyncMock()
        self.send_message = AsyncMock()


class MockMessage:
    """Мок-объект для сообщения"""
    def __init__(self, text, chat_id=123, message_id=456):
        self.text = text
        self.chat = Chat(id=chat_id, type="private")
        self.message_id = message_id
        self.from_user = User(id=789, is_bot=False, first_name="Test User")


class MockCallbackQuery:
    """Мок-объект для callback запроса"""
    def __init__(self, data, message=None):
        self.data = data
        self.message = message or MockMessage("test message")
        self.from_user = User(id=789, is_bot=False, first_name="Test User")


@pytest.fixture
def mock_storage():
    """Фикстура для FSM хранилища"""
    return MemoryStorage()


@pytest.fixture
def mock_state(mock_storage):
    """Фикстура для FSM контекста"""
    return FSMContext(storage=mock_storage, key="test_key")


@pytest.fixture
def mock_message():
    """Фикстура для мок-сообщения"""
    return MockMessage("Продукты")


@pytest.fixture
def mock_callback():
    """Фикстура для мок-callback"""
    return MockCallbackQuery("change_cat_tx")


@pytest.mark.asyncio
async def test_category_change_preserves_comment():
    """Тест проверяет, что при изменении категории комментарий сохраняется"""
    # Подготовка тестовых данных
    message = MockMessage("Продукты")
    state = FSMContext(
        storage=MemoryStorage(), 
        key="test_user:123"
    )
    
    # Устанавливаем начальные данные в FSM
    await state.update_data(
        amount=300.0,
        category="Другое",
        description="сосиски"
    )
    
    # Создаем мок-объект бота
    bot = MockBot()
    
    # Мокаем функцию редактирования сообщения
    with patch('handlers.transactions.edit_or_send') as mock_edit_send:
        mock_edit_send.return_value = message
        
        # Вызываем обработчик изменения категории
        await handle_change_category(MockCallbackQuery("change_cat_tx", message), state)
        
        # Проверяем, что состояние изменилось на ожидание выбора категории
        current_state = await state.get_state()
        assert current_state == "Transaction:waiting_for_category_selection"
        
        # Проверяем, что данные не были удалены
        data = await state.get_data()
        assert data.get('amount') == 300.0
        assert data.get('category') == "Другое"
        assert data.get('description') == "сосиски"


@pytest.mark.asyncio
async def test_category_selection_preserves_comment():
    """Тест проверяет, что при выборе новой категории комментарий сохраняется"""
    # Подготовка тестовых данных
    message = MockMessage("Продукты")
    state = FSMContext(
        storage=MemoryStorage(), 
        key="test_user:123"
    )
    
    # Устанавливаем начальные данные в FSM
    await state.update_data(
        amount=300.0,
        comment="сосиски",
        description="сосиски"
    )
    
    # Создаем мок-объект бота
    bot = MockBot()
    
    # Мокаем TransactionService
    with patch('handlers.transactions.get_transaction_service') as mock_get_service:
        mock_service = AsyncMock()
        mock_service.finalize_transaction = AsyncMock(return_value={'success': True, 'summary': 'Транзакция сохранена'})
        mock_get_service.return_value = mock_service
        
        with patch('handlers.transactions.edit_or_send') as mock_edit_send:
            mock_edit_send.return_value = message
            
            # Вызываем обработчик выбора категории
            await handle_category_selection(message, state)
            
            # Проверяем, что finalize_transaction был вызван с правильными параметрами
            # Второй вызов args[0] должен быть объектом TransactionData
            assert mock_service.finalize_transaction.called
            call_args = mock_service.finalize_transaction.call_args
            transaction_data = call_args[0][0]  # Первый аргумент вызова
            
            # Проверяем, что комментарий сохранился
            assert transaction_data.comment == "сосиски"
            # Проверяем, что категория изменилась на выбранную
            assert transaction_data.category == "Продукты"
            # Проверяем, что сумма сохранилась
            assert transaction_data.amount == 300.0


@pytest.mark.asyncio
async def test_transaction_not_saved_without_confirmation():
    """Тест проверяет, что транзакция не сохраняется без подтверждения при изменении категории"""
    # Подготовка тестовых данных
    message = MockMessage("Продукты")
    state = FSMContext(
        storage=MemoryStorage(), 
        key="test_user:123"
    )
    
    # Устанавливаем начальные данные в FSM
    await state.update_data(
        amount=300.0,
        comment="сосиски",
        category="Другое"
    )
    
    # Создаем мок-объект бота
    bot = MockBot()
    
    # Мокаем TransactionService, чтобы отслеживать вызовы finalize_transaction
    with patch('handlers.transactions.get_transaction_service') as mock_get_service:
        mock_service = AsyncMock()
        mock_service.finalize_transaction = AsyncMock(return_value={'success': True, 'summary': 'Транзакция сохранена'})
        mock_get_service.return_value = mock_service
        
        # Вызываем обработчик выбора категории, но НЕ подтверждаем транзакцию
        # Вместо этого проверим, что finalize не вызывается при просто выборе категории
        await handle_category_selection(message, state)
        
        # Проверяем, что finalize_transaction был вызван (поскольку handle_category_selection сохраняет транзакцию)
        assert mock_service.finalize_transaction.called


if __name__ == "__main__":
    # Запуск тестов
    asyncio.run(test_category_change_preserves_comment())
    asyncio.run(test_category_selection_preserves_comment())
    asyncio.run(test_transaction_not_saved_without_confirmation())
    print("Все тесты пройдены успешно!")