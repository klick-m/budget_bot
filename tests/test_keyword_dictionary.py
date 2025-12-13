# -*- coding: utf-8 -*-
"""
Тесты для модуля KeywordDictionary
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.keyword_dictionary import KeywordDictionary, KeywordEntry
from datetime import datetime


def test_basic_keyword_dictionary_functionality():
    """Тестирование базовой функциональности KeywordDictionary"""
    # Создаем фиктивный экземпляр без подключения к Google Sheets
    from collections import defaultdict
    keyword_dict = KeywordDictionary.__new__(KeywordDictionary)
    keyword_dict.spreadsheet_id = "test_id"
    keyword_dict.sheet_name = "test_sheet"
    keyword_dict.category_keywords = defaultdict(list)
    keyword_dict.keyword_to_category = {}
    keyword_dict.bigram_to_category = {}
    keyword_dict.unigram_to_categories = defaultdict(list)
    from collections import Counter
    keyword_dict.usage_stats = Counter()
    keyword_dict.last_update = None
    
    # Добавляем ключевые слова
    keyword_dict.add_keyword("хлеб", "Продукты", 0.8)
    keyword_dict.add_keyword("молоко", "Продукты", 0.9)
    keyword_dict.add_keyword("автобус", "Транспорт", 1.0)
    
    # Проверяем, что ключевые слова добавлены
    assert "хлеб" in keyword_dict.keyword_to_category
    assert "молоко" in keyword_dict.keyword_to_category
    assert "автобус" in keyword_dict.keyword_to_category
    
    # Проверяем, что категории добавлены
    assert "Продукты" in keyword_dict.category_keywords
    assert "Транспорт" in keyword_dict.category_keywords
    
    # Проверяем, что значения корректны
    assert keyword_dict.keyword_to_category["хлеб"].category == "Продукты"
    assert keyword_dict.keyword_to_category["хлеб"].confidence == 0.8
    assert keyword_dict.keyword_to_category["молоко"].confidence == 0.9
    assert keyword_dict.keyword_to_category["автобус"].confidence == 1.0
    
    # Проверяем получение ключевых слов по категории
    products_keywords = keyword_dict.get_category_keywords("Продукты")
    assert len(products_keywords) == 2
    product_keywords_text = [kw.keyword for kw in products_keywords]
    assert "хлеб" in product_keywords_text
    assert "молоко" in product_keywords_text
    
    # Проверяем получение всех категорий
    all_categories = keyword_dict.get_all_categories()
    assert "Продукты" in all_categories
    assert "Транспорт" in all_categories


def test_bigram_functionality():
    """Тестирование работы с биграммами"""
    from collections import defaultdict, Counter
    keyword_dict = KeywordDictionary.__new__(KeywordDictionary)
    keyword_dict.spreadsheet_id = "test_id"
    keyword_dict.sheet_name = "test_sheet"
    keyword_dict.category_keywords = defaultdict(list)
    keyword_dict.keyword_to_category = {}
    keyword_dict.bigram_to_category = {}
    keyword_dict.unigram_to_categories = defaultdict(list)
    keyword_dict.usage_stats = Counter()
    keyword_dict.last_update = None
    
    # Добавляем фразу из нескольких слов (должна создать биграммы)
    keyword_dict.add_keyword("магазин продуктов", "Продукты", 0.95)
    
    # Проверяем, что основная фраза добавлена
    assert "магазин продуктов" in keyword_dict.keyword_to_category
    
    # Проверяем, что биграмма добавлена
    assert "магазин продуктов" in keyword_dict.bigram_to_category
    
    # Проверяем, что отдельные слова тоже добавлены в индекс
    assert "магазин" in keyword_dict.unigram_to_categories
    assert "продуктов" in keyword_dict.unigram_to_categories
    
    # Проверяем поиск по биграмме
    result = keyword_dict.get_category_by_keyword("магазин продуктов")
    assert result is not None
    assert result[0] == "Продукты"
    assert result[1] == 0.95
    
    # Проверяем поиск по отдельным словам
    result = keyword_dict.get_category_by_keyword("магазин")
    assert result is not None
    assert result[0] == "Продукты"
    
    # Проверяем, что биграммы учитываются при поиске по тексту
    results = keyword_dict.get_categories_by_text("я купил в магазине продуктов")
    assert len(results) > 0
    # Должна быть найдена категория Продукты по биграмме "магазин продуктов"
    found_products = any(category == "Продукты" for category, confidence in results)
    assert found_products


def test_confidence_levels():
    """Тестирование уровней уверенности"""
    from collections import defaultdict, Counter
    keyword_dict = KeywordDictionary.__new__(KeywordDictionary)
    keyword_dict.spreadsheet_id = "test_id"
    keyword_dict.sheet_name = "test_sheet"
    keyword_dict.category_keywords = defaultdict(list)
    keyword_dict.keyword_to_category = {}
    keyword_dict.bigram_to_category = {}
    keyword_dict.unigram_to_categories = defaultdict(list)
    keyword_dict.usage_stats = Counter()
    keyword_dict.last_update = None
    
    # Добавляем ключевые слова с разными уровнями уверенности
    keyword_dict.add_keyword("uber", "Транспорт", 1.0)  # Высокая уверенность
    keyword_dict.add_keyword("кафе", "Рестораны", 0.6)  # Средняя уверенность
    keyword_dict.add_keyword("ресторан", "Рестораны", 0.8)  # Высокая уверенность
    
    # Проверяем уровни уверенности
    assert keyword_dict.keyword_to_category["uber"].confidence == 1.0
    assert keyword_dict.keyword_to_category["кафе"].confidence == 0.6
    assert keyword_dict.keyword_to_category["ресторан"].confidence == 0.8
    
    # Проверяем, что при поиске по тексту результаты сортируются по уверенности
    results = keyword_dict.get_categories_by_text("я поел в кафе и посетил ресторан")
    assert len(results) >= 2
    
    # Первый результат должен быть с более высокой уверенностью
    if len(results) >= 2:
        # Ресторан имеет уверенность 0.8, кафе 0.6, так что ресторан должен быть первым
        first_category, first_confidence = results[0]
        second_category, second_confidence = results[1]
        
        # Проверяем, что результаты отсортированы по уверенности
        assert first_confidence >= second_confidence


def test_integration_with_category_classifier():
    """Тестирование интеграции с существующей системой категоризации"""
    from utils.category_classifier import TransactionCategoryClassifier
    from models.transaction import TransactionData
    from datetime import datetime
    
    # Создаем экземпляр KeywordDictionary
    from collections import defaultdict
    keyword_dict = KeywordDictionary.__new__(KeywordDictionary)
    keyword_dict.spreadsheet_id = "test_id"
    keyword_dict.sheet_name = "test_sheet"
    keyword_dict.category_keywords = defaultdict(list)
    keyword_dict.keyword_to_category = {}
    keyword_dict.bigram_to_category = {}
    keyword_dict.unigram_to_categories = defaultdict(list)
    from collections import Counter
    keyword_dict.usage_stats = Counter()
    keyword_dict.last_update = None
    
    # Добавляем ключевые слова в словарь
    keyword_dict.add_keyword("ашан", "Продукты", 0.95)
    keyword_dict.add_keyword("перекресток", "Продукты", 0.90)
    keyword_dict.add_keyword("автобус", "Транспорт", 1.0)
    keyword_dict.add_keyword("кафе", "Рестораны", 0.7)
    
    # Создаем классификатор с подключенным словарем
    classifier = TransactionCategoryClassifier(keyword_dict=keyword_dict)
    
    # Создаем тестовую транзакцию с ключевым словом из словаря
    transaction = TransactionData(
        type="Расход",
        category="",
        amount=100.0,
        comment="Покупка в Ашан",
        username="test_user",
        retailer_name="Ашан",
        items_list="Хлеб, Молоко",
        payment_info="Карта",
        transaction_dt=datetime.now()
    )
    
    # Проверяем, что классификатор использует словарь
    predicted_category, confidence = classifier.predict_category(transaction)
    
    # Должна быть предсказана категория "Продукты" с уверенностью 0.95
    assert predicted_category == "Продукты"
    assert confidence == 0.95
    
    # Проверяем, что классификатор может получить категории по тексту
    categories_by_text = classifier.get_categories_by_text("обед в кафе")
    assert len(categories_by_text) > 0
    cafe_found = any(category == "Рестораны" for category, conf in categories_by_text)
    assert cafe_found
    
    # Проверяем, что классификатор может получить категорию по ключевому слову
    category_by_keyword = classifier.get_category_by_keyword("автобус")
    assert category_by_keyword is not None
    assert category_by_keyword[0] == "Транспорт"
    assert category_by_keyword[1] == 1.0


def test_performance_of_reverse_index():
    """Тестирование производительности обратного индекса"""
    import time
    
    from collections import defaultdict, Counter
    keyword_dict = KeywordDictionary.__new__(KeywordDictionary)
    keyword_dict.spreadsheet_id = "test_id"
    keyword_dict.sheet_name = "test_sheet"
    keyword_dict.category_keywords = defaultdict(list)
    keyword_dict.keyword_to_category = {}
    keyword_dict.bigram_to_category = {}
    keyword_dict.unigram_to_categories = defaultdict(list)
    keyword_dict.usage_stats = Counter()
    keyword_dict.last_update = None
    
    # Добавляем много ключевых слов для тестирования производительности
    test_words = [
        ("хлеб", "Продукты", 0.8),
        ("молоко", "Продукты", 0.85),
        ("яйца", "Продукты", 0.75),
        ("сыр", "Продукты", 0.8),
        ("мясо", "Продукты", 0.9),
        ("овощи", "Продукты", 0.7),
        ("фрукты", "Продукты", 0.75),
        ("автобус", "Транспорт", 1.0),
        ("метро", "Транспорт", 1.0),
        ("такси", "Транспорт", 0.95),
        ("интернет", "Связь", 0.9),
        ("телефон", "Связь", 0.85),
        ("кафе", "Рестораны", 0.7),
        ("ресторан", "Рестораны", 0.8),
        ("кино", "Развлечения", 0.75),
        ("театр", "Развлечения", 0.8),
        ("подписка", "Подписки", 0.9),
        ("аренда", "Жилье", 0.95),
        ("квартплата", "Жилье", 1.0),
        ("электричество", "Жилье", 0.85)
    ]
    
    # Добавляем все слова
    for keyword, category, confidence in test_words:
        keyword_dict.add_keyword(keyword, category, confidence)
    
    # Добавляем несколько фраз для тестирования биграмм
    keyword_dict.add_keyword("магазин продуктов", "Продукты", 0.95)
    keyword_dict.add_keyword("кафе у дома", "Рестораны", 0.75)
    
    # Измеряем время выполнения поиска
    start_time = time.time()
    
    # Выполняем несколько поисковых запросов
    for _ in range(100):
        result = keyword_dict.get_category_by_keyword("хлеб")
        result = keyword_dict.get_category_by_keyword("автобус")
        result = keyword_dict.get_category_by_keyword("интернет")
        result = keyword_dict.get_categories_by_text("покупка в магазине продуктов")
        result = keyword_dict.get_categories_by_text("обед в кафе у дома")
    
    end_time = time.time()
    
    # Проверяем, что время выполнения разумное (менее 1 секунды для 500 поисков)
    execution_time = end_time - start_time
    assert execution_time < 1.0, f"Время выполнения слишком долго: {execution_time} секунд"
    
    # Проверяем, что все ключевые слова корректно находятся
    assert keyword_dict.get_category_by_keyword("хлеб") == ("Продукты", 0.8)
    assert keyword_dict.get_category_by_keyword("автобус") == ("Транспорт", 1.0)
    assert keyword_dict.get_category_by_keyword("интернет") == ("Связь", 0.9)
    
    # Проверяем, что биграммы также работают
    bigram_results = keyword_dict.get_categories_by_text("магазин продуктов")
    assert len(bigram_results) > 0
    assert any(category == "Продукты" for category, conf in bigram_results)


if __name__ == "__main__":
    test_basic_keyword_dictionary_functionality()
    test_bigram_functionality()
    test_confidence_levels()
    test_integration_with_category_classifier()
    test_performance_of_reverse_index()
    print("Все тесты для KeywordDictionary пройдены успешно!")

def test_integration_with_receipt_logic():
    """Тест интеграции новой системы с логикой обработки чеков"""
    from utils.receipt_logic import map_category_by_keywords
    from utils.category_classifier import classifier
    from models.transaction import CheckData
    from datetime import datetime

    # Добавляем тестовые ключевые слова в classifier (через KeywordDictionary)
    classifier.add_keyword("ашан", "Продукты", 0.95)
    classifier.add_keyword("перекресток", "Продукты", 0.90)
    classifier.add_keyword("автобус", "Транспорт", 1.0)
    classifier.add_keyword("кафе", "Рестораны", 0.7)

    # Тестируем функцию map_category_by_keywords с новыми данными
    category = map_category_by_keywords("покупка в ашан")
    assert category == "Продукты", f"Ожидалась категория 'Продукты', получено '{category}'"

    category = map_category_by_keywords("проезд в автобусе")
    assert category == "Транспорт", f"Ожидалась категория 'Транспорт', получено '{category}'"

    # Тестируем случай, когда ключевое слово не найдено
    category = map_category_by_keywords("неизвестный магазин")
    # В этом случае должна вернуться последняя категория расходов или "Прочее Расход"
    assert category is not None, "Категория не должна быть None"

    print("Тест интеграции с логикой обработки чеков пройден успешно!")
