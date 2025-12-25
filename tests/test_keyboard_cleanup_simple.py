import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from aiogram.types import Message, User, Chat, BotCommand
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from handlers.transactions import handle_category_selection
from aiogram import types


async def test_handle_category_selection_with_mocking():
    """Простой тест для проверки работы handle_category_selection с моками"""
    
    # Создаем полноценные моки
    mock_user = User(id=123456789, is_bot=False, first_name="Test User")
    mock_chat = Chat(id=123456789, type="private")
    
    # Создаем мок сообщения
    mock_message = MagicMock(spec=Message)
    mock_message.text = "Продукты"
    mock_message.from_user = mock_user
    mock_message.chat = mock_chat
    mock_message.answer = AsyncMock()
    
    # Создаем бота
    mock_message.bot = MagicMock()
    mock_message.bot.id = 987654321
    
    # Создаем FSMContext с MemoryStorage
    storage = MemoryStorage()
    state = FSMContext(storage, key=(123456789, 123456789))
    
    # Устанавливаем данные состояния
    await state.update_data({
        'amount': 100.0,
        'description': 'покупка в магазине',
        'comment': 'покупка в магазине'
    })
    
    # Мокаем TransactionService
    with patch('handlers.transactions.get_transaction_service') as mock_get_service:
        mock_service = AsyncMock()
        mock_service.finalize_transaction.return_value = {'success': True, 'summary': 'Транзакция сохранена'}
        mock_service.classifier = MagicMock()
        mock_service.classifier.learn_keyword = MagicMock()
        mock_get_service.return_value = mock_service
        
        # Мокаем CATEGORY_STORAGE
        with patch('handlers.transactions.CATEGORY_STORAGE') as mock_category_storage:
            mock_category_storage.expense = ['Продукты', 'Транспорт', 'Развлечения', 'Прочее Расход']
            
            # Мокаем clean_previous_kb
            with patch('handlers.transactions.clean_previous_kb') as mock_clean_kb:
                mock_clean_kb.return_value = AsyncMock()
                
                # Вызываем функцию
                await handle_category_selection(mock_message, state)
                
                # Проверяем, что clean_previous_kb был вызван
                mock_clean_kb.assert_called_once()
                
                # Проверяем, что было отправлено сообщение
                assert mock_message.answer.called
                
                # Проверяем, что состояние было очищено
                current_data = await state.get_data()
                assert current_data == {}  # После вызова state.clear() данные должны быть пустыми
    
    print("Тест успешно пройден: clean_previous_kb был вызван при успешной обработке категории")


async def test_handle_category_selection_error_path():
    """Тест для проверки вызова clean_previous_kb при ошибке записи транзакции"""
    
    # Создаем полноценные моки
    mock_user = User(id=123456789, is_bot=False, first_name="Test User")
    mock_chat = Chat(id=123456789, type="private")
    
    # Создаем мок сообщения
    mock_message = MagicMock(spec=Message)
    mock_message.text = "Продукты"
    mock_message.from_user = mock_user
    mock_message.chat = mock_chat
    mock_message.answer = AsyncMock()
    
    # Создаем бота
    mock_message.bot = MagicMock()
    mock_message.bot.id = 987654321
    
    # Создаем FSMContext с MemoryStorage
    storage = MemoryStorage()
    state = FSMContext(storage, key=(123456789, 123456789))
    
    # Устанавливаем данные состояния
    await state.update_data({
        'amount': 100.0,
        'description': 'покупка в магазине',
        'comment': 'покупка в магазине'
    })
    
    # Мокаем TransactionService для возврата ошибки
    with patch('handlers.transactions.get_transaction_service') as mock_get_service:
        mock_service = AsyncMock()
        mock_service.finalize_transaction.return_value = {'success': False, 'error': 'Ошибка при записи'}
        mock_service.classifier = MagicMock()
        mock_service.classifier.learn_keyword = MagicMock()
        mock_get_service.return_value = mock_service
        
        # Мокаем CATEGORY_STORAGE
        with patch('handlers.transactions.CATEGORY_STORAGE') as mock_category_storage:
            mock_category_storage.expense = ['Продукты', 'Транспорт', 'Развлечения', 'Прочее Расход']
            
            # Мокаем clean_previous_kb
            with patch('handlers.transactions.clean_previous_kb') as mock_clean_kb:
                mock_clean_kb.return_value = AsyncMock()
                
                # Вызываем функцию
                await handle_category_selection(mock_message, state)
                
                # Проверяем, что clean_previous_kb был вызван даже при ошибке
                mock_clean_kb.assert_called_once()
                
                # Проверяем, что было отправлено сообщение об ошибке
                assert mock_message.answer.called
    
    print("Тест успешно пройден: clean_previous_kb был вызван даже при ошибке записи транзакции")


if __name__ == "__main__":
    # Запускаем тесты
    asyncio.run(test_handle_category_selection_with_mocking())
    asyncio.run(test_handle_category_selection_error_path())
    print("Все тесты пройдены успешно!")