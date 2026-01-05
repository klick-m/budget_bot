import pytest
from unittest.mock import AsyncMock, Mock, patch
from aiogram import Router, types
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, User, Chat
from aiogram.methods import SendMessage, EditMessageText, AnswerCallbackQuery
from handlers.common import undo_callback_handler, close_undo_handler
from handlers.receipts import handle_photo
from handlers.manual import confirm_manual_transaction
from handlers.smart_input import confirm_smart_transaction
from models.transaction import TransactionData
from services.transaction_service import TransactionService
from datetime import datetime


class TestErrorHandler:
    """Тесты для проверки обработки ошибок в хендлерах"""
    
    @pytest.mark.asyncio
    async def test_undo_callback_handler_with_service_error(self):
        """Тест: undo_callback_handler корректно обрабатывает ошибки сервиса"""
        # Создаем mock callback
        callback = Mock(spec=CallbackQuery)
        callback.data = "undo_2023-01-01_12:00:00_100.0"
        callback.from_user = Mock()
        callback.from_user.id = 123456
        callback.message = Mock()
        callback.message.edit_text = AsyncMock()
        callback.message.chat = Mock()
        callback.message.chat.id = 123456
        callback.message.message_id = 123
        callback.answer = AsyncMock()
        callback.bot = Mock()
        
        # Мокаем edit_or_send
        with patch('handlers.common.edit_or_send') as mock_edit_or_send:
            # Создаем мок-сервис, который вернет None при вызове delete_transaction_by_details
            mock_service = Mock(spec=TransactionService)
            mock_service.delete_transaction_by_details = AsyncMock(return_value=None)
            
            # Вызываем хендлер с мок-сервисом
            await undo_callback_handler(callback, mock_service)
            
            # Проверяем, что edit_or_send был вызван с правильными параметрами
            mock_edit_or_send.assert_called()
            # Проверяем, что хотя бы один из вызовов содержит нужный текст
            calls = mock_edit_or_send.call_args_list
            found_correct_call = False
            for call in calls:
                args, kwargs = call
                if len(args) >= 3 and "❌ Ошибка при удалении транзакции:" in args[2]:  # text аргумент
                    found_correct_call = True
                    break
            assert found_correct_call, "edit_or_send должен быть вызван с правильным текстом ошибки"
    
    @pytest.mark.asyncio
    async def test_undo_callback_handler_with_exception(self):
        """Тест: undo_callback_handler корректно обрабатывает исключения"""
        # Создаем mock callback
        callback = Mock(spec=CallbackQuery)
        callback.data = "undo_2023-01-01_12:00:00_100.0"
        callback.from_user = Mock()
        callback.from_user.id = 123456
        callback.message = Mock()
        callback.message.edit_text = AsyncMock()
        callback.message.chat = Mock()
        callback.message.chat.id = 123456
        callback.message.message_id = 123
        callback.answer = AsyncMock()
        callback.bot = Mock()
        
        # Мокаем edit_or_send
        with patch('handlers.common.edit_or_send') as mock_edit_or_send:
            # Мокаем TransactionService, чтобы он выбрасывал исключение
            mock_service = Mock(spec=TransactionService)
            mock_service.delete_transaction_by_details = AsyncMock(side_effect=Exception("Database connection failed"))
            
            # Вызываем хендлер с мок-сервисом
            await undo_callback_handler(callback, mock_service)
            
            # Проверяем, что edit_or_send был вызван с правильными параметрами
            mock_edit_or_send.assert_called()
            # Проверяем, что хотя бы один из вызовов содержит нужный текст
            calls = mock_edit_or_send.call_args_list
            found_correct_call = False
            for call in calls:
                args, kwargs = call
                if len(args) >= 3 and "❌ Ошибка при удалении транзакции: Database connection failed" in args[2]:  # text аргумент
                    found_correct_call = True
                    break
            assert found_correct_call, "edit_or_send должен быть вызван с правильным текстом ошибки"
    
    @pytest.mark.asyncio
    async def test_close_undo_handler_with_delete_error(self):
        """Тест: close_undo_handler корректно обрабатывает ошибки при удалении сообщения"""
        # Создаем mock callback
        callback = Mock(spec=CallbackQuery)
        callback.message = Mock()
        callback.message.delete = AsyncMock(side_effect=Exception("Message to delete not found"))
        callback.message.edit_text = AsyncMock()
        callback.message.chat = Mock()
        callback.message.chat.id = 123456
        callback.message.message_id = 123
        callback.answer = AsyncMock()
        callback.bot = Mock()
        
        # Мокаем edit_or_send
        with patch('handlers.common.edit_or_send') as mock_edit_or_send:
            # Вызываем хендлер
            await close_undo_handler(callback)
            
            # Проверяем, что edit_or_send был вызван с правильными параметрами
            mock_edit_or_send.assert_called()
            # Может быть вызван несколько раз, проверим хотя бы один вызов
            calls = mock_edit_or_send.call_args_list
            found_correct_call = False
            for call in calls:
                args, kwargs = call
                if len(args) >= 3 and "🗑 Меню отмены транзакций закрыто." in args[2]:  # text аргумент
                    found_correct_call = True
                    break
            assert found_correct_call, "edit_or_send должен быть вызван с правильным текстом"
    
    @pytest.mark.asyncio
    async def test_handle_photo_with_invalid_file_size(self):
        """Тест: handle_photo корректно обрабатывает слишком большой файл"""
        # Создаем mock message
        message = Mock(spec=Message)
        message.photo = [Mock()]
        message.photo[0].file_size = 10 * 1024 * 1024  # 10 MB - больше 5 MB лимита
        message.from_user = Mock()
        message.from_user.username = "test_user"
        message.from_user.full_name = "Test User"
        message.answer = AsyncMock()
        message.bot = Mock()
        
        # Создаем мок-сервис
        mock_service = Mock(spec=TransactionService)
        
        # Вызываем хендлер
        state = Mock(spec=FSMContext)
        state.clear = AsyncMock()
        
        await handle_photo(message, state, mock_service)
        
        # Проверяем, что было отправлено сообщение об ошибке
        message.answer.assert_called_once()
        args, kwargs = message.answer.call_args
        assert "❌ Размер изображения слишком большой" in args[0]
    
    @pytest.mark.asyncio
    async def test_confirm_manual_transaction_with_service_error(self):
        """Тест: confirm_manual_transaction корректно обрабатывает ошибки сервиса"""
        # Создаем mock callback
        callback = Mock(spec=CallbackQuery)
        callback.message = Mock()
        callback.message.edit_text = AsyncMock()
        callback.message.chat = Mock()
        callback.message.chat.id = 123456
        callback.message.message_id = 123
        callback.answer = AsyncMock()
        callback.bot = Mock()
        
        # Мокаем FSM state
        state = Mock(spec=FSMContext)
        state.get_data = AsyncMock(return_value={
            'transaction_data': TransactionData(
                type='Расход',
                category='Продукты',
                amount=10.0,
                comment='Тест',
                username='test_user',
                transaction_dt=datetime.now()
            )
        })
        
        # Мокаем edit_or_send
        with patch('handlers.manual.edit_or_send') as mock_edit_or_send:
            # Создаем мок-сервис, который выбросит исключение
            mock_service = Mock(spec=TransactionService)
            mock_service.finalize_transaction = AsyncMock(side_effect=Exception("Service not initialized"))
            
            # Вызываем хендлер с мок-сервисом
            await confirm_manual_transaction(callback, state, mock_service)
            
            # Проверяем, что edit_or_send был вызван хотя бы один раз
            # (в случае ошибки сервиса должно быть как минимум 1 обращение к edit_or_send)
            assert mock_edit_or_send.call_count >= 1, "edit_or_send должен быть вызван хотя бы один раз"
    
    @pytest.mark.asyncio
    async def test_confirm_manual_transaction_with_exception(self):
        """Тест: confirm_manual_transaction корректно обрабатывает исключения при сохранении"""
        # Создаем mock callback
        callback = Mock(spec=CallbackQuery)
        callback.message = Mock()
        callback.message.edit_text = AsyncMock()
        callback.message.chat = Mock()
        callback.message.chat.id = 123456
        callback.message.message_id = 123
        callback.answer = AsyncMock()
        callback.bot = Mock()
        
        # Мокаем FSM state
        state = Mock(spec=FSMContext)
        state.get_data = AsyncMock(return_value={
            'transaction_data': TransactionData(
                type='Расход',
                category='Продукты',
                amount=100.0,
                comment='Тест',
                username='test_user',
                transaction_dt=datetime.now()
            )
        })
        
        # Мокаем edit_or_send
        with patch('handlers.manual.edit_or_send') as mock_edit_or_send:
            # Мокаем TransactionService
            mock_service = Mock(spec=TransactionService)
            mock_service.finalize_transaction = AsyncMock(side_effect=Exception("Network error"))
            
            # Вызываем хендлер с мок-сервисом
            await confirm_manual_transaction(callback, state, mock_service)
            
            # Проверяем, что edit_or_send был вызван с правильными параметрами
            mock_edit_or_send.assert_called()
            # Проверяем, что хотя бы один из вызовов содержит нужный текст
            calls = mock_edit_or_send.call_args_list
            found_correct_call = False
            for call in calls:
                args, kwargs = call
                if len(args) >= 3 and (
                    "❌ **Ошибка при сохранении транзакции:** Network error" in args[2] or
                    "❌ **Критическая ошибка:**" in args[2]
                ):  # text аргумент
                    found_correct_call = True
                    break
            assert found_correct_call, "edit_or_send должен быть вызван с правильным текстом ошибки"
    
    @pytest.mark.asyncio
    async def test_confirm_smart_transaction_with_service_error(self):
        """Тест: confirm_smart_transaction корректно обрабатывает ошибки сервиса"""
        # Создаем mock callback
        callback = Mock(spec=CallbackQuery)
        callback.message = Mock()
        callback.message.edit_text = AsyncMock()
        callback.message.chat = Mock()
        callback.message.chat.id = 123456
        callback.message.message_id = 123
        callback.answer = AsyncMock()
        callback.bot = Mock()
        
        # Мокаем FSM state
        state = Mock(spec=FSMContext)
        state.get_data = AsyncMock(return_value={
            'transaction_data': TransactionData(
                type='Расход',
                category='Продукты',
                amount=10.0,
                comment='Тест',
                username='test_user',
                transaction_dt=datetime.now()
            )
        })
        
        # Мокаем edit_or_send
        with patch('handlers.smart_input.edit_or_send') as mock_edit_or_send:
            # Создаем мок-сервис, который выбросит исключение
            mock_service = Mock(spec=TransactionService)
            mock_service.finalize_transaction = AsyncMock(side_effect=Exception("Service not initialized"))
            
            # Вызываем хендлер с мок-сервисом
            await confirm_smart_transaction(callback, state, mock_service)
            
            # Проверяем, что edit_or_send был вызван хотя бы один раз
            # (в случае ошибки сервиса должно быть как минимум 1 обращение к edit_or_send)
            assert mock_edit_or_send.call_count >= 1, "edit_or_send должен быть вызван хотя бы один раз"
    
    @pytest.mark.asyncio
    async def test_confirm_smart_transaction_with_exception(self):
        """Тест: confirm_smart_transaction корректно обрабатывает исключения при сохранении"""
        # Создаем mock callback
        callback = Mock(spec=CallbackQuery)
        callback.message = Mock()
        callback.message.edit_text = AsyncMock()
        callback.message.chat = Mock()
        callback.message.chat.id = 123456
        callback.message.message_id = 123
        callback.answer = AsyncMock()
        callback.bot = Mock()
        
        # Мокаем FSM state
        state = Mock(spec=FSMContext)
        state.get_data = AsyncMock(return_value={
            'transaction_data': TransactionData(
                type='Расход',
                category='Продукты',
                amount=10.0,
                comment='Тест',
                username='test_user',
                transaction_dt=datetime.now()
            )
        })
        
        # Мокаем edit_or_send
        with patch('handlers.smart_input.edit_or_send') as mock_edit_or_send:
            # Мокаем TransactionService
            mock_service = Mock(spec=TransactionService)
            mock_service.finalize_transaction = AsyncMock(side_effect=Exception("API error"))
            
            # Вызываем хендлер с мок-сервисом
            await confirm_smart_transaction(callback, state, mock_service)
            
            # Проверяем, что edit_or_send был вызван с правильными параметрами
            mock_edit_or_send.assert_called()
            # Проверяем, что хотя бы один из вызовов содержит нужный текст
            calls = mock_edit_or_send.call_args_list
            found_correct_call = False
            for call in calls:
                args, kwargs = call
                if len(args) >= 3 and (
                    "❌ **Ошибка при сохранении транзакции:** API error" in args[2] or
                    "❌ **Критическая ошибка:**" in args[2]
                ):  # text аргумент
                    found_correct_call = True
                    break
            assert found_correct_call, "edit_or_send должен быть вызван с правильным текстом ошибки"