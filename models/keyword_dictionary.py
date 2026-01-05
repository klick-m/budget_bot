import re
from collections import defaultdict, Counter
from datetime import datetime
from typing import Dict, List, Tuple, Optional, Set
from dataclasses import dataclass, field

try:
    from pymorphy3 import MorphAnalyzer
except ImportError:
    MorphAnalyzer = None

from config import logger
from sheets.client import GoogleSheetsClient
from utils.lemmatizer import Lemmatizer


@dataclass
class KeywordEntry:
    """Класс для хранения информации о ключевом слове"""
    keyword: str
    category: str
    confidence: float
    usage_count: int = 0
    last_used: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.now)


class KeywordDictionary:
    """
    Класс для системы словаря ключевых слов с категориями и уровнями уверенности.
    Поддерживает хранение ключевых слов по категориям с весами, обратный индекс для быстрого поиска,
    статистику использования и биграммы.
    """
    
    def __init__(self, spreadsheet_id: str, sheet_name: str):
        """
        Инициализация словаря ключевых слов
        
        Args:
            spreadsheet_id: ID таблицы Google Sheets
            sheet_name: Название листа в таблице
        """
        self.spreadsheet_id = spreadsheet_id
        self.sheet_name = sheet_name
        self.sheets_client = GoogleSheetsClient()
        
        # Основной словарь: категория -> список ключевых слов
        self.category_keywords: Dict[str, List[KeywordEntry]] = defaultdict(list)
        
        # Обратный индекс: ключевое слово -> категория
        self.keyword_to_category: Dict[str, KeywordEntry] = {}
        
        # Индекс биграмм: биграмма -> категория
        self.bigram_to_category: Dict[str, KeywordEntry] = {}
        
        # Индекс униграмм (отдельных слов) для быстрого поиска
        self.unigram_to_categories: Dict[str, List[KeywordEntry]] = defaultdict(list)
        
        # Статистика использования
        self.usage_stats: Counter = Counter()
        
        # Дата последнего обновления
        self.last_update: Optional[datetime] = None
        
        # Инициализация Lemmatizer для лемматизации
        self.lemmatizer = Lemmatizer()
    
    def _initialize_morph_analyzer(self):
        """Метод для инициализации morph_analyzer, который можно вызывать отдельно"""
        # Этот метод больше не используется, так как лемматизация вынесена в отдельный класс
        pass
    
    def load_from_sheets(self):
        """Загрузка данных из Google Sheets"""
        try:
            # Получаем данные из Google Sheets (один batch-запрос)
            data = self.sheets_client.get_sheet_data(self.spreadsheet_id, self.sheet_name)
            
            # Очищаем текущие данные
            self.category_keywords.clear()
            self.keyword_to_category.clear()
            self.bigram_to_category.clear()
            self.unigram_to_categories.clear()
            
            # Обрабатываем полученные данные (все в памяти, без дополнительных API-вызовов)
            for row in data:
                if len(row) >= 3:  # Убедимся, что есть все необходимые столбцы
                    keyword = row[0].strip().lower()
                    category = row[1].strip()
                    try:
                        confidence = float(row[2])
                    except ValueError:
                        confidence = 0.5  # Значение по умолчанию при ошибке
                    
                    # Создаем новый или обновляем существующий элемент
                    if keyword in self.keyword_to_category:
                       # Обновляем существующий элемент
                       entry = self.keyword_to_category[keyword]
                       self._validate_keyword_entry(entry, f" при обновлении из таблицы для ключа '{keyword}'")
                       entry.category = category
                       entry.confidence = confidence
                    else:
                       # Создаем новый элемент
                       entry = KeywordEntry(
                           keyword=keyword,
                           category=category,
                           confidence=confidence
                       )
                       self.keyword_to_category[keyword] = entry
                    
                    # Добавляем в категорию
                    self.category_keywords[category].append(entry)
                    
                    # Добавляем в индекс униграмм
                    words = keyword.split()
                    for word in words:
                        if word not in self.unigram_to_categories:
                            self.unigram_to_categories[word] = []
                        self._validate_keyword_entry(entry, f" при добавлении в униграммы из таблицы для слова '{word}'")
                        self.unigram_to_categories[word].append(entry)
                    
                    # Добавляем биграммы, если слов в фразе больше одного
                    if len(words) > 1:
                        for i in range(len(words) - 1):
                            bigram = f"{words[i]} {words[i + 1]}"
                            self._validate_keyword_entry(entry, f" при добавлении в биграммы из таблицы '{bigram}'")
                            self.bigram_to_category[bigram] = entry
            
            self.last_update = datetime.now()
            
        except Exception as e:
            print(f"Ошибка при загрузке данных из Google Sheets: {e}")

    async def async_load_from_sheets(self):
        """Асинхронная загрузка данных из Google Sheets с использованием кэширования"""
        try:
            # Импортируем асинхронный клиент
            from sheets.client import get_sheet_data_with_cache
            # Получаем данные с использованием кэширования
            data = await get_sheet_data_with_cache(self.sheet_name)
            
            # Очищаем текущие данные
            self.category_keywords.clear()
            self.keyword_to_category.clear()
            self.bigram_to_category.clear()
            self.unigram_to_categories.clear()
            
            # Обрабатываем полученные данные (все в памяти, без дополнительных API-вызовов)
            for row in data:
                if len(row) >= 3:  # Убедимся, что есть все необходимые столбцы
                    keyword = row[0].strip().lower()
                    category = row[1].strip()
                    try:
                        confidence = float(row[2])
                    except ValueError:
                        confidence = 0.5  # Значение по умолчанию при ошибке
                    
                    # Создаем новый или обновляем существующий элемент
                    if keyword in self.keyword_to_category:
                       # Обновляем существующий элемент
                       entry = self.keyword_to_category[keyword]
                       self._validate_keyword_entry(entry, f" при асинхронном обновлении из таблицы для ключа '{keyword}'")
                       entry.category = category
                       entry.confidence = confidence
                    else:
                       # Создаем новый элемент
                       entry = KeywordEntry(
                           keyword=keyword,
                           category=category,
                           confidence=confidence
                       )
                       self.keyword_to_category[keyword] = entry
                    
                    # Добавляем в категорию
                    self.category_keywords[category].append(entry)
                    
                    # Добавляем в индекс униграмм
                    words = keyword.split()
                    for word in words:
                        if word not in self.unigram_to_categories:
                            self.unigram_to_categories[word] = []
                        self._validate_keyword_entry(entry, f" при добавлении в униграммы при асинхронной загрузке для слова '{word}'")
                        self.unigram_to_categories[word].append(entry)
                    
                    # Добавляем биграммы, если слов в фразе больше одного
                    if len(words) > 1:
                        for i in range(len(words) - 1):
                            bigram = f"{words[i]} {words[i + 1]}"
                            self._validate_keyword_entry(entry, f" при добавлении в биграммы при асинхронной загрузке '{bigram}'")
                            self.bigram_to_category[bigram] = entry
            
            self.last_update = datetime.now()
            
            # Убедимся, что лемматизатор инициализирован
            if not hasattr(self, 'lemmatizer'):
                self.lemmatizer = Lemmatizer()
            
        except Exception as e:
            print(f"Ошибка при асинхронной загрузке данных из Google Sheets: {e}")

    def update_from_sheets(self):
        """Обновление данных из Google Sheets - теперь вызывает асинхронный метод
        Метод изменен, чтобы избежать использования asyncio.run() внутри синхронной функции
        """
        import asyncio
        try:
            # Проверяем, запущен ли уже цикл
            loop = asyncio.get_running_loop()
            # Если цикл запущен, создаем задачу
            asyncio.create_task(self.async_load_from_sheets())
        except RuntimeError:
            # Если цикл не запущен, мы не можем запустить асинхронную функцию из синхронной
            # Вместо этого, пользователь должен вызвать асинхронный метод напрямую
            raise RuntimeError("Невозможно вызвать update_from_sheets из синхронного контекста без запущенного цикла. "
                             "Используйте async_load_from_sheets напрямую в асинхронном контексте.")

    async def load(self):
        """Асинхронный метод для загрузки данных из Google Sheets"""
        await self.async_load_from_sheets()
    
    async def update_dictionary(self):
        """Метод для обновления словаря - теперь асинхронный"""
        await self.async_load_from_sheets()
    
    def get_category_by_keyword(self, keyword: str) -> Optional[Tuple[str, float]]:
        """
        Получение категории по ключевому слову
        
        Args:
            keyword: Ключевое слово для поиска
            
        Returns:
            Кортеж (категория, уверенность) или None, если не найдено
        """
        keyword_lower = keyword.strip().lower()
        
        # Пробуем найти точное совпадение
        if keyword_lower in self.keyword_to_category:
            entry = self.keyword_to_category[keyword_lower]
            self._validate_keyword_entry(entry, f" для ключа '{keyword_lower}'")
            self._update_usage_stats(entry)
            return entry.category, entry.confidence
        
        # Пробуем найти по биграммам
        words = keyword_lower.split()
        if len(words) >= 2:
            for i in range(len(words) - 1):
                bigram = f"{words[i]} {words[i + 1]}"
                if bigram in self.bigram_to_category:
                    entry = self.bigram_to_category[bigram]
                    self._validate_keyword_entry(entry, f" для биграммы '{bigram}'")
                    self._update_usage_stats(entry)
                    return entry.category, entry.confidence
        
        # Пробуем найти по отдельным словам (униграммам)
        max_confidence = 0.0
        best_category = None
        
        for word in words:
            if word in self.unigram_to_categories:
                for entry in self.unigram_to_categories[word]:
                    self._validate_keyword_entry(entry, f" для униграммы '{word}'")
                    if entry.confidence > max_confidence:
                        max_confidence = entry.confidence
                        best_category = entry.category
        
        if best_category:
            # Создаем фиктивную запись для обновления статистики
            fake_entry = KeywordEntry(
                keyword=keyword_lower,
                category=best_category,
                confidence=max_confidence
            )
            self._update_usage_stats(fake_entry)
            return best_category, max_confidence
        
        # Если обычный поиск не дал результата, пробуем найти по лемме
        lemma_result = self._find_by_lemma(keyword)
        if lemma_result:
            return lemma_result
        
        return None
    
    def _validate_keyword_entry(self, entry, context: str = ""):
        """Валидация, что entry является экземпляром KeywordEntry"""
        if not isinstance(entry, KeywordEntry):
            raise TypeError(f"Entry{context} должен быть KeywordEntry, но является {type(entry)}")
    
    def _update_usage_stats(self, entry: KeywordEntry):
        """Обновление статистики использования для элемента"""
        self._validate_keyword_entry(entry, " для обновления статистики")
        entry.usage_count += 1
        entry.last_used = datetime.now()
        self.usage_stats[entry.keyword] += 1
    
    def get_categories_by_text(self, text: str) -> List[Tuple[str, float]]:
        """
        Получение потенциальных категорий по тексту с учетом биграмм
        
        Args:
            text: Текст для анализа
            
        Returns:
            Список кортежей (категория, уверенность)
        """
        results = []
        text_lower = text.strip().lower()
        words = text_lower.split()
        
        # Проверяем точные совпадения
        if text_lower in self.keyword_to_category:
            entry = self.keyword_to_category[text_lower]
            self._validate_keyword_entry(entry, f" для точного совпадения '{text_lower}'")
            self._update_usage_stats(entry)
            results.append((entry.category, entry.confidence))
        
        # Проверяем биграммы
        for i in range(len(words) - 1):
            bigram = f"{words[i]} {words[i + 1]}"
            if bigram in self.bigram_to_category:
                entry = self.bigram_to_category[bigram]
                self._validate_keyword_entry(entry, f" для биграммы '{bigram}'")
                self._update_usage_stats(entry)
                results.append((entry.category, entry.confidence))
        
        # Проверяем отдельные слова
        for word in words:
            if word in self.unigram_to_categories:
                for entry in self.unigram_to_categories[word]:
                    self._validate_keyword_entry(entry, f" для униграммы '{word}'")
                    # Избегаем дубликатов
                    if (entry.category, entry.confidence) not in results:
                        self._update_usage_stats(entry)
                        results.append((entry.category, entry.confidence))
        
        # Если не нашли результатов по обычному тексту, пробуем использовать лемматизацию
        if not results:
            lemma_results = self._find_by_lemma(text)
            if lemma_results:
                category, confidence = lemma_results
                # Проверяем, не является ли уже этот результат дубликатом
                if (category, confidence) not in results:
                    fake_entry = KeywordEntry(
                        keyword=self.lemmatize_text(text),
                        category=category,
                        confidence=confidence
                    )
                    self._update_usage_stats(fake_entry)
                    results.append((category, confidence))
        
        # Сортируем по уверенности
        results.sort(key=lambda x: x[1], reverse=True)
        
        return results
    
    def add_keyword(self, keyword: str, category: str, confidence: float = 0.5, save_to_sheet: bool = True):
        """
        Добавление нового ключевого слова
        
        Args:
            keyword: Ключевое слово
            category: Категория
            confidence: Уверенность (0.0-1.0)
            save_to_sheet: Сохранять ли ключевое слово в Google Sheets (по умолчанию True)
        """
        # Нормализуем ключевое слово: приводим к нижнему регистру и убираем лишние пробелы
        keyword_normalized = self.normalize_text(keyword)
        
        # Лемматизируем ключевое слово
        keyword_lemmatized = self.lemmatizer.lemmatize_text(keyword)
        
        # Добавляем нормализованное слово
        if keyword_normalized in self.keyword_to_category:
            # Обновляем существующий элемент
            entry = self.keyword_to_category[keyword_normalized]
            self._validate_keyword_entry(entry, f" при добавлении нового ключевого слова для ключа '{keyword_normalized}'")
            entry.category = category
            entry.confidence = confidence
        else:
            # Создаем новый элемент
            entry = KeywordEntry(
                keyword=keyword_normalized,
                category=category,
                confidence=confidence
            )
            self.keyword_to_category[keyword_normalized] = entry
        
        # Добавляем в категорию
        self.category_keywords[category].append(entry)
        
        # Обновляем индекс униграмм
        words = keyword_normalized.split()
        for word in words:
            if word not in self.unigram_to_categories:
                self.unigram_to_categories[word] = []
            self._validate_keyword_entry(entry, f" при добавлении в униграммы при ручном добавлении для слова '{word}'")
            self.unigram_to_categories[word].append(entry)
        
        # Обновляем биграммы
        if len(words) > 1:
            for i in range(len(words) - 1):
                bigram = f"{words[i]} {words[i + 1]}"
                self._validate_keyword_entry(entry, f" при добавлении в биграммы при ручном добавлении '{bigram}'")
                self.bigram_to_category[bigram] = entry
        
        # Если лемматизированное слово отличается от нормализованного, добавляем его тоже
        if keyword_lemmatized != keyword_normalized:
            if keyword_lemmatized not in self.keyword_to_category:
                # Создаем новый элемент для леммы
                lemma_entry = KeywordEntry(
                    keyword=keyword_lemmatized,
                    category=category,
                    confidence=confidence
                )
                self._validate_keyword_entry(lemma_entry, f" при добавлении леммы для ключа '{keyword_lemmatized}'")
                self.keyword_to_category[keyword_lemmatized] = lemma_entry
                
                # Добавляем лемму в категорию
                self.category_keywords[category].append(lemma_entry)
                
                # Обновляем индекс униграмм для леммы
                lemma_words = keyword_lemmatized.split()
                for word in lemma_words:
                    if word not in self.unigram_to_categories:
                        self.unigram_to_categories[word] = []
                    # Добавляем проверку типа перед добавлением в список
                    self._validate_keyword_entry(lemma_entry, f" при добавлении в униграммы для слова '{word}'")
                    self.unigram_to_categories[word].append(lemma_entry)
                
                # Обновляем биграммы для леммы
                if len(lemma_words) > 1:
                    for i in range(len(lemma_words) - 1):
                        bigram = f"{lemma_words[i]} {lemma_words[i + 1]}"
                        self._validate_keyword_entry(lemma_entry, f" при добавлении в биграммы '{bigram}'")
                        self.bigram_to_category[bigram] = lemma_entry
        
        # Сохраняем в Google Sheets только если save_to_sheet=True
        # Для асинхронного вызова используем отдельную функцию
        if save_to_sheet:
            self._async_add_keyword_to_sheet(keyword_normalized, category, confidence)
        
        self.last_update = datetime.now()

    def _async_add_keyword_to_sheet(self, keyword: str, category: str, confidence: float):
        """Асинхронное добавление ключевого слова в Google Sheets
        Метод изменен, чтобы избежать использования asyncio.get_event_loop() без проверки запущенного цикла
        """
        from sheets.client import add_keyword_to_sheet
        import asyncio
        try:
            # Выполняем асинхронный вызов для сохранения в Google Sheets
            loop = asyncio.get_running_loop()
            # Если цикл запущен, создаем задачу
            asyncio.create_task(add_keyword_to_sheet(keyword, category, confidence))
        except RuntimeError:
            # Если цикл не запущен, мы не можем выполнить асинхронный вызов из синхронного контекста
            # Вместо этого, пользователь должен вызвать асинхронный метод напрямую
            logger.warning(f"⚠️ Невозможно выполнить асинхронный вызов из синхронного контекста для добавления '{keyword}'. "
                          "Рекомендуется вызывать асинхронные методы из асинхронного контекста.")
            # В текущей реализации просто логируем предупреждение,
            # так как синхронная версия функции не реализована
            logger.warning(f"⚠️ Ключевое слово '{keyword}' не было сохранено в Google Sheets из-за отсутствия асинхронного контекста.")
    
    def normalize_text(self, text: str) -> str:
        """
        Нормализация текста: приведение к нижнему регистру, удаление лишних пробелов
        """
        return text.strip().lower()
    
    def lemmatize_word(self, word: str) -> str:
        """
        Лемматизация отдельного слова
        """
        return self.lemmatizer.lemmatize_word(word)
    
    def lemmatize_text(self, text: str) -> str:
        """
        Лемматизация всего текста
        """
        return self.lemmatizer.lemmatize_text(text)
    
    def _find_by_lemma(self, text: str) -> Optional[Tuple[str, float]]:
        """
        Поиск категории по лемматизированному тексту
        """
        # Проверяем, доступен ли лемматизатор
        if not hasattr(self, 'lemmatizer') or not self.lemmatizer.morph_analyzer:
            return None
            
        # Лемматизируем входной текст
        lemmatized_text = self.lemmatize_text(text)
        
        # Пробуем найти точное совпадение с лемматизированным текстом
        if lemmatized_text in self.keyword_to_category:
            entry = self.keyword_to_category[lemmatized_text]
            self._validate_keyword_entry(entry, f" для лемматизированного текста '{lemmatized_text}'")
            self._update_usage_stats(entry)
            return entry.category, entry.confidence
        
        # Проверяем биграммы в лемматизированном тексте
        lemmatized_words = lemmatized_text.split()
        for i in range(len(lemmatized_words) - 1):
            bigram = f"{lemmatized_words[i]} {lemmatized_words[i + 1]}"
            if bigram in self.bigram_to_category:
                entry = self.bigram_to_category[bigram]
                self._validate_keyword_entry(entry, f" для биграммы '{bigram}'")
                self._update_usage_stats(entry)
                return entry.category, entry.confidence
        
        # Проверяем отдельные лемматизированные слова
        max_confidence = 0.0
        best_category = None
        
        for word in lemmatized_words:
            if word in self.unigram_to_categories:
                for entry in self.unigram_to_categories[word]:
                    self._validate_keyword_entry(entry, f" для униграммы '{word}'")
                    if entry.confidence > max_confidence:
                        max_confidence = entry.confidence
                        best_category = entry.category
        
        if best_category:
            # Создаем фиктивную запись для обновления статистики
            fake_entry = KeywordEntry(
                keyword=lemmatized_text,
                category=best_category,
                confidence=max_confidence
            )
            self._update_usage_stats(fake_entry)
            return best_category, max_confidence
        
        return None
    
    def get_category_keywords(self, category: str) -> List[KeywordEntry]:
        """
        Получение всех ключевых слов для категории
        
        Args:
            category: Название категории
            
        Returns:
            Список ключевых слов в категории
        """
        return self.category_keywords.get(category, [])
    
    def get_all_categories(self) -> List[str]:
        """Получение всех категорий"""
        return list(self.category_keywords.keys())
    
    def get_usage_stats(self) -> Counter:
        """Получение статистики использования"""
        return self.usage_stats
    
    def get_keyword_entry(self, keyword: str) -> Optional[KeywordEntry]:
        """Получение полной информации о ключевом слове"""
        return self.keyword_to_category.get(keyword.strip().lower())
    
    def search_similar_keywords(self, keyword: str, threshold: float = 0.8) -> List[KeywordEntry]:
        """
        Поиск похожих ключевых слов по схожести
        
        Args:
            keyword: Ключевое слово для поиска
            threshold: Порог схожести (0.0-1.0)
            
        Returns:
            Список похожих ключевых слов
        """
        keyword_lower = keyword.strip().lower()
        similar = []
        
        for stored_keyword in self.keyword_to_category:
            similarity = self._calculate_similarity(keyword_lower, stored_keyword)
            if similarity >= threshold:
                similar.append(self.keyword_to_category[stored_keyword])
        
        return similar
    
    def _calculate_similarity(self, s1: str, s2: str) -> float:
        """
        Вычисление схожести между двумя строками (упрощенная версия)
        
        Args:
            s1: Первая строка
            s2: Вторая строка
            
        Returns:
            Коэффициент схожести (0.0-1.0)
        """
        # Простой алгоритм схожести - отношение длины пересечения к объединению
        set1 = set(s1.split())
        set2 = set(s2.split())
        
        if not set1 and not set2:
            return 1.0
        if not set1 or not set2:
            return 0.0
        
        intersection = set1.intersection(set2)
        union = set1.union(set2)
        
        return len(intersection) / len(union)