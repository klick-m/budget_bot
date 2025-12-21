# -*- coding: utf-8 -*-
"""
Модуль для классификации транзакций с использованием улучшенного словаря ключевых слов
"""
from typing import Tuple, Optional
from models.keyword_dictionary import KeywordDictionary
from models.transaction import TransactionData
from config import logger


class KeywordCategoryClassifier:
    """
    Класс для классификации транзакций по категориям на основе улучшенного словаря ключевых слов
    """
    def __init__(self, keyword_dict: Optional[KeywordDictionary] = None):
        if keyword_dict is None:
            from config import KEYWORDS_SPREADSHEET_ID, KEYWORDS_SHEET_NAME
            from config import logger
            try:
                self.keyword_dict = KeywordDictionary(KEYWORDS_SPREADSHEET_ID, KEYWORDS_SHEET_NAME)
            except Exception as e:
                logger.warning(f"⚠️ Не удалось инициализировать KeywordDictionary: {e}. Создаю пустой экземпляр.")
                # Создаем пустой экземпляр для тестирования
                self.keyword_dict = KeywordDictionary.__new__(KeywordDictionary)
                self.keyword_dict.spreadsheet_id = KEYWORDS_SPREADSHEET_ID
                self.keyword_dict.sheet_name = KEYWORDS_SHEET_NAME
                self.keyword_dict.category_keywords = {}
                self.keyword_dict.keyword_to_category = {}
                self.keyword_dict.bigram_to_category = {}
                self.keyword_dict.unigram_to_categories = {}
                self.keyword_dict.usage_stats = {}
                self.keyword_dict.last_update = None
                # Инициализируем morph_analyzer для пустого экземпляра
                self.keyword_dict._initialize_morph_analyzer()
        else:
            self.keyword_dict = keyword_dict
            
        # Убедимся, что morph_analyzer инициализирован для keyword_dict
        if not hasattr(self.keyword_dict, 'morph_analyzer'):
            self.keyword_dict._initialize_morph_analyzer()

    def predict_category(self, transaction: TransactionData) -> Tuple[Optional[str], float]:
        """
        Предсказание категории для транзакции с использованием словаря ключевых слов
        
        Args:
            transaction: Объект транзакции
            
        Returns:
            Кортеж (категория, уверенность) или (None, 0.0) если не найдено
        """
        # Формируем текст для анализа
        text = f"{transaction.comment} {transaction.retailer_name} {transaction.items_list}"
        
        # Получаем категории по тексту
        categories_by_text = self.keyword_dict.get_categories_by_text(text)
        
        if categories_by_text:
            # Возвращаем категорию с наибольшей уверенностью
            best_category, confidence = categories_by_text[0]
            return best_category, confidence
        
        # Если не найдено по тексту, пробуем по отдельным ключевым словам
        keyword_result = self.keyword_dict.get_category_by_keyword(text)
        if keyword_result:
            category, confidence = keyword_result
            return category, confidence
        
        return None, 0.0

    def suggest_category_with_improvement(self, transaction: TransactionData) -> Tuple[Optional[str], float]:
        """
        Возвращает лучшую категорию с возможностью улучшения
        """
        return self.predict_category(transaction)

    def add_keyword(self, keyword: str, category: str, confidence: float = 0.5):
        """
        Добавление нового ключевого слова в словарь
        """
        self.keyword_dict.add_keyword(keyword, category, confidence)