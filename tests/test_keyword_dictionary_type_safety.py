import pytest
import asyncio
from unittest.mock import Mock, patch, MagicMock
from models.keyword_dictionary import KeywordDictionary, KeywordEntry
from datetime import datetime


class TestKeywordDictionaryTypeSafety:
    """
    Тесты для проверки типобезопасности KeywordDictionary
    и отсутствия ситуаций, когда в словарях оказываются строки вместо KeywordEntry
    """

    def setup_method(self):
        """Настройка теста"""
        self.keyword_dict = KeywordDictionary("test_spreadsheet_id", "test_sheet_name")

    def test_initialization_creates_empty_dictionaries_with_correct_types(self):
        """Проверяем, что при инициализации создаются пустые словари с правильными типами"""
        assert isinstance(self.keyword_dict.category_keywords, dict)
        assert isinstance(self.keyword_dict.keyword_to_category, dict)
        assert isinstance(self.keyword_dict.bigram_to_category, dict)
        assert isinstance(self.keyword_dict.unigram_to_categories, dict)

        # Проверяем, что словари пусты
        assert len(self.keyword_dict.category_keywords) == 0
        assert len(self.keyword_dict.keyword_to_category) == 0
        assert len(self.keyword_dict.bigram_to_category) == 0
        assert len(self.keyword_dict.unigram_to_categories) == 0

    def test_add_keyword_creates_proper_keyword_entry(self):
        """Проверяем, что при добавлении ключевого слова создается объект KeywordEntry"""
        self.keyword_dict.add_keyword("кофе", "еда", 0.8)
        
        # Проверяем, что в словаре находится объект KeywordEntry, а не строка
        keyword_entry = self.keyword_dict.keyword_to_category.get("кофе")
        assert keyword_entry is not None
        assert isinstance(keyword_entry, KeywordEntry)
        assert keyword_entry.keyword == "кофе"
        assert keyword_entry.category == "еда"
        assert keyword_entry.confidence == 0.8

    def test_get_category_by_keyword_returns_proper_types(self):
        """Проверяем, что метод get_category_by_keyword возвращает правильные типы и не содержит строк"""
        # Добавляем тестовое ключевое слово
        self.keyword_dict.add_keyword("чай", "еда", 0.7)
        
        # Проверяем, что результат не содержит строк вместо KeywordEntry
        result = self.keyword_dict.get_category_by_keyword("чай")
        assert result is not None
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], str)  # категория
        assert isinstance(result[1], float)  # уверенность

        # Проверяем, что в словарях нет строк вместо KeywordEntry
        entry = self.keyword_dict.keyword_to_category.get("чай")
        assert isinstance(entry, KeywordEntry)

    def test_get_categories_by_text_returns_proper_types(self):
        """Проверяем, что метод get_categories_by_text возвращает правильные типы"""
        # Добавляем тестовое ключевое слово
        self.keyword_dict.add_keyword("молоко", "еда", 0.6)
        
        # Проверяем, что результат не содержит строк вместо KeywordEntry
        results = self.keyword_dict.get_categories_by_text("молоко")
        assert isinstance(results, list)
        
        # Проверяем, что в словарях нет строк вместо KeywordEntry
        entry = self.keyword_dict.keyword_to_category.get("молоко")
        assert isinstance(entry, KeywordEntry)

    def test_data_integrity_after_multiple_operations(self):
        """Проверяем целостность данных после нескольких операций добавления и поиска"""
        # Добавляем несколько ключевых слов
        self.keyword_dict.add_keyword("банан", "фрукты", 0.9)
        self.keyword_dict.add_keyword("яблоко", "фрукты", 0.85)
        self.keyword_dict.add_keyword("хлеб", "хлебобулочное", 0.75)
        
        # Проверяем, что все элементы в словарях являются KeywordEntry
        for keyword, entry in self.keyword_dict.keyword_to_category.items():
            assert isinstance(entry, KeywordEntry), f"Entry для ключа '{keyword}' не является KeywordEntry, а является {type(entry)}"
        
        for category, entries in self.keyword_dict.category_keywords.items():
            for entry in entries:
                assert isinstance(entry, KeywordEntry), f"Entry в категории '{category}' не является KeywordEntry, а является {type(entry)}"
        
        for unigram, entries in self.keyword_dict.unigram_to_categories.items():
            for entry in entries:
                assert isinstance(entry, KeywordEntry), f"Entry в unigram '{unigram}' не является KeywordEntry, а является {type(entry)}"
        
        for bigram, entry in self.keyword_dict.bigram_to_category.items():
            assert isinstance(entry, KeywordEntry), f"Entry для bigram '{bigram}' не является KeywordEntry, а является {type(entry)}"

    def test_hotfix_scenarios_no_longer_necessary(self):
        """Проверяем, что сценарии, для которых требовались hotfix'ы, больше не происходят"""
        # Создаем ситуацию, которая раньше могла привести к появлению строк в словаре
        # Добавляем ключевые слова
        self.keyword_dict.add_keyword("сыр", "молочные продукты", 0.8)
        self.keyword_dict.add_keyword("сыр твердый", "молочные продукты", 0.9)
        
        # Проверяем, что при поиске по ключевому слову не возникает строк вместо KeywordEntry
        result = self.keyword_dict.get_category_by_keyword("сыр")
        assert result is None or isinstance(result, tuple)
        
        # Проверяем, что все элементы по-прежнему являются KeywordEntry
        for keyword, entry in self.keyword_dict.keyword_to_category.items():
            assert isinstance(entry, KeywordEntry), f"Entry для ключа '{keyword}' не является KeywordEntry, а является {type(entry)}"
        
        # Проверяем поиск по тексту
        text_results = self.keyword_dict.get_categories_by_text("сыр твердый")
        assert isinstance(text_results, list)
        
        # Проверяем, что в биграммах тоже все корректно
        words = "сыр твердый".split()
        if len(words) > 1:
            bigram = f"{words[0]} {words[1]}"
            bigram_entry = self.keyword_dict.bigram_to_category.get(bigram)
            if bigram_entry is not None:
                assert isinstance(bigram_entry, KeywordEntry), f"Bigram entry для '{bigram}' не является KeywordEntry, а является {type(bigram_entry)}"

    def test_keyword_entry_attributes_integrity(self):
        """Проверяем, что все атрибуты KeywordEntry сохраняются корректно"""
        self.keyword_dict.add_keyword("шоколад", "сладости", 0.95)
        
        entry = self.keyword_dict.keyword_to_category.get("шоколад")
        assert isinstance(entry, KeywordEntry)
        
        # Проверяем все атрибуты
        assert hasattr(entry, 'keyword')
        assert hasattr(entry, 'category')
        assert hasattr(entry, 'confidence')
        assert hasattr(entry, 'usage_count')
        assert hasattr(entry, 'last_used')
        assert hasattr(entry, 'created_at')
        
        # Проверяем значения атрибутов
        assert entry.keyword == "шоколад"
        assert entry.category == "сладости"
        assert entry.confidence == 0.95
        assert entry.usage_count == 0  # Пока не использовался
        assert entry.last_used is None  # Пока не использовался
        assert isinstance(entry.created_at, datetime)

    @pytest.mark.asyncio
    async def test_async_operations_maintain_type_safety(self):
        """Проверяем, что асинхронные операции также поддерживают типобезопасность"""
        # Создаем mock для асинхронной загрузки данных
        with patch.object(self.keyword_dict, 'async_load_from_sheets') as mock_load:
            mock_load.return_value = None  # Заглушка для асинхронной загрузки
            
            # Вызываем асинхронную загрузку
            await self.keyword_dict.load()
            
            # Проверяем, что словари по-прежнему имеют правильные типы
            assert isinstance(self.keyword_dict.category_keywords, dict)
            assert isinstance(self.keyword_dict.keyword_to_category, dict)
            assert isinstance(self.keyword_dict.bigram_to_category, dict)
            assert isinstance(self.keyword_dict.unigram_to_categories, dict)

    def test_manual_string_assignment_raises_type_error(self):
        """Тест, который проверяет, что при попытке использовать строки вместо KeywordEntry выбрасывается исключение"""
        # Добавляем нормальное ключевое слово
        self.keyword_dict.add_keyword("чай", "напитки", 0.7)
        
        # Искусственно вставляем строку в место, где должен быть KeywordEntry
        # Это воспроизводит ситуацию, которая может возникнуть в результате ошибки
        self.keyword_dict.keyword_to_category["чай"] = "напитки"  # Это строка, а не KeywordEntry
        
        # Проверяем, что теперь в словаре находится строка
        entry = self.keyword_dict.keyword_to_category["чай"]
        assert isinstance(entry, str), "Entry должен быть строкой для проверки выбрасывания исключения"
        
        # Теперь вызываем get_category_by_keyword - это должно выбросить TypeError
        with pytest.raises(TypeError, match="должен быть KeywordEntry"):
            self.keyword_dict.get_category_by_keyword("чай")

    def test_manual_string_assignment_in_unigram_raises_type_error(self):
        """Тест, который проверяет, что при попытке использовать строки вместо KeywordEntry в unigram словаре выбрасывается исключение"""
        # Добавляем ключевое слово, которое будет добавлено в unigram
        self.keyword_dict.add_keyword("горячий кофе", "напитки", 0.8)  # Это создаст "горячий" и "кофе" в unigram
        
        # Искусственно вставляем строку в unigram список
        # Находим слово "кофе" в unigram_to_categories и заменяем первый элемент на строку
        if "кофе" in self.keyword_dict.unigram_to_categories:
            original_entry = self.keyword_dict.unigram_to_categories["кофе"][0]
            self.keyword_dict.unigram_to_categories["кофе"][0] = "напитки"  # Это строка, а не KeywordEntry
            
            # Проверяем, что теперь в списке находится строка
            entry = self.keyword_dict.unigram_to_categories["кофе"][0]
            assert isinstance(entry, str), "Entry должен быть строкой для проверки выбрасывания исключения"
            
            # Вызываем get_category_by_keyword с отдельным словом "кофе", чтобы проверить unigram
            with pytest.raises(TypeError, match="должен быть KeywordEntry"):
                self.keyword_dict.get_category_by_keyword("кофе")

    def test_manual_string_assignment_in_bigram_raises_type_error(self):
        """Тест, который проверяет, что при попытке использовать строки вместо KeywordEntry в bigram словаре выбрасывается исключение"""
        # Добавляем ключевое слово с несколькими словами, чтобы создать биграмму
        self.keyword_dict.add_keyword("горячий крепкий кофе", "напитки", 0.9)  # Это создаст биграммы "горячий крепкий" и "крепкий кофе"
        
        # Находим биграмму и искусственно вставляем строку
        bigrams = list(self.keyword_dict.bigram_to_category.keys())
        if len(bigrams) >= 2:  # Убедимся, что у нас есть хотя бы 2 биграммы
            bigram_key = bigrams[0] # Берем первую биграмму
            original_entry = self.keyword_dict.bigram_to_category[bigram_key]
            self.keyword_dict.bigram_to_category[bigram_key] = "напитки"  # Это строка, а не KeywordEntry
            
            # Проверяем, что теперь в словаре находится строка
            entry = self.keyword_dict.bigram_to_category[bigram_key]
            assert isinstance(entry, str), "Entry должен быть строкой для проверки выбрасывания исключения"
            
            # Вызываем get_category_by_keyword с фразой, содержащей биграмму, чтобы проверить биграмму
            with pytest.raises(TypeError, match="должен быть KeywordEntry"):
                # Используем фразу, которая будет разбита на слова, включая нашу биграмму
                words = bigram_key.split()
                search_phrase = f"{words[0]} {words[1]} что-то"
                self.keyword_dict.get_category_by_keyword(search_phrase)

    def test_lemmatization_does_not_create_string_entries(self):
        """Тест, который проверяет, что лемматизация не создает строк вместо KeywordEntry"""
        # Добавляем ключевое слово с лемматизацией
        self.keyword_dict.add_keyword("кофе", "напитки", 0.8)
        
        # Проверяем, что все элементы по-прежнему KeywordEntry после лемматизации
        for keyword, entry in self.keyword_dict.keyword_to_category.items():
            assert isinstance(entry, KeywordEntry), f"Entry для ключа '{keyword}' не является KeywordEntry, а является {type(entry)}"
        
        # Проверяем, что лемматизация работает корректно
        result = self.keyword_dict.get_category_by_keyword("кофе")
        assert result is None or isinstance(result, tuple)
        
        # Проверяем, что при лемматизации в словаре не появляются строки
        for keyword, entry in self.keyword_dict.keyword_to_category.items():
            assert isinstance(entry, KeywordEntry), f"Entry для ключа '{keyword}' не является KeywordEntry после лемматизации, а является {type(entry)}"

    def test_type_validation_in_all_search_methods(self):
        """Тест, который проверяет, что все методы поиска имеют валидацию типов"""
        # Добавляем ключевые слова
        self.keyword_dict.add_keyword("яблоко", "фрукты", 0.7)
        self.keyword_dict.add_keyword("яблочный сок", "напитки", 0.8)
        
        # Проверяем, что все методы поиска корректно обрабатывают типы
        result1 = self.keyword_dict.get_category_by_keyword("яблоко")
        assert result1 is None or isinstance(result1, tuple)
        
        result2 = self.keyword_dict.get_categories_by_text("яблоко")
        assert isinstance(result2, list)
        
        # Проверяем, что в словарях все еще находятся KeywordEntry
        for keyword, entry in self.keyword_dict.keyword_to_category.items():
            assert isinstance(entry, KeywordEntry)
        
        for unigram, entries in self.keyword_dict.unigram_to_categories.items():
            for entry in entries:
                assert isinstance(entry, KeywordEntry)
        
        for bigram, entry in self.keyword_dict.bigram_to_category.items():
            assert isinstance(entry, KeywordEntry)