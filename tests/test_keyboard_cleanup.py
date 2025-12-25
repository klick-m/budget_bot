import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from aiogram.types import Message, User, Chat
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State
from handlers.transactions import handle_category_selection
from aiogram import types


class MockState:
    """Mock для FSMContext"""
    def __init__(self):
        self.data = {}
        self.cleared = False

    async def get_data(self):
        return self.data

    async def update_data(self, **kwargs):
        self.data.update(kwargs)

    async def clear(self):
        self.cleared = True
        self.data = {}


class MockBot:
    """Mock для Bot"""
    def __init__(self):
        self.edit_message_reply_markup = AsyncMock()


class MockMessage:
    """Mock для Message"""
    def __init__(self, text, from_user=None, chat=None):
        self.text = text
        self.from_user = from_user or User(id=1, is_bot=False, first_name="Test")
        self.chat = chat or Chat(id=1, type="private")
        self.answer = AsyncMock()


@pytest.mark.asyncio
async def test_handle_category_selection_keyboard_cleanup():
    """Тест проверяет, что клавиатура убирается при выборе категории"""
    # Подготовка моков
    mock_message = MockMessage("Продукты")
    mock_message.bot = MockBot()
    mock_state = MockState()
    
    # Установим тестовые данные в состояние
    mock_state.data = {
        'amount': 100.0,
        'description': 'покупка в магазине',
        'comment': 'покупка в магазине'
    }
    
    # Мокаем TransactionService
    with patch('handlers.transactions.get_transaction_service') as mock_get_service:
        mock_service = AsyncMock()
        mock_service.finalize_transaction.return_value = {'success': True, 'summary': 'Транзакция сохранена'}
        mock_service.classifier = MagicMock()
        mock_service.classifier.learn_keyword = MagicMock()
        mock_get_service.return_value = mock_service
        
        # Также мокаем CATEGORY_STORAGE
        with patch('handlers.transactions.CATEGORY_STORAGE') as mock_category_storage:
            mock_category_storage.expense = ['Продукты', 'Транспорт', 'Развлечения', 'Прочее Расход']
            
            # Мокаем clean_previous_kb
            with patch('handlers.transactions.clean_previous_kb') as mock_clean_kb:
                mock_clean_kb.return_value = AsyncMock()
                
                # Вызываем тестируемую функцию
                await handle_category_selection(mock_message, mock_state)
                
                # Проверяем, что clean_previous_kb был вызван
                mock_clean_kb.assert_called_once()


@pytest.mark.asyncio
async def test_handle_category_selection_error_keyboard_cleanup():
    """Тест проверяет, что клавиатура убирается при ошибке записи транзакции"""
    # Подготовка моков
    mock_message = MockMessage("Продукты")
    mock_message.bot = MockBot()
    mock_state = MockState()
    
    # Установим тестовые данные в состояние
    mock_state.data = {
        'amount': 100.0,
        'description': 'покупка в магазине',
        'comment': 'покупка в магазине'
    }
    
    # Мокаем TransactionService для возврата ошибки
    with patch('handlers.transactions.get_transaction_service') as mock_get_service:
        mock_service = AsyncMock()
        mock_service.finalize_transaction.return_value = {'success': False, 'error': 'Ошибка при записи'}
        mock_service.classifier = MagicMock()
        mock_service.classifier.learn_keyword = MagicMock()
        mock_get_service.return_value = mock_service
        
        # Также мокаем CATEGORY_STORAGE
        with patch('handlers.transactions.CATEGORY_STORAGE') as mock_category_storage:
            mock_category_storage.expense = ['Продукты', 'Транспорт', 'Развлечения', 'Прочее Расход']
            
            # Мокаем clean_previous_kb
            with patch('handlers.transactions.clean_previous_kb') as mock_clean_kb:
                mock_clean_kb.return_value = AsyncMock()
                
                # Вызываем тестируемую функцию
                await handle_category_selection(mock_message, mock_state)
                
                # Проверяем, что clean_previous_kb был вызван даже при ошибке
                mock_clean_kb.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__])