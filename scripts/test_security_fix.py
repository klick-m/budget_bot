#!/usr/bin/env python3
"""
Тестирование безопасности фикса в функции get_latest_transactions
Проверяет:
1. Пользователь может видеть только свои транзакции
2. Пользователь не может получить доступ к транзакциям другого пользователя с похожим ID
3. Функция корректно работает с различными форматами user_id
"""
import asyncio
import sys
import os
# Добавляем текущую директорию в путь для импорта
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from unittest.mock import AsyncMock, patch
from sheets.client import get_latest_transactions


# Мокаем все зависимости перед тестированием
async def test_security_fix():
    print("Тестирование безопасности фикса в get_latest_transactions...")
    
    # Подготовим тестовые данные
    mock_sheet_data = [
        ["Дата", "Время", "Тип", "Категория", "Сумма", "Комментарий", "username", "Продавец", "Товары", "Оплата"],
        ["01.01.2024", "10:00:0", "Расход", "Еда", "100.0", "Покупка", "user123", "Магазин", "Хлеб", "Наличные"],
        ["01.01.2024", "11:0:00", "Расход", "Транспорт", "50.0", "Проезд", "user456", "Такси", "Поездка", "Карта"],
        ["02.01.2024", "12:00:0", "Доход", "Зарплата", "1000.0", "Оклад", "user123", "Компания", "Зарплата", "Перевод"],
        ["02.01.2024", "13:00:00", "Расход", "Еда", "200.0", "Обед", "user789", "Ресторан", "Суп", "Карта"],
        # Сценарий уязвимости: пользователь с ID "123" должен был получить доступ к транзакциям "user123" при старой логике
        ["03.01.2024", "14:00:00", "Расход", "Развлечения", "300.0", "Кино", "user123", "Кинотеатр", "Билет", "Карта"],
    ]
    
    print("\n1. Проверка: пользователь может видеть только свои транзакции")
    with patch('sheets.client.get_sheet_data_with_cache', AsyncMock(return_value=mock_sheet_data)):
        # Проверяем транзакции для user123
        user123_transactions = await get_latest_transactions("user123")
        print(f"   Транзакции для user123: {len(user123_transactions)} шт.")
        for i, tx in enumerate(user123_transactions):
            print(f"   - Транзакция {i+1}: {tx['date']} {tx['amount']} руб. (username: {tx['username']})")
            assert tx['username'] == "user123", f"Нарушение безопасности: транзакция другого пользователя в выдаче для user123: {tx}"
        
        print("   ✓ Пользователь user123 видит только свои транзакции")
        
        # Проверяем транзакции для user456
        user456_transactions = await get_latest_transactions("user456")
        print(f"   Транзакции для user456: {len(user456_transactions)} шт.")
        for i, tx in enumerate(user456_transactions):
            print(f"   - Транзакция {i+1}: {tx['date']} {tx['amount']} руб. (username: {tx['username']})")
            assert tx['username'] == "user456", f"Нарушение безопасности: транзакция другого пользователя в выдаче для user456: {tx}"
        
        print("   ✓ Пользователь user456 видит только свои транзакции")
    
    print("\n2. Проверка: пользователь не может получить доступ к транзакциям другого пользователя с похожим ID")
    with patch('sheets.client.get_sheet_data_with_cache', AsyncMock(return_value=mock_sheet_data)):
        # Проверяем, что пользователь "123" НЕ получает доступ к транзакциям "user123" (старая уязвимость)
        user123_transactions = await get_latest_transactions("user123")
        user_123_transactions = await get_latest_transactions("123")
        
        print(f"   Транзакции для 'user123': {len(user123_transactions)} шт.")
        print(f"   Транзакции для '123': {len(user_123_transactions)} шт. (должно быть 0)")
        
        # Пользователь "123" не должен видеть транзакции "user123"
        assert len(user_123_transactions) == 0, f"Нарушение безопасности: пользователь '123' получил доступ к транзакциям 'user123'"
        print("   ✓ Пользователь '123' не получает доступ к транзакциям 'user123'")
        
        # Проверим также другие похожие ID
        similar_ids = ["123", "ser123", "use123", "user12", "user1"]
        for test_id in similar_ids:
            test_transactions = await get_latest_transactions(test_id)
            print(f"   Транзакции для '{test_id}': {len(test_transactions)} шт.")
            assert len(test_transactions) == 0, f"Нарушение безопасности: пользователь '{test_id}' получил доступ к транзакциям"
        
        print("   ✓ Пользователи с похожими ID не получают доступ к чужим транзакциям")
    
    print("\n3. Проверка: функция корректно работает с различными форматами user_id")
    with patch('sheets.client.get_sheet_data_with_cache', AsyncMock(return_value=mock_sheet_data)):
        # Тестируем различные форматы ID
        # Правильные ожидания на основе тестовых данных:
        # - user123: 3 транзакции (встречается 3 раза в тестовых данных)
        # - user456: 1 транзакция (встречается 1 раз)
        # - user789: 1 транзакция (встречается 1 раз)
        test_cases_correct = [
            ("user123", 3),  # Должен получить 3 транзакции
            ("user456", 1),  # Должен получить 1 транзакцию
            ("user789", 1),  # Должен получить 1 транзакцию
            ("nonexistent", 0),  # Должен получить 0 транзакций
            ("", 0),  # Пустой ID - 0 транзакций
            ("123456789", 0),  # Числовой ID - 0 транзакций
            ("user_123", 0),  # ID с подчеркиванием - 0 транзакций
        ]
        
        for user_id, expected_count in test_cases_correct:
            transactions = await get_latest_transactions(user_id)
            print(f"   ID '{user_id}': {len(transactions)} транзакций (ожидается {expected_count})")
            assert len(transactions) == expected_count, f"Неправильное количество транзакций для ID '{user_id}': {len(transactions)}, ожидалось {expected_count}"
        
        print("   ✓ Функция корректно работает с различными форматами user_id")
    
    print("\n✅ Все тесты безопасности пройдены успешно!")
    print("   - Пользователи видят только свои транзакции")
    print("   - Уязвимость с подстрокой user_id устранена")
    print("   - Функция корректно обрабатывает различные форматы ID")

if __name__ == "__main__":
    asyncio.run(test_security_fix())