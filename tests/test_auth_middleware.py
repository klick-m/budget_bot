import pytest
from unittest.mock import AsyncMock, MagicMock, Mock
from datetime import datetime
from aiogram.types import Message, CallbackQuery, User, Chat
from services.repository import UserRepository
from utils.service_wrappers import AuthMiddleware


@pytest.fixture
def mock_repo():
    """Мок репозитория для тестов"""
    repo = AsyncMock(spec=UserRepository)
    # Добавляем метод, который будет использоваться в middleware
    repo.get_user_by_telegram_id = AsyncMock()
    return repo


@pytest.fixture
def auth_middleware(mock_repo):
    """Создание экземпляра AuthMiddleware с мок-репозиторием"""
    return AuthMiddleware(repo=mock_repo)


class TestAuthMiddleware:
    """Тесты для middleware аутентификации"""

    @pytest.mark.asyncio
    async def test_allowed_user_message(self, auth_middleware, mock_repo):
        """Тест: разрешенный пользователь может отправлять сообщения"""
        # Подготовка
        user = User(
            id=123456789,
            is_bot=False,
            first_name="Test"
        )
        chat = Chat(
            id=123456789,
            type="private"
        )
        message = Message(
            message_id=1,
            date=int(datetime.now().timestamp()),
            chat=chat,
            from_user=user,
            text="/start"
        )
        
        # Настройка мока - пользователь существует в БД
        mock_repo.get_user_by_telegram_id.return_value = {
            'id': 1,
            'telegram_id': 123456789,
            'username': 'testuser',
            'role': 'user',
            'monthly_limit': 1000
        }
        
        # Заглушка для handler
        handler = AsyncMock(return_value="success")
        
        # Выполнение
        result = await auth_middleware(handler, message, {"handler": handler})
        
        # Проверка
        assert result == "success"  # Обработчик должен быть вызван
        mock_repo.get_user_by_telegram_id.assert_called_once_with(123456789)

    @pytest.mark.asyncio
    async def test_allowed_user_callback_query(self, auth_middleware, mock_repo):
        """Тест: разрешенный пользователь может отправлять callback запросы"""
        # Подготовка
        user = User(
            id=123456789,
            is_bot=False,
            first_name="Test"
        )
        callback_query = CallbackQuery(
            id="123",
            from_user=user,
            chat_instance="test",
            data="test_data"
        )
        
        # Настройка мока - пользователь существует в БД
        mock_repo.get_user_by_telegram_id.return_value = {
            'id': 1,
            'telegram_id': 123456789,
            'username': 'testuser',
            'role': 'user',
            'monthly_limit': 10000
        }
        
        # Заглушка для handler
        handler = AsyncMock(return_value="success")
        
        # Выполнение
        result = await auth_middleware(handler, callback_query, {"handler": handler})
        
        # Проверка
        assert result == "success"  # Обработчик должен быть вызван
        mock_repo.get_user_by_telegram_id.assert_called_once_with(123456789)

    @pytest.mark.asyncio
    async def test_unauthorized_user_message(self, auth_middleware, mock_repo):
        """Тест: неразрешенный пользователь не может отправлять сообщения"""
        # Подготовка
        user = User(
            id=987654321,
            is_bot=False,
            first_name="Unknown"
        )
        chat = Chat(
            id=987654321,
            type="private"
        )
        message = Message(
            message_id=1,
            date=int(datetime.now().timestamp()),
            chat=chat,
            from_user=user,
            text="/start"
        )
        
        # Настройка мока - пользователь НЕ существует в БД
        mock_repo.get_user_by_telegram_id.return_value = None
        
        # Заглушка для handler
        handler = AsyncMock(return_value="success")
        
        # Выполнение
        result = await auth_middleware(handler, message, {"handler": handler})
        
        # Проверка
        assert result is None  # Обработчик НЕ должен быть вызван
        mock_repo.get_user_by_telegram_id.assert_called_once_with(987654321)

    @pytest.mark.asyncio
    async def test_unauthorized_user_callback_query(self, auth_middleware, mock_repo):
        """Тест: неразрешенный пользователь не может отправлять callback запросы"""
        # Подготовка
        user = User(
            id=987654321,
            is_bot=False,
            first_name="Unknown"
        )
        callback_query = CallbackQuery(
            id="123",
            from_user=user,
            chat_instance="test",
            data="test_data"
        )
        
        # Настройка мока - пользователь НЕ существует в БД
        mock_repo.get_user_by_telegram_id.return_value = None
        
        # Заглушка для handler
        handler = AsyncMock(return_value="success")
        
        # Выполнение
        result = await auth_middleware(handler, callback_query, {"handler": handler})
        
        # Проверка
        assert result is None  # Обработчик НЕ должен быть вызван
        mock_repo.get_user_by_telegram_id.assert_called_once_with(987654321)

    @pytest.mark.asyncio
    async def test_missing_user_info_message(self, auth_middleware, mock_repo):
        """Тест: обработка сообщения без информации о пользователе"""
        # Подготовка
        chat = Chat(
            id=987654321,
            type="private"
        )
        message = Message(
            message_id=1,
            date=int(datetime.now().timestamp()),
            chat=chat,
            from_user=None,  # Нет информации о пользователе
            text="/start"
        )
        
        # Заглушка для handler
        handler = AsyncMock(return_value="success")
        
        # Выполнение
        result = await auth_middleware(handler, message, {"handler": handler})
        
        # Проверка
        assert result is None  # Обработчик НЕ должен быть вызван
        mock_repo.get_user_by_telegram_id.assert_not_called()

    @pytest.mark.asyncio
    async def test_missing_user_info_callback_query(self, auth_middleware, mock_repo):
        """Тест: обработка callback запроса без информации о пользователе"""
        # Создаем мок-объект CallbackQuery с отсутствующим from_user
        callback_query = Mock()
        callback_query.from_user = None  # Нет информации о пользователе
        
        # Заглушка для handler
        handler = AsyncMock(return_value="success")
        
        # Выполнение
        result = await auth_middleware(handler, callback_query, {"handler": handler})
        
        # Проверка
        assert result is None  # Обработчик НЕ должен быть вызван
        mock_repo.get_user_by_telegram_id.assert_not_called()