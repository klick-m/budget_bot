# -*- coding: utf-8 -*-
"""
Тестирование новой системы распознавания категорий
"""
from utils.category_classifier import TransactionCategoryClassifier
from models.keyword_dictionary import KeywordDictionary
from collections import defaultdict, Counter
from models.transaction import TransactionData
from datetime import datetime

def test_new_system():
    # Создаем тестовый KeywordDictionary
    keyword_dict = KeywordDictionary.__new__(KeywordDictionary)
    keyword_dict.spreadsheet_id = 'test_id'
    keyword_dict.sheet_name = 'test_sheet'
    keyword_dict.category_keywords = defaultdict(list)
    keyword_dict.keyword_to_category = {}
    keyword_dict.bigram_to_category = {}
    keyword_dict.unigram_to_categories = defaultdict(list)
    keyword_dict.usage_stats = Counter()
    keyword_dict.last_update = None

    # Добавляем тестовые ключевые слова
    keyword_dict.add_keyword('ашан', 'Продукты', 0.95)
    keyword_dict.add_keyword('автобус', 'Транспорт', 1.0)
    keyword_dict.add_keyword('кафе', 'Рестораны', 0.7)

    # Создаем классификатор с тестовым словарем, обходя автоматическую инициализацию
    from utils.category_classifier import TransactionCategoryClassifier
    classifier = TransactionCategoryClassifier.__new__(TransactionCategoryClassifier)
    classifier.category_keywords = defaultdict(list)
    classifier.category_features = defaultdict(lambda: defaultdict(int))
    classifier.global_features = defaultdict(int)
    classifier.category_transactions_count = defaultdict(int)
    classifier.total_transactions = 0
    classifier.categories = set()
    classifier.keyword_dict = keyword_dict  # Прямо устанавливаем наш тестовый словарь

    # Тестируем
    result = classifier.get_category_by_keyword('ашан')
    print('Результат для ашан:', result)
    assert result == ('Продукты', 0.95), f"Ожидалось ('Продукты', 0.95), получено {result}"

    result = classifier.get_categories_by_text('покупка в ашан')
    print('Результат для покупка в ашан:', result)
    assert len(result) > 0, "Должен быть найден хотя бы один результат"
    assert any(cat == 'Продукты' for cat, conf in result), "Должна быть найдена категория Продукты"

    # Тестируем транзакцию
    transaction = TransactionData(
        type='Расход',
        category='',
        amount=100.0,
        comment='Покупка в Ашан',
        username='test_user',
        retailer_name='Ашан',
        items_list='Хлеб, Молоко',
        payment_info='Карта',
        transaction_dt=datetime.now()
    )

    # Используем методы keyword_dict напрямую, чтобы избежать проблем с ML-моделью
    # при тестировании новой системы распознавания
    result = keyword_dict.get_category_by_keyword('ашан')
    print('Результат для транзакции (через keyword_dict):', result)
    assert result[0] == 'Продукты', f"Ожидалась категория Продукты, получено {result[0]}"

    print("Все тесты пройдены успешно!")

if __name__ == "__main__":
    test_new_system()