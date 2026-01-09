# -*- coding: utf-8 -*-
# tests/test_refunds.py
import unittest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import sys
import os

# === 🛠 МАГИЯ ПУТЕЙ (PATH HACK) ===
# Получаем абсолютный путь к папке, где лежит этот скрипт (tests/)
current_script_path = os.path.dirname(os.path.abspath(__file__))
# Получаем родительскую папку (корень проекта budget_bot/)
project_root = os.path.dirname(current_script_path)
# Вставляем корень в начало списка путей, где Python ищет модули
sys.path.insert(0, project_root)
# =================================

from models.transaction import TransactionData
from services.transaction_service import TransactionService
from services.repository import TransactionRepository
from services.auth_service import AuthService


class TestRefunds(unittest.TestCase):
    """Тесты для проверки функционала возвратов по транзакциям"""

    def setUp(self):
        """Подготовка тестовой среды"""
        # Создаем моки для зависимостей
        self.mock_repository = AsyncMock(spec=TransactionRepository)
        
        # Создаем транзакционный сервис с моком репозитория
        self.service = TransactionService(repository=self.mock_repository)
        
        # Создаем тестовые данные транзакции
        self.original_transaction = TransactionData(
            type="Расход",
            category="Продукты",
            amount=1000.0,
            comment="Покупка продуктов",
            username="test_user",
            user_id=123456789
        )

    def test_create_return_transaction_basic(self):
        """Тест создания транзакции возврата"""
        # Создаем транзакцию возврата
        return_transaction = TransactionData(
            type="Возврат",
            category="Продукты",
            amount=-1000.0,  # Отрицательная сумма для возврата
            comment="Возврат покупки продуктов",
            username="test_user",
            user_id=123456789
        )
        
        # Проверяем, что транзакция возврата создалась корректно
        self.assertEqual(return_transaction.type, "Возврат")
        self.assertEqual(return_transaction.amount, -1000.0)
        self.assertEqual(return_transaction.category, "Продукты")

    @patch('sheets.client.write_transaction')
    async def test_process_return_transaction(self, mock_write_transaction):
        """Тест обработки транзакции возврата через сервис"""
        mock_write_transaction.return_value = True
        
        # Создаем транзакцию возврата
        return_transaction = TransactionData(
            type="Возврат",
            category="Продукты",
            amount=-500.0,
            comment="Возврат части покупки",
            username="test_user",
            user_id=123456789
        )
        
        # Сохраняем транзакцию возврата
        result = await self.service.save_transaction(return_transaction)
        
        # Проверяем, что транзакция сохранилась успешно
        self.assertTrue(result)
        # Проверяем, что репозиторий был вызван с правильными параметрами
        self.mock_repository.add_transaction.assert_called_once()

    async def test_refund_affects_balance_correctly(self):
        """Тест, что возврат корректно влияет на баланс"""
        # Создаем несколько транзакций: расход и возврат
        expense_transaction = TransactionData(
            type="Расход",
            category="Продукты",
            amount=1000.0,
            comment="Покупка",
            username="test_user",
            user_id=123456789
        )
        
        refund_transaction = TransactionData(
            type="Возврат",  # или "Расход" с отрицательной суммой
            category="Продукты",
            amount=-600.0,  # Частичный возврат
            comment="Возврат",
            username="test_user",
            user_id=123456789
        )
        
        # Обе транзакции должны быть сохранены
        expense_saved = await self.service.save_transaction(expense_transaction)
        refund_saved = await self.service.save_transaction(refund_transaction)
        
        # Проверяем, что обе транзакции сохранились
        self.assertTrue(expense_saved)
        self.assertTrue(refund_saved)
        
        # Проверяем, что были вызваны соответствующие методы репозитория
        self.assertEqual(self.mock_repository.add_transaction.call_count, 2)


class TestRefundIntegration(unittest.IsolatedAsyncioTestCase):
    """Интеграционные тесты для функционала возвратов"""

    async def asyncSetUp(self):
        """Асинхронная подготовка тестовой среды"""
        # Используем временную файловую базу, так как in-memory база не сохраняет таблицы между подключениями
        import tempfile
        import os
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()
        self.repository = TransactionRepository(db_path=self.temp_db.name)  # Используем файловую базу для тестов
        await self.repository.init_db()
        self.service = TransactionService(repository=self.repository)

    async def asyncTearDown(self):
        """Очистка после теста"""
        await self.repository.close()
        import os
        if os.path.exists(self.temp_db.name):
            os.remove(self.temp_db.name)

    async def test_full_refund_flow(self):
        """Тест полного цикла работы с возвратами"""
        # Создаем оригинальную транзакцию
        original_transaction = TransactionData(
            type="Расход",
            category="Электроника",
            amount=15000.0,
            comment="Покупка ноутбука",
            username="test_user",
            user_id=123456789
        )
        
        # Сохраняем оригинальную транзакцию
        original_saved = await self.service.save_transaction(original_transaction)
        self.assertTrue(original_saved)
        
        # Создаем транзакцию возврата
        refund_transaction = TransactionData(
            type="Возврат",
            category="Электроника",
            amount=-15000.0,  # Полный возврат
            comment="Возврат ноутбука",
            username="test_user",
            user_id=123456789
        )
        
        # Сохраняем транзакцию возврата
        refund_saved = await self.service.save_transaction(refund_transaction)
        self.assertTrue(refund_saved)
        
        # Проверяем, что в базе есть обе транзакции
        unsynced_transactions = await self.repository.get_unsynced()
        self.assertEqual(len(unsynced_transactions), 2)
        
        # Проверяем, что суммы корректно учитываются
        total_amount = sum(t['amount'] for t in unsynced_transactions)
        self.assertEqual(total_amount, 0.0)  # После возврата баланс должен быть 0


if __name__ == '__main__':
    # Запуск тестов
    unittest.main()