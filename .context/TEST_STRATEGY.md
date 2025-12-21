# Стратегия тестирования для REF-006: Исправление инициализации MorphAnalyzer

## Цель
Обеспечить покрытие тестами сценариев, в которых может возникать AttributeError: morph_analyzer, и проверить корректность исправления.

## Тест-кейсы для Code Agent

### 1. Тестирование инициализации через __new__
```python
def test_keyword_dictionary_init_with_new():
    """Тест создания экземпляра KeywordDictionary через __new__"""
    from models.keyword_dictionary import KeywordDictionary
    from collections import defaultdict, Counter
    
    # Создание экземпляра через __new__ как в текущем коде
    keyword_dict = KeywordDictionary.__new__(KeywordDictionary)
    keyword_dict.spreadsheet_id = "test_id"
    keyword_dict.sheet_name = "test_sheet"
    keyword_dict.category_keywords = defaultdict(list)
    keyword_dict.keyword_to_category = {}
    keyword_dict.bigram_to_category = {}
    keyword_dict.unigram_to_categories = defaultdict(list)
    keyword_dict.usage_stats = Counter()
    keyword_dict.last_update = None
    
    # Проверка, что morph_analyzer инициализирован (даже если None)
    assert hasattr(keyword_dict, 'morph_analyzer')
    
    # Проверка, что можно вызвать методы, использующие morph_analyzer
    result = keyword_dict.lemmatize_text("тестовый текст")
    assert isinstance(result, str)
```

### 2. Тестирование инициализации CategoryClassifier с пустым KeywordDictionary
```python
def test_category_classifier_with_new_keyword_dict():
    """Тест создания CategoryClassifier с KeywordDictionary, созданным через __new__"""
    from utils.category_classifier import TransactionCategoryClassifier
    from models.keyword_dictionary import KeywordDictionary
    from collections import defaultdict, Counter
    
    # Создание KeywordDictionary через __new__ как в текущем коде
    keyword_dict = KeywordDictionary.__new__(KeywordDictionary)
    keyword_dict.spreadsheet_id = "test_id"
    keyword_dict.sheet_name = "test_sheet"
    keyword_dict.category_keywords = defaultdict(list)
    keyword_dict.keyword_to_category = {}
    keyword_dict.bigram_to_category = {}
    keyword_dict.unigram_to_categories = defaultdict(list)
    keyword_dict.usage_stats = Counter()
    keyword_dict.last_update = None
    keyword_dict.sheets_client = None
    
    # Создание классификатора с этим словарем
    classifier = TransactionCategoryClassifier(keyword_dict=keyword_dict)
    
    # Проверка, что morph_analyzer инициализирован
    assert hasattr(classifier, 'morph_analyzer')
    assert hasattr(classifier.keyword_dict, 'morph_analyzer')
    
    # Проверка, что можно вызвать методы, использующие morph_analyzer
    result = classifier.lemmatize_text("тестовый текст")
    assert isinstance(result, str)
```

### 3. Тестирование асинхронной инициализации
```python
def test_async_initialization_preserves_morph_analyzer():
    """Тест, что асинхронная инициализация не теряет morph_analyzer"""
    import asyncio
    from models.keyword_dictionary import KeywordDictionary
    
    # Создание обычного экземпляра
    keyword_dict = KeywordDictionary("test_id", "test_sheet")
    
    # Сохранение состояния morph_analyzer до асинхронной операции
    original_morph_analyzer = keyword_dict.morph_analyzer
    
    # Выполнение асинхронной загрузки (даже если она не завершится успешно)
    try:
        asyncio.run(keyword_dict.async_load_from_sheets())
    except:
        pass  # Ошибка загрузки не важна для этого теста
    
    # Проверка, что morph_analyzer сохранился
    assert hasattr(keyword_dict, 'morph_analyzer')
    assert keyword_dict.morph_analyzer is not None or keyword_dict.morph_analyzer is None  # Не должно быть AttributeError
```

### 4. Тестирование случаев, когда pymorphy3 не установлен
```python
def test_morph_analyzer_unavailable_handling():
    """Тест обработки случая, когда pymorphy3 не установлен"""
    import sys
    from unittest.mock import patch
    
    # Имитация отсутствия pymorphy3
    with patch.dict(sys.modules, {'pymorphy3': None}):
        from models.keyword_dictionary import KeywordDictionary
        
        # Создание экземпляра при отсутствии pymorphy3
        keyword_dict = KeywordDictionary("test_id", "test_sheet")
        
        # Проверка, что morph_analyzer равен None, но атрибут существует
        assert hasattr(keyword_dict, 'morph_analyzer')
        assert keyword_dict.morph_analyzer is None
        
        # Проверка, что методы не вызывают AttributeError
        result = keyword_dict.lemmatize_text("тест")
        assert result == "тест"  # Должно вернуть исходный текст
        
        # Проверка лемматизации слова
        result = keyword_dict.lemmatize_word("тест")
        assert result == "тест"
```

### 5. Тестирование интеграции с использованием __new__ в тестах
```python
def test_keyword_dictionary_functionality_with_new_init():
    """Тест полной функциональности KeywordDictionary при инициализации через __new__"""
    from models.keyword_dictionary import KeywordDictionary, KeywordEntry
    from collections import defaultdict, Counter
    from datetime import datetime
    
    # Создание экземпляра через __new__ как в существующих тестах
    keyword_dict = KeywordDictionary.__new__(KeywordDictionary)
    keyword_dict.spreadsheet_id = "test_id"
    keyword_dict.sheet_name = "test_sheet"
    keyword_dict.category_keywords = defaultdict(list)
    keyword_dict.keyword_to_category = {}
    keyword_dict.bigram_to_category = {}
    keyword_dict.unigram_to_categories = defaultdict(list)
    keyword_dict.usage_stats = Counter()
    keyword_dict.last_update = None
    
    # Проверка, что можно добавить ключевое слово без ошибок
    keyword_dict.add_keyword("хлеб", "Продукты", 0.8)
    
    # Проверка, что можно получить категорию без ошибок
    result = keyword_dict.get_category_by_keyword("хлеб")
    assert result is not None
    assert result[0] == "Продукты"
    
    # Проверка, что можно использовать лемматизацию без ошибок
    lemmatized = keyword_dict.lemmatize_text("хлеба")  # форма слова "хлеб" в родительном падеже
    assert isinstance(lemmatized, str)
```

## Дополнительные проверки
- Убедиться, что все существующие тесты продолжают проходить после исправления
- Проверить, что исправление не нарушает совместимость с асинхронной загрузкой
- Убедиться, что исправление работает как при наличии, так и при отсутствии pymorphy3