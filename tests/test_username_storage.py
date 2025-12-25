import pytest
import asyncio
import tempfile
import os
from datetime import datetime

from services.repository import TransactionRepository
from models.transaction import TransactionData


@pytest.mark.asyncio
async def test_transaction_stores_real_username():
    """Тест проверяет, что транзакции сохраняются с реальными именами пользователей"""
    # Создаем временный файл для тестовой базы данных
    with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as temp_db:
        temp_db_path = temp_db.name

    try:
        # Инициализируем репозиторий с временной базой данных
        repo = TransactionRepository(db_path=temp_db_path)
        await repo.init_db()

        # Добавляем транзакцию с реальным именем пользователя
        user_id = 123456789
        username = "Иван Иванов"
        amount = 1000.0
        category = "Продукты"
        comment = "Покупка в магазине"

        transaction_id = await repo.add_transaction(
            user_id=user_id,
            username=username,
            amount=amount,
            category=category,
            comment=comment
        )

        # Проверяем, что транзакция была добавлена
        assert transaction_id > 0

        # Получаем несинхронизированные транзакции
        unsynced_transactions = await repo.get_unsynced()

        # Проверяем, что транзакция содержится в списке
        assert len(unsynced_transactions) == 1
        transaction = unsynced_transactions[0]

        # Проверяем, что все поля корректно сохранены
        assert transaction['user_id'] == user_id
        assert transaction['username'] == username
        assert transaction['amount'] == amount
        assert transaction['category'] == category
        assert transaction['comment'] == comment
        assert transaction['is_synced'] == 0

    finally:
        # Удаляем временный файл
        if os.path.exists(temp_db_path):
            os.unlink(temp_db_path)


@pytest.mark.asyncio
async def test_transaction_stores_username_with_special_characters():
    """Тест проверяет, что транзакции корректно сохраняют имена специальными символами"""
    # Создаем временный файл для тестовой базы данных
    with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as temp_db:
        temp_db_path = temp_db.name

    try:
        # Инициализируем репозиторий с временной базой данных
        repo = TransactionRepository(db_path=temp_db_path)
        await repo.init_db()

        # Добавляем транзакцию с именем пользователя, содержащим специальные символы
        user_id = 987654321
        username = "Петров-Водкин @user#123"
        amount = 2500.50
        category = "Развлечения"
        comment = "Кино и ужин"

        transaction_id = await repo.add_transaction(
            user_id=user_id,
            username=username,
            amount=amount,
            category=category,
            comment=comment
        )

        # Проверяем, что транзакция была добавлена
        assert transaction_id > 0

        # Получаем несинхронизированные транзакции
        unsynced_transactions = await repo.get_unsynced()

        # Проверяем, что транзакция содержится в списке
        assert len(unsynced_transactions) == 1
        transaction = unsynced_transactions[0]

        # Проверяем, что имя пользователя корректно сохранено
        assert transaction['username'] == username

    finally:
        # Удаляем временный файл
        if os.path.exists(temp_db_path):
            os.unlink(temp_db_path)


@pytest.mark.asyncio
async def test_transaction_handles_empty_username():
    """Тест проверяет, что транзакции корректно обрабатывают пустое имя пользователя"""
    # Создаем временный файл для тестовой базы данных
    with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as temp_db:
        temp_db_path = temp_db.name

    try:
        # Инициализируем репозиторий с временной базой данных
        repo = TransactionRepository(db_path=temp_db_path)
        await repo.init_db()

        # Добавляем транзакцию с пустым именем пользователя
        user_id = 555123456
        username = ""
        amount = 500.0
        category = "Транспорт"
        comment = "Проездной"

        transaction_id = await repo.add_transaction(
            user_id=user_id,
            username=username,
            amount=amount,
            category=category,
            comment=comment
        )

        # Проверяем, что транзакция была добавлена
        assert transaction_id > 0

        # Получаем несинхронизированные транзакции
        unsynced_transactions = await repo.get_unsynced()

        # Проверяем, что транзакция содержится в списке
        assert len(unsynced_transactions) == 1
        transaction = unsynced_transactions[0]

        # Проверяем, что пустое имя пользователя корректно сохранено
        assert transaction['username'] == username

    finally:
        # Удаляем временный файл
        if os.path.exists(temp_db_path):
            os.unlink(temp_db_path)