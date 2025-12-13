# -*- coding: utf-8 -*-
"""
Модуль для улучшенной классификации транзакций с использованием машинного обучения
"""
import re
from typing import List, Dict, Tuple, Optional
from collections import defaultdict, Counter
import math
from datetime import datetime

from models.transaction import TransactionData
from models.keyword_dictionary import KeywordDictionary
from config import logger, KEYWORDS_SPREADSHEET_ID, KEYWORDS_SHEET_NAME


class TransactionCategoryClassifier:
    """
    Класс для классификации транзакций по категориям на основе машинного обучения
    """
    def __init__(self, keyword_dict: Optional[KeywordDictionary] = None):
        self.category_keywords = defaultdict(list)  # ключевые слова для каждой категории
        self.category_features = defaultdict(lambda: defaultdict(int))  # частоты признаков по категориям
        self.global_features = defaultdict(int)  # частоты признаков глобально
        self.category_transactions_count = defaultdict(int)  # количество транзакций в каждой категории
        self.total_transactions = 0
        self.categories = set()
        
        # Интеграция с новой системой KeywordDictionary
        if keyword_dict is None:
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
        else:
            self.keyword_dict = keyword_dict
        
    def extract_features(self, text: str) -> List[str]:
        """
        Извлечение признаков из текста транзакции
        """
        # Приводим к нижнему регистру и разбиваем на слова
        text = text.lower()
        # Убираем цифры и специальные символы, оставляя только слова
        words = re.findall(r'\b[а-яёa-z]+\b', text)
        
        # Фильтруем короткие слова и добавляем n-граммы
        features = []
        for word in words:
            if len(word) >= 3:  # добавляем только слова длиной 3 символа и более
                features.append(word)
        
        # Добавляем биграммы (последовательности из 2 слов)
        for i in range(len(words) - 1):
            if len(words[i]) >= 2 and len(words[i+1]) >= 2:
                bigram = f"{words[i]}_{words[i+1]}"
                features.append(bigram)
        
        # Убираем дубликаты
        return list(set(features))
    
    def train(self, transactions: List[TransactionData]):
        """
        Обучение классификатора на исторических данных
        """
        logger.info(f"Начинаю обучение классификатора на {len(transactions)} транзакциях")
        
        for transaction in transactions:
            category = transaction.category
            self.categories.add(category)
            self.category_transactions_count[category] += 1
            self.total_transactions += 1
            
            # Извлекаем признаки из комментария, названия продавца и списка товаров
            text = f"{transaction.comment} {transaction.retailer_name} {transaction.items_list}"
            features = self.extract_features(text)
            
            # Обновляем частоты признаков
            for feature in features:
                self.category_features[category][feature] += 1
                self.global_features[feature] += 1
        
        # Обновляем ключевые слова для каждой категории
        for category in self.categories:
            category_features = self.category_features[category]
            # Выбираем топ-10 наиболее характерных признаков для категории
            sorted_features = sorted(
                category_features.items(), 
                key=lambda x: self._calculate_tfidf(x[0], category), 
                reverse=True
            )
            self.category_keywords[category] = [feature for feature, _ in sorted_features[:10]]
        
        logger.info(f"Обучение завершено. Обнаружено {len(self.categories)} категорий")
    
    def _calculate_tfidf(self, feature: str, category: str) -> float:
        """
        Расчет TF-IDF для признака в категории
        """
        # Term Frequency в категории
        category_sum = sum(self.category_features[category].values())
        if category_sum == 0:
            tf = 0  # Если сумма равна нулю, то и частота равна нулю
        else:
            tf = self.category_features[category][feature] / category_sum
        
        # Inverse Document Frequency
        category_containing_feature = sum(
            1 for cat in self.categories
            if self.category_features[cat][feature] > 0
        )
        idf = math.log(self.total_transactions / category_containing_feature) if category_containing_feature > 0 else 0
        
        return tf * idf
    
    def predict_category(self, transaction: TransactionData) -> Tuple[str, float]:
        """
        Предсказание категории для новой транзакции с возвратом уверенности
        """
        text = f"{transaction.comment} {transaction.retailer_name} {transaction.items_list}"
        features = self.extract_features(text)
        
        scores = {}
        
        for category in self.categories:
            # Счетчик для этой категории
            category_score = 0
            category_total_features = sum(self.category_features[category].values())
            
            # Оцениваем каждый признак
            for feature in features:
                if category_total_features > 0:
                    # Вероятность признака в данной категории
                    feature_prob = self.category_features[category][feature] / category_total_features
                    # Добавляем к оценке с использованием TF-IDF
                    tfidf = self._calculate_tfidf(feature, category)
                    category_score += feature_prob * (1 + tfidf)
                else:
                    # Если в категории нет признаков, пропускаем этот признак
                    continue
            
            # Учитываем априорную вероятность категории
            prior_prob = self.category_transactions_count[category] / self.total_transactions if self.total_transactions > 0 else 0
            scores[category] = category_score + prior_prob
        
        if not scores:
            # Если не найдено ни одной подходящей категории, возвращаем наиболее частую
            if self.category_transactions_count:
                most_common_category = max(self.category_transactions_count, key=self.category_transactions_count.get)
                return most_common_category, 0.5
            else:
                return "Прочее Расход", 0.0
        
        # Находим категорию с максимальной оценкой
        best_category = max(scores, key=scores.get)
        max_score = scores[best_category]
        
        # Нормализуем оценку в диапазон [0, 1]
        if max_score > 0:
            # Используем softmax-подобное преобразование для нормализации
            total_score = sum(scores.values())
            confidence = max_score / total_score if total_score > 0 else 0.0
        else:
            confidence = 0.0
            
        return best_category, confidence
    
    def suggest_category_with_improvement(self, transaction: TransactionData) -> Tuple[str, float]:
        """
        Возвращает лучшую категорию из существующих с уровнем уверенности.
        """
        return self.predict_category(transaction)
    
    def get_category_keywords(self, category: str) -> List[str]:
        """
        Возвращает ключевые слова для указанной категории.
        """
        return self.category_keywords.get(category, [])

    def get_categories_by_text(self, text: str) -> List[Tuple[str, float]]:
        """
        Получение потенциальных категорий по тексту с использованием KeywordDictionary
        """
        return self.keyword_dict.get_categories_by_text(text)

    def get_category_by_keyword(self, keyword: str) -> Optional[Tuple[str, float]]:
        """
        Получение категории по ключевому слову с использованием KeywordDictionary
        """
        return self.keyword_dict.get_category_by_keyword(keyword)

    def add_keyword(self, keyword: str, category: str, confidence: float = 0.5):
        """
        Добавление нового ключевого слова в KeywordDictionary
        """
        self.keyword_dict.add_keyword(keyword, category, confidence)


# Глобальный экземпляр классификатора
classifier = TransactionCategoryClassifier()