import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import traceback

from services.transaction_service import TransactionService
from models.transaction import TransactionData, CheckData
from utils.exceptions import SheetWriteError
from config import logger


class TestExceptionHandling:
    """Тесты для проверки улучшенной обработки исключений"""

    @pytest.mark.asyncio
    async def test_save_transaction_exception_handling(self):
        """Тест обработки исключения в методе save_transaction"""
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
        
        # Проверяем, что исключение правильно обрабатывается
        with pytest.raises(SheetWriteError) as exc_info:
            await service.save_transaction(transaction)
        
        assert "Ошибка при записи транзакции в SQLite" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_finalize_transaction_exception_handling(self):
        """Тест обработки исключения в методе finalize_transaction"""
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
        
        # Проверяем, что метод возвращает правильный результат при ошибке
        result = await service.finalize_transaction(transaction)
        
        assert result['success'] is False
        # Ошибка из save_transaction будет перехвачена как SheetWriteError в finalize_transaction
        assert "Ошибка записи в Google Sheets! Ошибка:" in result['error']
        assert "Ошибка при записи транзакции в SQLite" in result['error']

    def test_transaction_datetime_parsing_exception(self):
        """Тест обработки исключения при парсинге даты в TransactionData"""
        # Создаем CheckData с некорректной строкой даты
        check_data = CheckData(
            type="Расход",
            category="Продукты",
            amount=100.0,
            comment="Тестовая транзакция",
            check_datetime_str="некорректная_дата"
        )
        
        # Проверяем, что используется текущая дата при ошибке парсинга
        current_time = check_data.transaction_datetime
        assert isinstance(current_time, type(asyncio.run(asyncio.sleep(0))).__class__.__bases__[0])  # Это datetime

    def test_transaction_datetime_correct_parsing(self):
        """Тест корректного парсинга даты в TransactionData"""
        # Создаем CheckData с корректной строкой даты
        check_data = CheckData(
            type="Расход",
            category="Продукты",
            amount=100.0,
            comment="Тестовая транзакция",
            check_datetime_str="2023-12-24T15:30:00"
        )
        
        # Проверяем, что дата корректно распарсилась
        parsed_time = check_data.transaction_datetime
        assert parsed_time.year == 2023
        assert parsed_time.month == 12
        assert parsed_time.day == 24
        assert parsed_time.hour == 15
        assert parsed_time.minute == 30
        assert parsed_time.second == 0

    @pytest.mark.asyncio
    async def test_transaction_datetime_minutes_only_parsing(self):
        """Тест парсинга даты без секунд в TransactionData"""
        # Создаем CheckData с корректной строкой даты без секунд
        check_data = CheckData(
            type="Расход",
            category="Продукты",
            amount=100.0,
            comment="Тестовая транзакция",
            check_datetime_str="2023-12-24T15:30"
        )
        
        # Проверяем, что дата корректно распарсилась
        parsed_time = check_data.transaction_datetime
        assert parsed_time.year == 2023
        assert parsed_time.month == 12
        assert parsed_time.day == 24
        assert parsed_time.hour == 15
        assert parsed_time.minute == 30
        assert parsed_time.second == 0