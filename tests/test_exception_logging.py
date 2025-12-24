import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import traceback
import logging

from services.transaction_service import TransactionService
from models.transaction import TransactionData, CheckData
from utils.exceptions import SheetWriteError
from config import logger


class TestExceptionLogging:
    """Тесты для проверки логирования исключений"""

    @pytest.mark.asyncio
    async def test_save_transaction_logs_traceback(self, caplog):
        """Тест логирования стека вызовов в save_transaction"""
        # Создаем мок-репозиторий, который будет выбрасывать исключение
        mock_repository = AsyncMock()
        mock_repository.add_transaction.side_effect = Exception("Database connection failed")
        
        service = TransactionService(repository=mock_repository)
        
        # Создаем тестовую транзакцию
        transaction = TransactionData(
            type="Расход",
            category="Продукты",
            amount=100.0,
            comment="Тестовая транзакция",
            username="test_user"
        )
        
        # Проверяем логирование при исключении
        with caplog.at_level(logging.DEBUG):
            with pytest.raises(SheetWriteError):
                await service.save_transaction(transaction)
        
        # Проверяем, что были записи об ошибке и стеке вызовов
        error_logs = [record for record in caplog.records if record.levelno == logging.ERROR]
        debug_logs = [record for record in caplog.records if record.levelno == logging.DEBUG]
        
        assert len(error_logs) > 0
        assert "Ошибка при записи транзакции в SQLite" in error_logs[0].message
        
        # Проверяем, что в debug логах есть информация о стеке вызовов
        debug_found = any("Стек вызова:" in record.message for record in debug_logs)
        assert debug_found, "Должно быть логирование стека вызовов на уровне debug"

    @pytest.mark.asyncio
    async def test_finalize_transaction_logs_traceback(self, caplog):
        """Тест логирования стека вызовов в finalize_transaction"""
        # Создаем мок-репозиторий, который будет выбрасывать исключение
        mock_repository = AsyncMock()
        mock_repository.add_transaction.side_effect = Exception("Database connection failed")
        
        service = TransactionService(repository=mock_repository)
        
        # Создаем тестовую транзакцию
        transaction = TransactionData(
            type="Расход",
            category="Продукты",
            amount=100.0,
            comment="Тестовая транзакция",
            username="test_user"
        )
        
        # Проверяем логирование при исключении
        with caplog.at_level(logging.DEBUG):
            await service.finalize_transaction(transaction)
        
        # Проверяем, что были записи об ошибке и стеке вызовов
        error_logs = [record for record in caplog.records if record.levelno == logging.ERROR]
        debug_logs = [record for record in caplog.records if record.levelno == logging.DEBUG]
        
        # Проверяем, что есть логи ошибок из save_transaction
        error_found = any("Ошибка при записи транзакции в SQLite" in record.message for record in error_logs)
        assert error_found, "Должно быть логирование ошибки при записи транзакции в SQLite"
        
        # Проверяем, что в debug логах есть информация о стеке вызовов
        debug_found = any("Стек вызова:" in record.message for record in debug_logs)
        assert debug_found, "Должно быть логирование стека вызовов на уровне debug"

    def test_transaction_datetime_logs_traceback(self, caplog):
        """Тест логирования стека вызовов при парсинге даты в TransactionData"""
        # Создаем CheckData с некорректной строкой даты
        check_data = CheckData(
            type="Расход",
            category="Продукты",
            amount=100.0,
            comment="Тестовая транзакция",
            check_datetime_str="некорректная_дата"
        )
        
        # Проверяем, что используется текущая дата при ошибке парсинга
        with caplog.at_level(logging.DEBUG):
            current_time = check_data.transaction_datetime
        
        # Проверяем, что были записи о предупреждении и стеке вызовов
        warning_logs = [record for record in caplog.records if record.levelno == logging.WARNING]
        debug_logs = [record for record in caplog.records if record.levelno == logging.DEBUG]
        
        assert len(warning_logs) > 0
        assert "Ошибка парсинга даты транзакции" in warning_logs[0].message
        
        # Проверяем, что в debug логах есть информация о стеке вызовов
        debug_found = any("Стек вызова:" in record.message for record in debug_logs)
        assert debug_found, "Должно быть логирование стека вызовов на уровне debug"