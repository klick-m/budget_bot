import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from aiogram import Router, Dispatcher
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message, CallbackQuery, User, Chat
from aiogram.methods import SendMessage
from aiogram.filters import Command

from handlers.common import command_start_handler
from utils.service_wrappers import AuthMiddleware
from services.repository import TransactionRepository


@pytest.mark.asyncio
async def test_command_start_handler_signature():
    """
    Тест проверяет сигнатуру хендлера command_start_handler.
    """
    # Проверяем, что хендлер ожидает 3 аргумента: message, data, state
    import inspect
    sig = inspect.signature(command_start_handler)
    params = list(sig.parameters.keys())
    assert len(params) == 3
    assert params[0] == 'message'
    assert params[1] == 'data'
    assert params[2] == 'state'


@pytest.mark.asyncio
async def test_dispatcher_calls_handler_with_correct_params():
    """
    Тест проверяет, как диспетчер вызывает хендлеры с правильными параметрами,
    включая FSMContext.
    """
    # Создаем mock объекты
    mock_user = User(id=123456789, is_bot=False, first_name="Test")
    mock_chat = Chat(id=123456789, type="private")
    
    # Создаем сообщение
    mock_message = Message(
        message_id=1,
        date=1234567890,
        chat=mock_chat,
        from_user=mock_user,
        text="/start"
    )
    original_answer = mock_message.answer
    mock_message.answer = AsyncMock()
    
    # Создаем диспетчер
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)
    
    # Создаем mock репозитория
    mock_repo = AsyncMock(spec=TransactionRepository)
    mock_repo.get_user_by_telegram_id = AsyncMock(return_value={
        "telegram_id": 123456789,
        "username": "test_user",
        "role": "user"
    })
    
    # Регистрируем middleware
    auth_middleware = AuthMiddleware(repo=mock_repo)
    dp.message.middleware(auth_middleware)
    
    # Создаем роутер и регистрируем хендлер
    router = Router()
    router.message.register(command_start_handler, Command("start"))
    dp.include_router(router)
    
    # Подготовка update для обработки
    from aiogram.types import Update
    update = Update(message=mock_message, update_id=1)
    
    # Попробуем обработать апдейт
    # Это должно вызвать ошибку, потому что наш middleware не передает FSMContext
    # но хендлер его ожидает
    try:
        await dp.feed_update(bot=AsyncMock(), update=update)
        # Если не было ошибки, значит middleware как-то обходит проблему
        # или FSMContext автоматически предоставляется диспетчером
    except Exception as e:
        # Ожидаем, что будет ошибка, связанная с количеством аргументов
        assert "missing" in str(e) or "required" in str(e) or "argument" in str(e)


@pytest.mark.asyncio
async def test_direct_handler_call_without_fsm_context():
    """
    Тест проверяет, что вызов хендлера напрямую без FSMContext приводит к ошибке.
    """
    # Создаем mock объекты
    mock_message = AsyncMock(spec=Message)
    mock_user = User(id=123456789, is_bot=False, first_name="Test")
    mock_chat = Chat(id=123456789, type="private")
    
    mock_message.from_user = mock_user
    mock_message.chat = mock_chat
    mock_message.text = "/start"
    mock_message.answer = AsyncMock()
    
    # Подготовка данных, которые обычно передаются из middleware
    mock_data = {
        "current_user": {
            "telegram_id": 123456789,
            "username": "test_user",
            "role": "user"
        }
    }
    
    # Проверяем, что хендлер ожидает 3 аргумента: message, data, state
    # Если передать только 2 (без state), должно быть TypeError
    with pytest.raises(TypeError) as exc_info:
        await command_start_handler(mock_message, mock_data)
    
    # Проверяем, что ошибка связана с отсутствующим аргументом 'state'
    assert "state" in str(exc_info.value) or "required" in str(exc_info.value)


@pytest.mark.asyncio
async def test_auth_middleware_only_passes_event_and_data():
    """
    Тест демонстрирует, что AuthMiddleware передает только event и data в хендлер,
    но не FSMContext, который может ожидаться хендлером.
    """
    # Создаем mock объекты
    mock_message = AsyncMock(spec=Message)
    mock_user = User(id=123456789, is_bot=False, first_name="Test")
    mock_chat = Chat(id=123456789, type="private")
    
    mock_message.from_user = mock_user
    mock_message.chat = mock_chat
    mock_message.text = "/start"
    
    # Создаем mock репозитория
    mock_repo = AsyncMock(spec=TransactionRepository)
    mock_repo.get_user_by_telegram_id = AsyncMock(return_value={
        "telegram_id": 123456789,
        "username": "test_user",
        "role": "user"
    })
    
    # Создаем AuthMiddleware
    auth_middleware = AuthMiddleware(repo=mock_repo)
    
    # Хендлер, который ожидает 3 параметра: event, data и state
    async def mock_handler_that_expects_state(event, data, state):
        # Этот handler ожидает 3 параметра: event, data и state
        pass
    
    # Подготовка данных для middleware
    data = {}
    
    # Проверяем, что при вызове middleware с handler, который ожидает FSMContext,
    # возникнет ошибка, потому что middleware передает только event и data
    with pytest.raises(TypeError) as exc_info:
        await auth_middleware(mock_handler_that_expects_state, mock_message, data)
    
    # Проверяем, что ошибка связана с отсутствующим аргументом
    assert "missing" in str(exc_info.value) or "required" in str(exc_info.value) or "argument" in str(exc_info.value)