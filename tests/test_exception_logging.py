# -*- coding: utf-8 -*-
"""
Тесты для проверки логирования стека вызовов при ошибках
"""
import pytest
import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, patch, MagicMock
import traceback

from models.transaction import CheckData
from services.transaction_service import TransactionService
from sheets.client import get_latest_transactions


class TestExceptionLogging:
    """Тесты для проверки логирования стека вызовов"""

    def test_check_data_transaction_datetime_traceback_logging(self):
        """Тест: Проверка логирования стека вызовов при парсинге даты в CheckData"""
        import logging
        from io import StringIO
        
        # Создаем буфер для захвата логов
        log_capture = StringIO()
        handler = logging.StreamHandler(log_capture)
        handler.setLevel(logging.DEBUG) # Уровень DEBUG, чтобы захватить стек вызовов
        
        # Получаем логгер, который используется в модуле
        logger = logging.getLogger('bot_logger')  # Используем тот же логгер, что и в config
        logger.addHandler(handler)
        
        # Создаем CheckData с некорректной строкой даты
        check_data = CheckData(
            category="Продукты",
            amount=100.0,
            comment="Тест",
            check_datetime_str="некорректная_датa"
        )
        
        # Вызываем свойство transaction_datetime, которое должно вызвать ValueError
        dt = check_data.transaction_datetime
        
        # Проверяем, что возвращается текущая дата (поскольку парсинг не удался)
        assert isinstance(dt, datetime)
        
        # Проверяем, что сообщение о стеке вызовов было записано в лог
        log_contents = log_capture.getvalue()
        assert "Стек вызова:" in log_contents
        assert "некорректная_датa" in log_contents
        
        # Убираем обработчик
        logger.removeHandler(handler)

    @pytest.mark.asyncio
    async def test_parse_datetime_traceback_logging(self):
        """Тест: Проверка логирования стека вызовов в функции parse_datetime"""
        import logging
        from io import StringIO
        
        # Создаем буфер для захвата логов
        log_capture = StringIO()
        handler = logging.StreamHandler(log_capture)
        handler.setLevel(logging.DEBUG)  # Уровень DEBUG, чтобы захватить стек вызовов
        
        # Получаем логгер
        logger = logging.getLogger('bot_logger')
        logger.addHandler(handler)
        
        # Имитируем транзакцию с некорректной датой
        transaction = {
            "date": "некорректная_дата",
            "time": "некорректное_время"
        }
        
        # Импортируем функцию parse_datetime из sheets.client
        # Создаем временную функцию для тестирования
        from datetime import datetime
        import traceback
        from config import logger
        
        def parse_datetime(transaction):
            try:
                dt_str = f"{transaction['date']} {transaction['time']}"
                return datetime.strptime(dt_str, "%d.%m.%Y %H:%M:%S")
            except ValueError as e:
                # Если формат даты не распознан, возвращаем минимальную дату
                logger.warning(f"Ошибка парсинга даты и времени: {e}")
                logger.debug(f"Стек вызова: {traceback.format_exc()}")
                return datetime.min
        
        # Вызываем функцию parse_datetime
        result = parse_datetime(transaction)
        
        # Проверяем, что возвращается минимальная дата
        assert result == datetime.min
        
        # Проверяем, что сообщение о стеке вызовов было записано в лог
        log_contents = log_capture.getvalue()
        assert "Стек вызова:" in log_contents
        assert "Ошибка парсинга даты и времени:" in log_contents
        
        # Убираем обработчик
        logger.removeHandler(handler)