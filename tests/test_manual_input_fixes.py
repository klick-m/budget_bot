import pytest
import asyncio
from datetime import datetime
from aiogram import types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from unittest.mock import AsyncMock, MagicMock, patch

from handlers.transactions import (
    Transaction,
    new_transaction_handler,
    handle_category_selection,
    handle_change_category,
    parse_transaction_handler,
    smart_input_handler
)
from models.transaction import TransactionData
from services.global_service_locator import get_transaction_service


@pytest.fixture
def mock_message():
    message = MagicMock(spec=types.Message)
    message.text = "Test message"
    message.from_user = MagicMock()
    message.from_user.username = "test_user"
    message.from_user.full_name = "Test User"
    message.from_user.id = 123456
    message.chat = MagicMock()
    message.chat.id = 123456
    message.answer = AsyncMock()
    return message


@pytest.fixture
def mock_callback():
    callback = MagicMock(spec=types.CallbackQuery)
    callback.data = "test_data"
    callback.from_user = MagicMock()
    callback.from_user.username = "test_user"
    callback.from_user.full_name = "Test User"
    callback.from_user.id = 123456
    callback.message = MagicMock()
    callback.message.text = "Test message"
    callback.message.chat = MagicMock()
    callback.message.chat.id = 123456
    callback.answer = AsyncMock()
    return callback


@pytest.fixture
def mock_state():
    storage = MemoryStorage()
    # FSMContext принимает storage и StorageKey
    from aiogram.fsm.storage.base import StorageKey
    from aiogram.types import User, Chat
    chat = Chat(id=123456, type="private")
    user = User(id=123456, is_bot=False, first_name="Test")
    key = StorageKey(bot_id=123, chat_id=chat.id, user_id=user.id)
    state = FSMContext(storage, key)
    return state


@pytest.fixture
def mock_transaction_service():
    service = MagicMock()
    service.classifier = MagicMock()
    service.classifier.get_category_by_keyword.return_value = None
    service.classifier.predict_category.return_value = ("Продукты", 0.8)
    service.classifier.predict.return_value = "Другое"
    service.classifier.learn_keyword = MagicMock()
    service.finalize_transaction = AsyncMock()
    service.finalize_transaction.return_value = {
        'success': True,
        'summary': 'Test summary'
    }
    return service


@pytest.mark.asyncio
async def test_smart_input_handler_with_keyword_recognition(
    mock_message, mock_state, mock_transaction_service
):
    """Тест: Проверка распознавания по ключевому слову в smart_input_handler"""
    with patch('handlers.transactions.get_transaction_service') as mock_get_service:
        mock_get_service.return_value = mock_transaction_service
        
        # Мокаем результат классификатора для ключевого слова
        mock_transaction_service.classifier.get_category_by_keyword.return_value = ("Продукты", 0.9)
        
        mock_message.text = "сосиски 300"
        
        await smart_input_handler(mock_message, mock_state)
        
        # Проверяем, что была вызвана функция сохранения транзакции
        assert mock_transaction_service.finalize_transaction.called
        # Проверяем, что транзакция создана с правильной категорией
        args, kwargs = mock_transaction_service.finalize_transaction.call_args
        transaction_data = args[0]
        assert transaction_data.category == "Продукты"
        assert transaction_data.comment == "сосиски"
        assert transaction_data.amount == 300


@pytest.mark.asyncio
async def test_smart_input_handler_with_ml_classification(
    mock_message, mock_state, mock_transaction_service
):
    """Тест: Проверка ML-классификации в smart_input_handler"""
    with patch('handlers.transactions.get_transaction_service') as mock_get_service:
        mock_get_service.return_value = mock_transaction_service
        
        # Мокаем результат классификатора для ML-классификации
        mock_transaction_service.classifier.get_category_by_keyword.return_value = None
        mock_transaction_service.classifier.predict_category.return_value = ("Транспорт", 0.7)
        
        mock_message.text = "такси 500"
        
        await smart_input_handler(mock_message, mock_state)
        
        # Проверяем, что была вызвана функция сохранения транзакции
        assert mock_transaction_service.finalize_transaction.called
        # Проверяем, что транзакция создана с правильной категорией
        args, kwargs = mock_transaction_service.finalize_transaction.call_args
        transaction_data = args[0]
        assert transaction_data.category == "Транспорт"
        assert transaction_data.comment == "такси"
        assert transaction_data.amount == 500


@pytest.mark.asyncio
async def test_parse_transaction_handler_with_keyword_recognition(
    mock_message, mock_state, mock_transaction_service
):
    """Тест: Проверка распознавания по ключевому слову в parse_transaction_handler"""
    with patch('handlers.transactions.get_transaction_service') as mock_get_service:
        mock_get_service.return_value = mock_transaction_service
        with patch('handlers.transactions.parse_transaction_text') as mock_parse:
            mock_parse.return_value = {'amount': 300, 'category': 'сосиски'}
            
            # Мокаем результат классификатора для ключевого слова
            mock_transaction_service.classifier.get_category_by_keyword.return_value = ("Продукты", 0.9)
            
            mock_message.text = "сосиски 300"
            
            await parse_transaction_handler(mock_message, mock_state)
            
            # Проверяем, что состояние изменилось на ожидание подтверждения
            current_state = await mock_state.get_state()
            assert current_state == "Transaction:waiting_for_confirmation"
            
            # Проверяем, что данные сохранены корректно
            data = await mock_state.get_data()
            assert data['amount'] == 300
            assert data['category'] == "Продукты"
            assert data['description'] == "сосиски"


@pytest.mark.asyncio
async def test_handle_category_selection_preserves_comment(
    mock_message, mock_state, mock_transaction_service
):
    """Тест: Проверка сохранения комментария при смене категории"""
    with patch('handlers.transactions.get_transaction_service') as mock_get_service:
        mock_get_service.return_value = mock_transaction_service
        
        # Мокаем CATEGORY_STORAGE из config
        with patch('config.CATEGORY_STORAGE') as mock_category_storage:
            mock_category_storage.expense = ["Продукты", "Транспорт", "Другое"]
            
            # Устанавливаем состояние и данные
            await mock_state.set_state(Transaction.waiting_for_category_selection)
            await mock_state.update_data(amount=300, comment="сосиски", description="сосиски")
            
            mock_message.text = "Продукты"
            
            await handle_category_selection(mock_message, mock_state)
            
            # Проверяем, что транзакция создана с сохранением комментария
            await asyncio.sleep(0.1)  # Небольшая задержка для завершения асинхронной операции
            assert mock_transaction_service.finalize_transaction.called
            args, kwargs = mock_transaction_service.finalize_transaction.call_args
            transaction_data = args[0]
            assert transaction_data.category == "Продукты"
            assert transaction_data.comment == "сосиски"
            assert transaction_data.amount == 300


@pytest.mark.asyncio
async def test_handle_category_selection_preserves_description(
    mock_message, mock_state, mock_transaction_service
):
    """Тест: Проверка сохранения описания при смене категории через FSM"""
    with patch('handlers.transactions.get_transaction_service') as mock_get_service:
        mock_get_service.return_value = mock_transaction_service
        
        # Мокаем CATEGORY_STORAGE из config
        with patch('config.CATEGORY_STORAGE') as mock_category_storage:
            mock_category_storage.expense = ["Продукты", "Транспорт", "Другое"]
            
            # Устанавливаем состояние и данные
            await mock_state.set_state(Transaction.waiting_for_category_selection)
            await mock_state.update_data(amount=500, description="такси")
            
            mock_message.text = "Транспорт"
            
            await handle_category_selection(mock_message, mock_state)
            
            # Проверяем, что транзакция создана с сохранением описания
            await asyncio.sleep(0.1)  # Небольшая задержка для завершения асинхронной операции
            assert mock_transaction_service.finalize_transaction.called
            args, kwargs = mock_transaction_service.finalize_transaction.call_args
            transaction_data = args[0]
            assert transaction_data.category == "Транспорт"
            assert transaction_data.comment == "такси"  # description должен быть сохранен как comment
            assert transaction_data.amount == 500


@pytest.mark.asyncio
async def test_handle_change_category_shows_current_comment(
    mock_callback, mock_state
):
    """Тест: Проверка показа текущего комментария при изменении категории"""
    await mock_state.update_data(description="тестовый комментарий")
    
    mock_callback.message.answer = AsyncMock()
    mock_callback.data = "change_cat_tx"
    mock_callback.answer = AsyncMock()
    
    with patch('aiogram.types.ReplyKeyboardMarkup') as mock_keyboard:
        mock_keyboard_instance = MagicMock()
        mock_keyboard.return_value = mock_keyboard_instance
        
        await handle_change_category(mock_callback, mock_state)
        
        # Проверяем, что сообщение содержит текущий комментарий
        mock_callback.message.answer.assert_called()
        call_args = mock_callback.message.answer.call_args
        assert "тестовый комментарий" in call_args[0][0]
        
        # Проверяем, что состояние изменилось
        current_state = await mock_state.get_state()
        assert current_state == "Transaction:waiting_for_category_selection"


@pytest.mark.asyncio
async def test_new_transaction_handler_creates_empty_draft(
    mock_message, mock_state
):
    """Тест: Проверка создания пустого черновика при новой транзакции"""
    await mock_state.clear()
    
    # Мокаем функции, чтобы избежать лишних вызовов
    with patch('handlers.transactions.clean_previous_kb') as mock_clean, \
         patch('handlers.transactions.send_draft_message') as mock_send:
        
        await new_transaction_handler(mock_message, mock_state)
        
        # Проверяем, что состояние изменилось
        current_state = await mock_state.get_state()
        assert current_state == "Transaction:editing_draft"
        
        # Проверяем, что черновик создан с пустыми полями
        data = await mock_state.get_data()
        assert 'draft' in data
        draft = data['draft']
        assert draft['type'] is None
        assert draft['category'] is None
        assert draft['amount'] is None
        assert draft['comment'] == ""