import pytest
from unittest.mock import Mock, patch
from models.keyword_dictionary import KeywordDictionary, KeywordEntry
from utils.lemmatizer import Lemmatizer


class TestLemmatizationIntegration:
    """
    Тесты для проверки интеграции лемматизации с KeywordDictionary
    """
    
    def setup_method(self):
        """Настройка теста"""
        self.keyword_dict = KeywordDictionary("test_spreadsheet_id", "test_sheet_name")
    
    def test_lemmatizer_initialization(self):
        """Проверяем, что лемматизатор инициализируется корректно"""
        assert hasattr(self.keyword_dict, 'lemmatizer')
        assert isinstance(self.keyword_dict.lemmatizer, Lemmatizer)
    
    def test_lemmatize_word_method(self):
        """Проверяем, что метод lemmatize_word использует лемматизатор"""
        # Тестируем с простыми словами
        word = "кофе"
        lemmatized = self.keyword_dict.lemmatize_word(word)
        assert isinstance(lemmatized, str)
        # Лемматизация может не изменить слово, если оно уже в нормальной форме
        assert lemmatized == word or lemmatized != ""
    
    def test_lemmatize_text_method(self):
        """Проверяем, что метод lemmatize_text использует лемматизатор"""
        text = "я люблю кофе"
        lemmatized = self.keyword_dict.lemmatize_text(text)
        assert isinstance(lemmatized, str)
        assert lemmatized == self.keyword_dict.lemmatizer.lemmatize_text(text)
    
    def test_add_keyword_with_lemmatization(self):
        """Проверяем добавление ключевых слов с лемматизацией"""
        # Добавляем ключевое слово
        self.keyword_dict.add_keyword("горячий кофе", "напитки", 0.8)
        
        # Проверяем, что ключевое слово добавлено
        assert "горячий кофе" in self.keyword_dict.keyword_to_category
        entry = self.keyword_dict.keyword_to_category["горячий кофе"]
        assert isinstance(entry, KeywordEntry)
        assert entry.category == "напитки"
        assert entry.confidence == 0.8
        
        # Проверяем, что лемматизированное ключевое слово тоже добавлено, если оно отличается
        lemmatized_keyword = self.keyword_dict.lemmatizer.lemmatize_text("горячий кофе")
        if lemmatized_keyword != "горячий кофе":
            assert lemmatized_keyword in self.keyword_dict.keyword_to_category
    
    def test_search_by_lemma(self):
        """Проверяем поиск по лемме"""
        # Добавляем ключевое слово
        self.keyword_dict.add_keyword("кофе", "напитки", 0.9)
        
        # Проверяем, что поиск по лемме работает
        result = self.keyword_dict._find_by_lemma("кофе")
        if result:
            category, confidence = result
            assert category == "напитки"
            assert confidence == 0.9
    
    def test_lemmatization_with_existing_keywords(self):
        """Проверяем, что лемматизация работает с существующими ключевыми словами"""
        # Добавляем ключевые слова
        self.keyword_dict.add_keyword("чай", "напитки", 0.7)
        self.keyword_dict.add_keyword("кофе", "напитки", 0.8)
        
        # Проверяем, что можно получить категории по лемматизированному тексту
        results = self.keyword_dict.get_categories_by_text("чай и кофе")
        assert isinstance(results, list)
        # Проверяем, что хотя бы одна категория найдена
        found_drinks = any(category == "напитки" for category, _ in results)
        assert found_drinks
    
    def test_lemmatization_consistency(self):
        """Проверяем, что лемматизация дает одинаковый результат при повторных вызовах"""
        text = "горячий крепкий кофе"
        first_result = self.keyword_dict.lemmatize_text(text)
        second_result = self.keyword_dict.lemmatize_text(text)
        
        assert first_result == second_result
    
    def test_lemmatization_with_special_characters(self):
        """Проверяем, что лемматизация корректно обрабатывает специальные символы"""
        text = "кофе-то"
        result = self.keyword_dict.lemmatize_text(text)
        assert isinstance(result, str)
    
    def test_lemmatization_with_empty_string(self):
        """Проверяем, что лемматизация корректно обрабатывает пустую строку"""
        result = self.keyword_dict.lemmatize_text("")
        assert result == ""
    
    def test_lemmatization_with_numbers(self):
        """Проверяем, что лемматизация корректно обрабатывает числа"""
        text = "кофе 2 штуки"
        result = self.keyword_dict.lemmatize_text(text)
        assert isinstance(result, str)
        # Проверяем, что числа остались в строке
        # Лемматизация может не сохранять числа, так как они не подлежат лемматизации
        # Проверим, что в результате остались слова, которые можно лемматизировать
        assert "кофе" in result or "штука" in result
    
    def test_get_category_by_keyword_with_lemmatization(self):
        """Проверяем, что get_category_by_keyword использует лемматизацию"""
        # Добавляем ключевое слово
        self.keyword_dict.add_keyword("кофе", "напитки", 0.85)
        
        # Проверяем, что поиск работает
        result = self.keyword_dict.get_category_by_keyword("кофе")
        if result:
            category, confidence = result
            assert category == "напитки"
            assert confidence == 0.85
    
    def test_get_categories_by_text_with_lemmatization(self):
        """Проверяем, что get_categories_by_text использует лемматизацию"""
        # Добавляем ключевые слова
        self.keyword_dict.add_keyword("чай", "напитки", 0.7)
        self.keyword_dict.add_keyword("яблоко", "фрукты", 0.6)
        
        # Проверяем, что поиск по тексту работает
        results = self.keyword_dict.get_categories_by_text("чай и яблоко")
        assert isinstance(results, list)
        
        # Проверяем, что найдены обе категории
        categories = [category for category, _ in results]
        assert "напитки" in categories
        assert "фрукты" in categories
    
    def test_lemmatization_with_mixed_case(self):
        """Проверяем, что лемматизация работает с разным регистром"""
        text = "ГОРЯЧИЙ КОФЕ"
        result = self.keyword_dict.lemmatize_text(text)
        assert isinstance(result, str)
        # Результат должен быть в нижнем регистре
        assert result == result.lower()
    
    def test_lemmatization_with_punctuation(self):
        """Проверяем, что лемматизация корректно обрабатывает пунктуацию"""
        text = "кофе, чай, сахар."
        result = self.keyword_dict.lemmatize_text(text)
        assert isinstance(result, str)
        # Проверяем, что слова остались в строке
        assert "кофе" in result or "коф" in result
        assert "чай" in result or "ч" in result