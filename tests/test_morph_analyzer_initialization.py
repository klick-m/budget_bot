import pytest
import sys
from unittest.mock import Mock, patch
from models.keyword_dictionary import KeywordDictionary
from utils.category_classifier import TransactionCategoryClassifier
from utils.keyword_classifier import KeywordCategoryClassifier


def test_keyword_dictionary_morph_analyzer_initialization():
    """Тест проверяет, что morph_analyzer инициализируется корректно при обычной инициализации"""
    # Создаем фейковые параметры
    fake_spreadsheet_id = "fake_id"
    fake_sheet_name = "fake_sheet"
    
    # Создаем экземпляр KeywordDictionary
    keyword_dict = KeywordDictionary(fake_spreadsheet_id, fake_sheet_name)
    
    # Проверяем, что morph_analyzer существует как атрибут
    assert hasattr(keyword_dict, 'morph_analyzer')
    # Проверяем, что morph_analyzer может быть None или объектом MorphAnalyzer
    assert keyword_dict.morph_analyzer is None or hasattr(keyword_dict.morph_analyzer, 'parse')


def test_keyword_dictionary_morph_analyzer_via_new_fixed():
    """Тест проверяет, что при создании через __new__ и последующей инициализации morph_analyzer становится доступен"""
    # Создаем экземпляр через __new__
    keyword_dict = KeywordDictionary.__new__(KeywordDictionary)
    keyword_dict.spreadsheet_id = "fake_id"
    keyword_dict.sheet_name = "fake_sheet"
    keyword_dict.category_keywords = {}
    keyword_dict.keyword_to_category = {}
    keyword_dict.bigram_to_category = {}
    keyword_dict.unigram_to_categories = {}
    keyword_dict.usage_stats = {}
    keyword_dict.last_update = None
    keyword_dict.sheets_client = None
    
    # Проверяем, что morph_analyzer НЕ существует как атрибут до инициализации
    assert not hasattr(keyword_dict, 'morph_analyzer'), "morph_analyzer должен отсутствовать при создании через __new__"
    
    # Инициализируем morph_analyzer
    keyword_dict._initialize_morph_analyzer()
    
    # Проверяем, что morph_analyzer теперь существует как атрибут
    assert hasattr(keyword_dict, 'morph_analyzer'), "morph_analyzer должен существовать после инициализации"
    
    # Проверяем, что мы можем вызвать метод, который использует morph_analyzer, без AttributeError
    result = keyword_dict.lemmatize_text("тест")
    assert isinstance(result, str)


def test_category_classifier_morph_analyzer_initialization():
    """Тест проверяет, что morph_analyzer инициализируется корректно в CategoryClassifier"""
    classifier = TransactionCategoryClassifier()
    
    # Проверяем, что morph_analyzer существует как атрибут
    assert hasattr(classifier, 'morph_analyzer')
    # Проверяем, что morph_analyzer может быть None или объектом MorphAnalyzer
    assert classifier.morph_analyzer is None or hasattr(classifier.morph_analyzer, 'parse')


def test_category_classifier_morph_analyzer_with_new_keyword_dict_fixed():
    """Тест проверяет, что при использовании KeywordDictionary, созданного через __new__, morph_analyzer инициализируется корректно"""
    # Создаем KeywordDictionary через __new__ (как в текущем коде)
    fake_spreadsheet_id = "fake_id"
    fake_sheet_name = "fake_sheet"
    keyword_dict = KeywordDictionary.__new__(KeywordDictionary)
    keyword_dict.spreadsheet_id = fake_spreadsheet_id
    keyword_dict.sheet_name = fake_sheet_name
    keyword_dict.category_keywords = {}
    keyword_dict.keyword_to_category = {}
    keyword_dict.bigram_to_category = {}
    keyword_dict.unigram_to_categories = {}
    keyword_dict.usage_stats = {}
    keyword_dict.last_update = None
    keyword_dict.sheets_client = None
    
    # Создаем classifier с этим keyword_dict
    classifier = TransactionCategoryClassifier(keyword_dict=keyword_dict)
    
    # Проверяем, что morph_analyzer у classifier существует
    assert hasattr(classifier, 'morph_analyzer')
    
    # Проверяем, что morph_analyzer также инициализирован у keyword_dict
    assert hasattr(keyword_dict, 'morph_analyzer'), "morph_analyzer должен быть инициализирован для keyword_dict"
    
    # Проверяем, что мы можем вызвать метод, который использует morph_analyzer без ошибки
    result = classifier.lemmatize_text("тестовый текст")
    assert isinstance(result, str)


def test_keyword_classifier_morph_analyzer_with_new_keyword_dict_fixed():
    """Тест проверяет, что morph_analyzer инициализируется корректно в KeywordDictionary, созданном через __new__"""
    # Создаем KeywordDictionary через __new__ (как в текущем коде)
    fake_spreadsheet_id = "fake_id"
    fake_sheet_name = "fake_sheet"
    keyword_dict = KeywordDictionary.__new__(KeywordDictionary)
    keyword_dict.spreadsheet_id = fake_spreadsheet_id
    keyword_dict.sheet_name = fake_sheet_name
    keyword_dict.category_keywords = {}
    keyword_dict.keyword_to_category = {}
    keyword_dict.bigram_to_category = {}
    keyword_dict.unigram_to_categories = {}
    keyword_dict.usage_stats = {}
    keyword_dict.last_update = None
    
    # Создаем classifier с этим keyword_dict
    classifier = KeywordCategoryClassifier(keyword_dict=keyword_dict)
    
    # Проверяем, что morph_analyzer инициализирован для keyword_dict
    assert hasattr(keyword_dict, 'morph_analyzer'), "morph_analyzer должен быть инициализирован для keyword_dict"
    
    # Проверяем, что мы можем вызвать метод, который использует morph_analyzer без ошибки
    result = keyword_dict.lemmatize_text("тест")
    assert isinstance(result, str)


if __name__ == "__main__":
    pytest.main([__file__])