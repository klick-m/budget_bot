#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тестирование "Быстрого ввода" (Smart Parsing) для бота.
Проверяет работу парсера с различными форматами ввода:
- "Текст Число" (например, "Еда 100")
- "Число Текст" (например, "100 Еда") 
- "Просто Число" (например, "100")
"""

import sys
import os

# Добавляем директорию проекта в путь Python для импорта модулей
sys.path.insert(0, os.path.abspath('.'))

from services.input_parser import InputParser


def test_parser():
    """Тестируем парсер с различными форматами ввода."""
    parser = InputParser()
    
    test_cases = [
        # (входной_текст, ожидаемая_сумма, ожидаемый_комментарий)
        ("Еда 100", 100.0, "Еда"),
        ("100 Еда", 100.0, "Еда"),
        ("100", 100.0, ""),
        ("Такси 500", 500.0, "Такси"),
        ("500 такси", 500.0, "такси"),
        ("Продукты 1234.56", 1234.56, "Продукты"),
        ("1234.56 Продукты", 1234.56, "Продукты"),
        ("Кофе 300.50", 300.50, "Кофе"),
        ("300.50 Кофе", 300.50, "Кофе"),
        ("100.00", 100.00, ""),
        ("Число 123.45 текст", 123.45, "Число текст"),
        ("", None, ""),
        ("Текст", None, ""),
        ("абв 123 гдеж", 123.0, "абв гдеж"),
        ("123.456.789", 123.45, "6 789"),  # Несколько чисел - берется первое (123.45), остаток: "6 789"
        ("Просто текст без числа", None, ""),
        ("100.50.200", 100.50, "200"),  # Несколько чисел - берется первое
        ("100,50", 100.50, ""),  # Запятая как разделитель
        ("Еда 100,50", 100.50, "Еда"),  # Запятая как разделитель с текстом
    ]
    
    print("Тестирование парсера 'Быстрого ввода' (Smart Parsing)")
    print("=" * 60)
    
    all_passed = True
    
    for i, (input_text, expected_amount, expected_comment) in enumerate(test_cases, 1):
        result = parser.parse_user_input(input_text)
        
        if result is None:
            actual_amount = None
            actual_comment = ""
        else:
            actual_amount = result['amount']
            actual_comment = result['comment']
        
        # Проверяем результат
        amount_ok = (actual_amount == expected_amount)
        comment_ok = (actual_comment == expected_comment)
        
        status = "[OK]" if (amount_ok and comment_ok) else "[FAIL]"
        
        print(f"{i:2d}. Ввод: '{input_text}'")
        print(f"    Ожидаем: сумма={expected_amount}, коммент='{expected_comment}'")
        print(f"    Результат: сумма={actual_amount}, коммент='{actual_comment}'")
        print(f"    Статус: {status}")
        
        if not (amount_ok and comment_ok):
            all_passed = False
            print(f"    ОШИБКА: ожидалось сумма={expected_amount}, коммент='{expected_comment}', "
                  f"получено сумма={actual_amount}, коммент='{actual_comment}'")
        
        print()
    
    print("=" * 60)
    if all_passed:
        print("[OK] Все тесты пройдены успешно!")
    else:
        print("[FAIL] Некоторые тесты не пройдены!")
    
    return all_passed


if __name__ == "__main__":
    test_parser()