import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock
from services.auth_service import AuthService
from services.repository import TransactionRepository
from aiogram import types
from handlers.admin import is_admin, admin_command_handler, set_role_command_handler
from utils.keyboards import get_main_keyboard


@pytest.fixture
def mock_repo():
    """Фикстура для создания mock репозитория"""
    repo = AsyncMock(spec=TransactionRepository)
    repo.get_user_by_telegram_id = AsyncMock(return_value=None)
    repo._get_connection = AsyncMock()
    return repo


@pytest.fixture
def mock_auth_service(mock_repo):
    """Фикстура для создания AuthService с mock репозитория"""
    service = AsyncMock(spec=AuthService)
    service.update_user_role = AsyncMock(return_value=True)
    service.get_all_users = AsyncMock(return_value=[])
    return service


@pytest.fixture
def mock_message():
    """Фикстура для создания mock сообщения"""
    message = AsyncMock(spec=types.Message)
    message.answer = AsyncMock()
    message.text = "/set_role 44995715 admin"
    return message


@pytest.fixture
def mock_data():
    """Фикстура для создания mock данных"""
    data = {
        "current_user": {"role": "admin"}
    }
    return data


@pytest.mark.asyncio
async def test_is_admin_function_with_admin_user():
    """Тест: проверка функции is_admin с админ-пользователем"""
    # Подготовка
    current_user = {"role": "admin"}

    # Выполнение и проверка
    assert is_admin(current_user) is True


@pytest.mark.asyncio
async def test_is_admin_function_with_regular_user():
    """Тест: проверка функции is_admin с обычным пользователем"""
    # Подготовка
    current_user = {"role": "user"}

    # Выполнение и проверка
    assert is_admin(current_user) is False


@pytest.mark.asyncio
async def test_is_admin_function_with_empty_user():
    """Тест: проверка функции is_admin с пустым пользователем"""
    # Подготовка
    current_user = {}

    # Выполнение и проверка
    assert is_admin(current_user) is False


@pytest.mark.asyncio
async def test_is_admin_function_with_none_user():
    """Тест: проверка функции is_admin с None пользователем"""
    # Подготовка
    current_user = None

    # Выполнение и проверка
    assert is_admin(current_user) is False


@pytest.mark.asyncio
async def test_set_role_command_handler_valid_args(mock_message, mock_data, mock_auth_service):
    """Тест: команда /set_role с корректными аргументами для назначения администратора"""
    # Подготовка
    mock_message.text = "/set_role 44995715 admin"
    mock_auth_service.update_user_role.return_value = True

    # Выполнение
    await set_role_command_handler(mock_message, mock_auth_service, mock_data["current_user"])

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
    mock_auth_service.update_user_role.assert_called_once_with(44995715, "admin")


@pytest.mark.asyncio
async def test_set_role_command_handler_invalid_args(mock_message, mock_data, mock_auth_service):
    """Тест: команда /set_role с некорректными аргументами"""
    # Подготовка
    mock_message.text = "/set_role 44995715"
    mock_auth_service.update_user_role.return_value = True

    # Выполнение
    await set_role_command_handler(mock_message, mock_auth_service, mock_data["current_user"])

    # Проверка - должно быть сообщение об ошибке формата
    mock_message.answer.assert_called_once()
    call_args = mock_message.answer.call_args
    args, kwargs = call_args
    text_content = ""
    if args:
        text_content = args[0].lower() if isinstance(args[0], str) else ""
    elif 'text' in kwargs:
        text_content = kwargs['text'].lower()
    assert "неправильный формат команды" in text_content


@pytest.mark.asyncio
async def test_set_role_command_handler_invalid_role(mock_message, mock_data, mock_auth_service):
    """Тест: команда /set_role с недопустимой ролью"""
    # Подготовка
    mock_message.text = "/set_role 44995715 superadmin"
    mock_auth_service.update_user_role.return_value = True

    # Выполнение
    await set_role_command_handler(mock_message, mock_auth_service, mock_data["current_user"])

    # Проверка - должно быть сообщение об ошибке недопустимой роли
    mock_message.answer.assert_called_once()
    call_args = mock_message.answer.call_args
    args, kwargs = call_args
    text_content = ""
    if args:
        text_content = args[0].lower() if isinstance(args[0], str) else ""
    elif 'text' in kwargs:
        text_content = kwargs['text'].lower()
    assert "недопустимая роль" in text_content


@pytest.mark.asyncio
async def test_get_main_keyboard_with_admin_flag():
    """Тест: клавиатура с админ-панелью для администратора"""
    # Выполнение
    keyboard = get_main_keyboard(is_admin=True)

    # Проверка - клавиатура должна содержать кнопку админ-панели
    keyboard_buttons = []
    for row in keyboard.keyboard:
        for button in row:
            keyboard_buttons.append(button.text)

    assert "🛡️ Админ-панель" in keyboard_buttons


@pytest.mark.asyncio
async def test_get_main_keyboard_without_admin_flag():
    """Тест: клавиатура без админ-панели для обычного пользователя"""
    # Выполнение
    keyboard = get_main_keyboard(is_admin=False)

    # Проверка - клавиатура не должна содержать кнопку админ-панели
    keyboard_buttons = []
    for row in keyboard.keyboard:
        for button in row:
            keyboard_buttons.append(button.text)

    assert "🛡️ Админ-панель" not in keyboard_buttons


@pytest.mark.asyncio
async def test_admin_command_handler_access_denied_for_regular_user(mock_message, mock_data, mock_auth_service):
    """Тест: команда /admin недоступна обычному пользователю"""
    # Подготовка
    mock_data_copy = mock_data.copy()
    mock_data_copy["current_user"]["role"] = "user"

    # Выполнение
    await admin_command_handler(mock_message, mock_auth_service, mock_data_copy["current_user"])

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
async def test_admin_command_handler_access_granted_for_admin(mock_message, mock_data, mock_auth_service):
    """Тест: команда /admin доступна администратору"""
    # Подготовка
    mock_data_copy = mock_data.copy()

    # Выполнение
    await admin_command_handler(mock_message, mock_auth_service, mock_data_copy["current_user"])

    # Проверка
    # Должно быть 2 вызова: один для меню администратора, второй для клавиатуры
    assert mock_message.answer.call_count >= 1
    call_args = mock_message.answer.call_args_list[0]
    args, kwargs = call_args
    text_content = ""
    if args:
        text_content = args[0].lower() if isinstance(args[0], str) else ""
    elif 'text' in kwargs:
        text_content = kwargs['text'].lower()
    assert "панель администратора" in text_content