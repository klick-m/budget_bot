"""
Модуль для централизованной лемматизации текста.
"""
from typing import List
import re
try:
    from pymorphy3 import MorphAnalyzer
except ImportError:
    MorphAnalyzer = None

from config import logger


class Lemmatizer:
    """
    Класс для лемматизации текста, использующий pymorphy3.
    Предоставляет унифицированный интерфейс для лемматизации слов и текста.
    """
    
    # Глобальный экземпляр MorphAnalyzer для избежания дублирования инициализаций
    _global_morph_analyzer = None
    
    def __init__(self):
        """Инициализация лемматизатора"""
        global _global_morph_analyzer
        self.morph_analyzer = _global_morph_analyzer
        if self.morph_analyzer is None:
            self._initialize_morph_analyzer()
    
    def _initialize_morph_analyzer(self):
        """Метод для инициализации morph_analyzer"""
        global _global_morph_analyzer
        try:
            if MorphAnalyzer:
                _global_morph_analyzer = MorphAnalyzer()
                self.morph_analyzer = _global_morph_analyzer
                logger.info("✅ pymorphy3 MorphAnalyzer инициализирован")
            else:
                logger.warning("⚠️ pymorphy3 не установлен, лемматизация будет недоступна")
        except Exception as e:
            logger.warning(f"⚠️ Не удалось инициализировать pymorphy3 MorphAnalyzer: {e}")
    
    @classmethod
    def get_global_analyzer(cls):
        """Получить глобальный экземпляр MorphAnalyzer"""
        global _global_morph_analyzer
        if globals().get('_global_morph_analyzer') is None and MorphAnalyzer:
            try:
                _global_morph_analyzer = MorphAnalyzer()
                logger.info("✅ pymorphy3 MorphAnalyzer инициализирован глобально")
            except Exception as e:
                logger.warning(f"⚠️ Не удалось инициализировать pymorphy3 MorphAnalyzer: {e}")
        return _global_morph_analyzer
    
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
    
    def lemmatize_words_list(self, words: List[str]) -> List[str]:
        """
        Лемматизация списка слов
        """
        return [self.lemmatize_word(word) for word in words]