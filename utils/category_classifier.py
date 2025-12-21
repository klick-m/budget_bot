# -*- coding: utf-8 -*-
"""
Модуль для улучшенной классификации транзакций с использованием машинного обучения
"""
import re
import asyncio
from typing import List, Dict, Tuple, Optional
from collections import defaultdict, Counter
import math
from datetime import datetime

try:
    from pymorphy3 import MorphAnalyzer
except ImportError:
    MorphAnalyzer = None

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
        
        # Инициализация MorphAnalyzer для лемматизации
        if MorphAnalyzer:
            try:
                self.morph_analyzer = MorphAnalyzer()
            except Exception as e:
                logger.warning(f"⚠️ Не удалось инициализировать pymorphy3 MorphAnalyzer: {e}")
                self.morph_analyzer = None
        else:
            logger.warning("⚠️ pymorphy3 не установлен, лемматизация будет недоступна")
            self.morph_analyzer = None
        
        # Интеграция с новой системой KeywordDictionary
        if keyword_dict is None:
            # Создаем пустой экземпляр на время инициализации
            self.keyword_dict = KeywordDictionary.__new__(KeywordDictionary)
            self.keyword_dict.spreadsheet_id = KEYWORDS_SPREADSHEET_ID
            self.keyword_dict.sheet_name = KEYWORDS_SHEET_NAME
            self.keyword_dict.category_keywords = defaultdict(list)
            self.keyword_dict.keyword_to_category = {}
            self.keyword_dict.bigram_to_category = {}
            self.keyword_dict.unigram_to_categories = {}
            self.keyword_dict.usage_stats = Counter()
            self.keyword_dict.last_update = None
            self.keyword_dict.sheets_client = None
        else:
            self.keyword_dict = keyword_dict
            
    async def load(self):
        """Асинхронная инициализация KeywordDictionary"""
        try:
            # Если keyword_dict еще не инициализирован как полноценный объект, делаем это
            if not hasattr(self.keyword_dict, 'async_load_from_sheets'):
                self.keyword_dict = KeywordDictionary(
                    spreadsheet_id=KEYWORDS_SPREADSHEET_ID,
                    sheet_name=KEYWORDS_SHEET_NAME
                )
            
            # Вызываем асинхронную инициализацию
            await self.keyword_dict.load()
            
        except Exception as e:
            logger.error(f"❌ Ошибка при инициализации KeywordDictionary: {e}")
            
    # Удаляем старый метод delayed_init, так как он заменен на async_init
         
    def extract_features(self, text: str) -> List[str]:
        """
        Извлечение признаков из текста транзакции
        """
        # Приводим к нижнему регистру и разбиваем на слова
        text = text.lower()
        # Убираем цифры и специальные символы, оставляя только слова
        words = re.findall(r'\b[а-яёa-z]+\b', text)
        
        # Лемматизируем слова, если доступен morph_analyzer
        if self.morph_analyzer:
            lemmatized_words = []
            for word in words:
                if len(word) >= 2:  # лемматизируем только слова длиной 2 символа и более
                    try:
                        parsed_word = self.morph_analyzer.parse(word)[0]
                        lemma = parsed_word.normal_form
                        lemmatized_words.append(lemma)
                    except Exception:
                        # Если лемматизация не удалась, используем исходное слово
                        lemmatized_words.append(word)
            words = lemmatized_words
        
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
    
    def lemmatize_word(self, word: str) -> str:
        """
        Лемматизация отдельного слова
        """
        if self.morph_analyzer and len(word) >= 2:
            try:
                parsed_word = self.morph_analyzer.parse(word)[0]
                return parsed_word.normal_form
            except Exception:
                # Если лемматизация не удалась, возвращаем исходное слово
                return word
        return word
    
    def lemmatize_text(self, text: str) -> str:
        """
        Лемматизация всего текста
        """
        if not self.morph_analyzer:
            return text.lower()
            
        words = re.findall(r'\b[а-яёa-z]+\b', text.lower())
        lemmatized_words = [self.lemmatize_word(word) for word in words]
        return ' '.join(lemmatized_words)
    
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

    def add_keyword(self, keyword: str, category: str, confidence: float = 0.5, save_to_sheet: bool = True):
        """
        Добавление нового ключевого слова в KeywordDictionary
        """
        self.keyword_dict.add_keyword(keyword, category, confidence, save_to_sheet=save_to_sheet)

    def learn_keyword(self, text: str, category: str):
        """
        Обучение классификатора новому соответствию текста и категории.
        Добавляет пару текст-категория в словарь ключевых слов и сохраняет в Google Sheets.
        """
        # Очистка текста - оставляем только слова, убираем числа
        cleaned_text = re.sub(r'\d+', '', text.lower().strip())
        cleaned_text = re.sub(r'\s+', ' ', cleaned_text).strip()
        
        # Проверяем, не является ли текст слишком общим или пустым после очистки
        if not cleaned_text or len(cleaned_text) < 2:
            return  # Не учимся на пустых или слишком коротких текстах
        
        # Проверяем, не является ли текст просто числом или содержит только числа
        if not re.search(r'[а-яёa-z]', text.lower()):
            return # Не учимся на текстах без букв
        
        # Нормализуем текст с помощью метода из KeywordDictionary
        normalized_text = self.keyword_dict.normalize_text(cleaned_text)
        
        # Лемматизируем текст, если доступен morph_analyzer
        lemmatized_text = self.lemmatize_text(cleaned_text) if self.morph_analyzer else normalized_text
        
        # Добавляем ключевое слово в KeywordDictionary
        self.add_keyword(normalized_text, category)
        
        # Также добавляем лемматизированную версию
        if lemmatized_text != normalized_text:
            self.add_keyword(lemmatized_text, category, save_to_sheet=False)  # Не сохраняем лемму отдельно в Google Sheets
        
        # Обновляем локальные данные
        self.categories.add(category)
        if hasattr(self, 'category_keywords'):
            if category not in self.category_keywords:
                self.category_keywords[category] = []
            if normalized_text not in self.category_keywords[category]:
                self.category_keywords[category].append(normalized_text)
            # Также добавляем лемму, если она отличается
            if lemmatized_text != normalized_text and lemmatized_text not in self.category_keywords[category]:
                self.category_keywords[category].append(lemmatized_text)
        
        logger.info(f"Добавлено новое ключевое слово: '{normalized_text}' -> '{category}' (с леммой: '{lemmatized_text}')")

    def predict(self, text: str) -> str:
        """
        Предсказание категории для текста с проверкой на валидность категории.
        Возвращает только валидные категории из известных или "Другое" по умолчанию.
        """
        # Сначала пробуем найти категорию по ключевым словам
        keyword_result = self.get_category_by_keyword(text)
        if keyword_result:
            category, confidence = keyword_result
            # Проверяем, что категория валидна (существует в системе)
            if category in self.categories or self._is_valid_category(category):
                return category
        
        # Если по ключевым словам не нашли, пробуем ML-классификацию
        # Но перед этим создаем фейковую транзакцию для использования существующей логики
        from models.transaction import TransactionData
        fake_transaction = TransactionData(
            type="Расход",
            category="",  # Пока не знаем
            amount=0.0,
            comment=text,
            username="",
            retailer_name="",
            items_list="",
            payment_info="",
            transaction_dt=datetime.now()
        )
        
        predicted_category, confidence = self.predict_category(fake_transaction)
        
        # Проверяем, что предсказанная категория валидна
        if predicted_category in self.categories or self._is_valid_category(predicted_category):
            return predicted_category
        else:
            # Если категория не валидна, возвращаем "Другое" или "Не распознано"
            return "Другое"
    
    def _is_valid_category(self, category: str) -> bool:
        """
        Проверяет, является ли категория валидной (существует в системе).
        """
        # Проверяем, есть ли категория в известных категориях или в KeywordDictionary
        return (category in self.categories or
                category in self.keyword_dict.category_keywords if hasattr(self.keyword_dict, 'category_keywords') else True)


# Глобальный экземпляр классификатора
classifier = TransactionCategoryClassifier()