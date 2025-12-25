# -*- coding: utf-8 -*-
"""
Тесты для проверки обработки исключений в различных компонентах бота
"""
import pytest
import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, patch, MagicMock
import traceback

from models.transaction import CheckData
from services.transaction_service import TransactionService
from sheets.client import get_latest_transactions


class TestExceptionHandling:
    """Тесты для проверки обработки исключений"""

    def test_check_data_transaction_datetime_value_error_logging(self):
        """Тест: Проверка логирования ValueError при парсинге даты в CheckData"""
        import logging
        from io import StringIO
        
        # Создаем буфер для захвата логов
        log_capture = StringIO()
        handler = logging.StreamHandler(log_capture)
        handler.setLevel(logging.WARNING)
        
        # Получаем логгер, который используется в модуле
        logger = logging.getLogger('bot_logger')  # Используем тот же логгер, что и в config
        logger.addHandler(handler)
        
        # Создаем CheckData с некорректной строкой даты
        check_data = CheckData(
            category="Продукты",
            amount=100.0,
            comment="Тест",
            check_datetime_str="некорректная_дата"
        )
        
        # Вызываем свойство transaction_datetime, которое должно вызвать ValueError
        dt = check_data.transaction_datetime
        
        # Проверяем, что возвращается текущая дата (поскольку парсинг не удался)
        assert isinstance(dt, datetime)
        
        # Проверяем, что сообщение об ошибке было записано в лог
        log_contents = log_capture.getvalue()
        assert "Ошибка парсинга даты транзакции" in log_contents
        assert "некорректная_дата" in log_contents
        
        # Убираем обработчик
        logger.removeHandler(handler)

    @pytest.mark.asyncio
    async def test_transaction_service_save_transaction_exception_logging(self):
        """Тест: Проверка логирования исключений в save_transaction"""
        import logging
        from io import StringIO
        
        # Создаем буфер для захвата логов
        log_capture = StringIO()
        handler = logging.StreamHandler(log_capture)
        handler.setLevel(logging.ERROR)
        
        # Получаем логгер
        logger = logging.getLogger('bot_logger')
        logger.addHandler(handler)
        
        # Создаем мок репозитория, который будет выбрасывать исключение
        mock_repository = AsyncMock()
        mock_repository.add_transaction.side_effect = Exception("Тестовая ошибка SQLite")
        
        transaction_service = TransactionService(repository=mock_repository)
        
        from models.transaction import TransactionData
        transaction = TransactionData(
            type="Расход",
            category="Продукты",
            amount=100.0,
            comment="Тест",
            username="test_user"
        )
        
        # Проверяем, что исключение обрабатывается корректно
        from utils.exceptions import SheetWriteError
        with pytest.raises(SheetWriteError):
            await transaction_service.save_transaction(transaction)
        
        # Проверяем, что сообщение об ошибке было записано в лог
        log_contents = log_capture.getvalue()
        assert "Ошибка при записи транзакции в SQLite" in log_contents
        assert "Тестовая ошибка SQLite" in log_contents
        
        # Убираем обработчик
        logger.removeHandler(handler)

    @pytest.mark.asyncio
    async def test_transaction_service_finalize_transaction_exception_logging(self):
        """Тест: Проверка логирования исключений в finalize_transaction"""
        import logging
        from io import StringIO
        
        # Создаем буфер для захвата логов
        log_capture = StringIO()
        handler = logging.StreamHandler(log_capture)
        handler.setLevel(logging.ERROR)
        
        # Получаем логгер
        logger = logging.getLogger('bot_logger')
        logger.addHandler(handler)
        
        # Создаем мок репозитория, который будет выбрасывать исключение
        mock_repository = AsyncMock()
        mock_repository.add_transaction.side_effect = Exception("Тестовая ошибка SQLite")
        
        transaction_service = TransactionService(repository=mock_repository)
        
        from models.transaction import TransactionData
        transaction = TransactionData(
            type="Расход",
            category="Продукты",
            amount=100.0,
            comment="Тест",
            username="test_user",
            transaction_dt=datetime.now()
        )
        
        # Вызываем finalize_transaction, который должен обработать исключение
        result = await transaction_service.finalize_transaction(transaction)
        
        # Проверяем, что результат содержит информацию об ошибке
        assert result['success'] is False
        assert 'Неизвестная ошибка' in result['error']
        
        # Проверяем, что сообщение об ошибке было записано в лог
        log_contents = log_capture.getvalue()
        assert "Неизвестная ошибка при финализации транзакции" in log_contents
        
        # Убираем обработчик
        logger.removeHandler(handler)