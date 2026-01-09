import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from aiogram import Dispatcher
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, User, Chat
from aiogram.methods import SendMessage, EditMessageText, AnswerCallbackQuery
from services.auth_service import AuthService
from services.repository import TransactionRepository
from handlers.admin import AdminPanel, admin_callback_handler, is_admin
from utils.states import AdminStates


@pytest.mark.asyncio
class TestInteractiveAdminPanel:
    """Тесты для интерактивной админ-панели с FSM"""

    @pytest.fixture
    def mock_user_admin(self):
        """Создает mock администратора"""
        user = User(id=44995715, is_bot=False, first_name="Admin", username="admin")
        return user

    @pytest.fixture
    def mock_user_regular(self):
        """Создает mock обычного пользователя"""
        user = User(id=987654321, is_bot=False, first_name="Regular", username="regular")
        return user

    @pytest.fixture
    def mock_auth_service(self):
        """Создает mock AuthService"""
        auth_service = AsyncMock(spec=AuthService)
        return auth_service

    @pytest.fixture
    def fsm_context(self):
        """Создает mock FSMContext"""
        context = AsyncMock(spec=FSMContext)
        context.get_state = AsyncMock(return_value=None)
        context.set_state = AsyncMock()
        context.clear = AsyncMock()
        context.update_data = AsyncMock()
        context.get_data = AsyncMock(return_value={})
        return context

    @pytest.fixture
    def mock_message(self):
        """Создает mock сообщения"""
        message = AsyncMock()
        message.chat.id = 123456789
        message.from_user = AsyncMock()
        message.from_user.id = 123456789
        message.answer = AsyncMock()
        return message

    @pytest.fixture
    def mock_callback_query(self):
        """Создает mock callback query"""
        callback_query = AsyncMock()
        callback_query.from_user = AsyncMock()
        callback_query.from_user.id = 123456789
        callback_query.message = AsyncMock()
        callback_query.message.edit_text = AsyncMock()
        callback_query.message.chat.id = 123456789
        callback_query.message.answer = AsyncMock()
        callback_query.answer = AsyncMock()
        callback_query.data = "test_data"
        callback_query.bot = AsyncMock()
        callback_query.bot.send_message = AsyncMock()
        return callback_query

    async def test_admin_command_starts_fsm_for_admin_user(self, mock_message, mock_auth_service, fsm_context):
        """Тест: команда /admin запускает FSM и показывает главное меню админ-панели для администратора"""
        # Arrange
        current_user = {"role": "admin"}

        # Act
        await AdminPanel.admin_menu(mock_message, fsm_context, mock_auth_service, current_user)

        # Assert
        fsm_context.set_state.assert_called_once_with(AdminStates.main_menu)
        mock_message.answer.assert_called()

    async def test_admin_command_denies_access_for_regular_user(self, mock_message, mock_auth_service, fsm_context):
        """Тест: команда /admin отклоняется для обычного пользователя"""
        # Arrange
        current_user = {"role": "user"}

        # Act
        await AdminPanel.admin_menu(mock_message, fsm_context, mock_auth_service, current_user)

        # Assert
        # Проверяем, что FSM состояние не было установлено
        fsm_context.set_state.assert_not_called()
        # Проверяем, что было отправлено сообщение об ошибке
        mock_message.answer.assert_called_once()
        args, kwargs = mock_message.answer.call_args
        assert "доступ запрещен" in args[0].lower()

    async def test_main_menu_shows_correct_buttons(self, mock_message, mock_auth_service, fsm_context):
        """Тест: главное меню админ-панели показывает корректные кнопки"""
        # Arrange
        current_user = {"role": "admin"}

        # Act
        await AdminPanel.admin_menu(mock_message, fsm_context, mock_auth_service, current_user)

        # Assert
        # Проверяем, что было вызвано ответное сообщение
        assert mock_message.answer.call_count >= 1

    async def test_manage_users_submenu_transition(self, mock_callback_query, mock_auth_service, fsm_context):
        """Тест: переход в подменю управления пользователями"""
        # Arrange
        current_user = {"role": "admin"}
        mock_callback_query.data = "manage_users"
        
        # Act
        await AdminPanel.manage_users(mock_callback_query, fsm_context)

        # Assert
        fsm_context.set_state.assert_called_once_with(AdminStates.users_menu)

    async def test_view_statistics_submenu_transition(self, mock_callback_query, mock_auth_service, fsm_context):
        """Тест: переход в подменю просмотра статистики"""
        # Arrange
        current_user = {"role": "admin"}
        mock_callback_query.data = "view_stats"
        
        # Act
        await AdminPanel.view_statistics(mock_callback_query, fsm_context)

        # Assert
        fsm_context.set_state.assert_called_once_with(AdminStates.stats_menu)

    async def test_cancel_admin_session(self, mock_callback_query, mock_auth_service, fsm_context):
        """Тест: отмена сессии админ-панели возвращает в исходное состояние"""
        # Arrange
        current_user = {"role": "admin"}
        mock_callback_query.data = "cancel_admin"
        
        # Act
        await AdminPanel.cancel_admin_session(mock_callback_query, fsm_context)

        # Assert
        fsm_context.clear.assert_called_once()

    async def test_fsm_state_validation(self):
        """Тест: проверка корректности определения FSM состояний"""
        # Проверяем, что все необходимые состояния определены в AdminStates
        assert hasattr(AdminStates, 'main_menu')
        assert hasattr(AdminStates, 'users_menu')
        assert hasattr(AdminStates, 'stats_menu')
        assert hasattr(AdminStates, 'reports_menu')
        assert hasattr(AdminStates, 'settings_menu')

    async def test_is_admin_function_with_admin_user(self):
        """Тест: функция is_admin правильно определяет администратора"""
        # Arrange
        current_user = {"role": "admin"}
        
        # Act
        result = is_admin(current_user)
        
        # Assert
        assert result is True

    async def test_is_admin_function_with_regular_user(self):
        """Тест: функция is_admin правильно определяет обычного пользователя"""
        # Arrange
        current_user = {"role": "user"}
        
        # Act
        result = is_admin(current_user)
        
        # Assert
        assert result is False

    async def test_is_admin_function_with_empty_user(self):
        """Тест: функция is_admin возвращает False для пустого пользователя"""
        # Act
        result = is_admin(None)
        
        # Assert
        assert result is False

    async def test_admin_callback_handler_with_manage_users_action(self, mock_callback_query, mock_auth_service, fsm_context):
        """Тест: обработчик callback'а для действия управления пользователями"""
        # Arrange
        current_user = {"role": "admin"}
        mock_callback_query.data = "manage_users"
        
        # Act
        await admin_callback_handler(mock_callback_query, fsm_context, mock_auth_service, current_user)

        # Assert
        # Проверяем, что было изменено состояние на users_menu
        fsm_context.set_state.assert_called_once_with(AdminStates.users_menu)

    async def test_admin_callback_handler_with_unauthorized_user(self, mock_callback_query, mock_auth_service, fsm_context):
        """Тест: обработчик callback'а отклоняет неавторизованного пользователя"""
        # Arrange
        current_user = {"role": "user"}
        mock_callback_query.data = "manage_users"
        
        # Act
        await admin_callback_handler(mock_callback_query, fsm_context, mock_auth_service, current_user)

        # Assert
        # Проверяем, что было показано предупреждение
        mock_callback_query.answer.assert_called_once()
        args, kwargs = mock_callback_query.answer.call_args
        assert kwargs.get('show_alert') is True
        assert "доступ запрещен" in args[0].lower()

    async def test_admin_callback_handler_with_view_stats_action(self, mock_callback_query, mock_auth_service, fsm_context):
        """Тест: обработчик callback'а для действия просмотра статистики"""
        # Arrange
        current_user = {"role": "admin"}
        mock_callback_query.data = "view_stats"
        
        # Act
        await admin_callback_handler(mock_callback_query, fsm_context, mock_auth_service, current_user)

        # Assert
        # Проверяем, что было изменено состояние на stats_menu
        fsm_context.set_state.assert_called_once_with(AdminStates.stats_menu)

    async def test_admin_callback_handler_with_cancel_action(self, mock_callback_query, mock_auth_service, fsm_context):
        """Тест: обработчик callback'а для действия отмены"""
        # Arrange
        current_user = {"role": "admin"}
        mock_callback_query.data = "cancel_admin"
        
        # Act
        await admin_callback_handler(mock_callback_query, fsm_context, mock_auth_service, current_user)

        # Assert
        # Проверяем, что состояние было очищено
        fsm_context.clear.assert_called_once()