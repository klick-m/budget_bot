import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from aiogram import types
from aiogram.fsm.context import FSMContext
from services.auth_service import AuthService
from handlers.admin import (
    admin_command_handler,
    add_user_command_handler,
    remove_user_command_handler,
    set_role_command_handler,
    list_users_command_handler,
    is_admin
)


@pytest.fixture
def mock_auth_service():
    """Создает mock AuthService для тестов."""
    service = AsyncMock(spec=AuthService)
    service.get_user_by_telegram_id = AsyncMock()
    service.create_user = AsyncMock()
    service.delete_user = AsyncMock()
    service.update_user_role = AsyncMock()
    service.get_all_users = AsyncMock()
    return service


@pytest.fixture
def mock_message():
    """Создает mock сообщение."""
    message = AsyncMock(spec=types.Message)
    message.from_user = types.User(id=123456789, is_bot=False, first_name="Test Admin")
    message.chat = types.Chat(id=123456789, type="private")
    message.answer = AsyncMock()
    message.text = "/admin"
    return message


@pytest.fixture
def mock_callback():
    """Создает mock callback запрос."""
    callback = AsyncMock(spec=types.CallbackQuery)
    callback.from_user = types.User(id=123456789, is_bot=False, first_name="Test Admin")
    callback.message = AsyncMock()
    callback.message.answer = AsyncMock()
    callback.answer = AsyncMock()
    return callback


@pytest.fixture
def mock_data():
    """Создает mock данных для хендлера."""
    return {
        "current_user": {
            "id": 1,
            "telegram_id": 123456789,
            "username": "test_admin",
            "role": "admin",
            "monthly_limit": 10000.0
        }
    }


class TestAdminCommands:
    """Тесты для административных команд."""

    @pytest.mark.asyncio
    async def test_is_admin_with_admin_user(self):
        """Тест: проверка администратора с админ-пользователем."""
        # Подготовка
        current_user = {"role": "admin"}
        
        # Выполнение и проверка
        assert is_admin(current_user) is True

    @pytest.mark.asyncio
    async def test_is_admin_with_regular_user(self):
        """Тест: проверка администратора с обычным пользователем."""
        # Подготовка
        current_user = {"role": "user"}
        
        # Выполнение и проверка
        assert is_admin(current_user) is False

    @pytest.mark.asyncio
    async def test_is_admin_with_no_user(self):
        """Тест: проверка администратора без пользователя."""
        # Подготовка
        current_user = None
        
        # Выполнение и проверка
        assert is_admin(current_user) is False

    @pytest.mark.asyncio
    async def test_admin_command_handler_as_admin(self, mock_message, mock_data, mock_auth_service):
        """Тест: команда /admin для администратора."""
        # Подготовка
        mock_data_copy = mock_data.copy()

        # Выполнение
        await admin_command_handler(mock_message, mock_data_copy, mock_auth_service)

        # Проверка
        mock_message.answer.assert_called_once()
        call_args = mock_message.answer.call_args
        # Проверяем аргументы вызова - текст может быть как позиционным, так и именованным аргументом
        args, kwargs = call_args
        text_content = ""
        if args:
            text_content = args[0].lower() if isinstance(args[0], str) else ""
        elif 'text' in kwargs:
            text_content = kwargs['text'].lower()
        assert "панель администратора" in text_content

    @pytest.mark.asyncio
    async def test_admin_command_handler_as_regular_user(self, mock_message, mock_data, mock_auth_service):
        """Тест: команда /admin для обычного пользователя."""
        # Подготовка
        mock_data_copy = mock_data.copy()
        mock_data_copy["current_user"]["role"] = "user"

        # Выполнение
        await admin_command_handler(mock_message, mock_data_copy, mock_auth_service)

        # Проверка
        mock_message.answer.assert_called_once()
        call_args = mock_message.answer.call_args
        # Проверяем аргументы вызова - текст может быть как позиционным, так и именованным аргументом
        args, kwargs = call_args
        text_content = ""
        if args:
            text_content = args[0].lower() if isinstance(args[0], str) else ""
        elif 'text' in kwargs:
            text_content = kwargs['text'].lower()
        assert "доступ запрещен" in text_content

    @pytest.mark.asyncio
    async def test_add_user_command_handler_valid_args(self, mock_message, mock_data, mock_auth_service):
        """Тест: команда /add_user с корректными аргументами."""
        # Подготовка
        mock_message.text = "/add_user 987654321 newuser admin 5000.0"
        mock_auth_service.create_user.return_value = MagicMock(
            telegram_id=987654321,
            username="newuser",
            role="admin",
            monthly_limit=5000.0
        )

        # Выполнение
        await add_user_command_handler(mock_message, mock_data, mock_auth_service)

        # Проверка
        mock_message.answer.assert_called_once()
        call_args = mock_message.answer.call_args
        # Проверяем аргументы вызова - текст может быть как позиционным, так и именованным аргументом
        args, kwargs = call_args
        text_content = ""
        if args:
            text_content = args[0].lower() if isinstance(args[0], str) else ""
        elif 'text' in kwargs:
            text_content = kwargs['text'].lower()
        assert "успешно добавлен" in text_content
        mock_auth_service.create_user.assert_called_once_with(
            telegram_id=987654321,
            username="newuser",
            role="admin",
            monthly_limit=5000.0
        )

    @pytest.mark.asyncio
    async def test_add_user_command_handler_invalid_args(self, mock_message, mock_data, mock_auth_service):
        """Тест: команда /add_user с некорректными аргументами."""
        # Подготовка
        mock_message.text = "/add_user invalid_args"

        # Выполнение
        await add_user_command_handler(mock_message, mock_data, mock_auth_service)

        # Проверка
        mock_message.answer.assert_called_once()
        call_args = mock_message.answer.call_args
        # Проверяем аргументы вызова - текст может быть как позиционным, так и именованным аргументом
        args, kwargs = call_args
        text_content = ""
        if args:
            text_content = args[0].lower() if isinstance(args[0], str) else ""
        elif 'text' in kwargs:
            text_content = kwargs['text'].lower()
        assert "неправильный формат" in text_content

    @pytest.mark.asyncio
    async def test_remove_user_command_handler_valid_args(self, mock_message, mock_data, mock_auth_service):
        """Тест: команда /remove_user с корректными аргументами."""
        # Подготовка
        mock_message.text = "/remove_user 987654321"
        mock_auth_service.delete_user.return_value = True

        # Выполнение
        await remove_user_command_handler(mock_message, mock_data, mock_auth_service)

        # Проверка
        mock_message.answer.assert_called_once()
        call_args = mock_message.answer.call_args
        # Проверяем аргументы вызова - текст может быть как позиционным, так и именованным аргументом
        args, kwargs = call_args
        text_content = ""
        if args:
            text_content = args[0].lower() if isinstance(args[0], str) else ""
        elif 'text' in kwargs:
            text_content = kwargs['text'].lower()
        assert "успешно удален" in text_content
        mock_auth_service.delete_user.assert_called_once_with(987654321)

    @pytest.mark.asyncio
    async def test_remove_user_command_handler_invalid_args(self, mock_message, mock_data, mock_auth_service):
        """Тест: команда /remove_user с некорректными аргументами."""
        # Подготовка
        mock_message.text = "/remove_user invalid"

        # Выполнение
        await remove_user_command_handler(mock_message, mock_data, mock_auth_service)

        # Проверка
        mock_message.answer.assert_called_once()
        call_args = mock_message.answer.call_args
        # Проверяем аргументы вызова - текст может быть как позиционным, так и именованным аргументом
        args, kwargs = call_args
        text_content = ""
        if args:
            text_content = args[0].lower() if isinstance(args[0], str) else ""
        elif 'text' in kwargs:
            text_content = kwargs['text'].lower()
        assert "неправильный формат" in text_content

    @pytest.mark.asyncio
    async def test_set_role_command_handler_valid_args(self, mock_message, mock_data, mock_auth_service):
        """Тест: команда /set_role с корректными аргументами."""
        # Подготовка
        mock_message.text = "/set_role 987654321 admin"
        mock_auth_service.update_user_role.return_value = True

        # Выполнение
        await set_role_command_handler(mock_message, mock_data, mock_auth_service)

        # Проверка
        mock_message.answer.assert_called_once()
        call_args = mock_message.answer.call_args
        # Проверяем аргументы вызова - текст может быть как позиционным, так и именованным аргументом
        args, kwargs = call_args
        text_content = ""
        if args:
            text_content = args[0].lower() if isinstance(args[0], str) else ""
        elif 'text' in kwargs:
            text_content = kwargs['text'].lower()
        assert "успешно обновлена" in text_content
        mock_auth_service.update_user_role.assert_called_once_with(987654321, "admin")

    @pytest.mark.asyncio
    async def test_set_role_command_handler_invalid_args(self, mock_message, mock_data, mock_auth_service):
        """Тест: команда /set_role с некорректными аргументами."""
        # Подготовка
        mock_message.text = "/set_role invalid_role"

        # Выполнение
        await set_role_command_handler(mock_message, mock_data, mock_auth_service)

        # Проверка
        mock_message.answer.assert_called_once()
        call_args = mock_message.answer.call_args
        # Проверяем аргументы вызова - текст может быть как позиционным, так и именованным аргументом
        args, kwargs = call_args
        text_content = ""
        if args:
            text_content = args[0].lower() if isinstance(args[0], str) else ""
        elif 'text' in kwargs:
            text_content = kwargs['text'].lower()
        assert "неправильный формат" in text_content

    @pytest.mark.asyncio
    async def test_list_users_command_handler(self, mock_message, mock_data, mock_auth_service):
        """Тест: команда /list_users."""
        # Подготовка
        from models.user import User
        mock_users = [
            User(id=1, telegram_id=123456789, username="admin", role="admin", monthly_limit=10000.0),
            User(id=2, telegram_id=987654321, username="user", role="user", monthly_limit=5000.0)
        ]
        mock_auth_service.get_all_users.return_value = mock_users

        # Выполнение
        await list_users_command_handler(mock_message, mock_data, mock_auth_service)

        # Проверка
        mock_message.answer.assert_called_once()
        call_args = mock_message.answer.call_args
        # Проверяем аргументы вызова - текст может быть как позиционным, так и именованным аргументом
        args, kwargs = call_args
        text_content = ""
        if args:
            text_content = args[0] if isinstance(args[0], str) else ""
        elif 'text' in kwargs:
            text_content = kwargs['text']
        assert "admin" in text_content
        assert "user" in text_content
        assert str(123456789) in text_content
        assert str(987654321) in text_content
        mock_auth_service.get_all_users.assert_called_once()