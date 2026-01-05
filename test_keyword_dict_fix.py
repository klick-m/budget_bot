#!/usr/bin/env python3
"""
Тестирование исправления инициализации KeywordDictionary
"""
import asyncio
import sys
import os

# Добавляем путь к проекту
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.category_classifier import classifier
from models.keyword_dictionary import KeywordDictionary
from config import KEYWORDS_SPREADSHEET_ID, KEYWORDS_SHEET_NAME


async def test_keyword_dict_initialization():
    """Тестирование инициализации KeywordDictionary"""
    print("Тестируем инициализацию KeywordDictionary...")
    
    # Создаем экземпляр KeywordDictionary напрямую
    keyword_dict = KeywordDictionary(KEYWORDS_SPREADSHEET_ID, KEYWORDS_SHEET_NAME)
    
    # Проверяем, что атрибут lemmatizer существует
    if hasattr(keyword_dict, 'lemmatizer'):
        print("✅ Атрибут lemmatizer существует в KeywordDictionary")
    else:
        print("❌ Атрибут lemmatizer отсутствует в KeywordDictionary")
        return False
    
    # Проверяем, что lemmatizer является экземпляром Lemmatizer
    from utils.lemmatizer import Lemmatizer
    if isinstance(keyword_dict.lemmatizer, Lemmatizer):
        print("✅ Атрибут lemmatizer является экземпляром Lemmatizer")
    else:
        print("❌ Атрибут lemmatizer не является экземпляром Lemmatizer")
        return False
    
    # Проверяем, что можно вызвать методы лемматизации
    try:
        result = keyword_dict.lemmatize_text("тестовый текст")
        print(f"✅ Метод lemmatize_text работает, результат: {result}")
    except Exception as e:
        print(f"❌ Ошибка при вызове lemmatize_text: {e}")
        return False
    
    try:
        result = keyword_dict.lemmatize_word("слово")
        print(f"✅ Метод lemmatize_word работает, результат: {result}")
    except Exception as e:
        print(f"❌ Ошибка при вызове lemmatize_word: {e}")
        return False
    
    # Тестируем classifier
    print("\nТестируем инициализацию classifier...")
    if hasattr(classifier, 'keyword_dict'):
        print("✅ Атрибут keyword_dict существует в classifier")
    else:
        print("❌ Атрибут keyword_dict отсутствует в classifier")
        return False
    
    # Проверяем, что можно вызвать асинхронную инициализацию
    try:
        await classifier.load()
        print("✅ Асинхронная инициализация classifier прошла успешно")
    except Exception as e:
        print(f"❌ Ошибка при асинхронной инициализации classifier: {e}")
        return False
    
    # Проверяем, что у classifier.keyword_dict есть lemmatizer
    if hasattr(classifier.keyword_dict, 'lemmatizer'):
        print("✅ Атрибут lemmatizer существует в classifier.keyword_dict")
    else:
        print("❌ Атрибут lemmatizer отсутствует в classifier.keyword_dict")
        return False
    
    # Проверяем, что можно вызвать методы лемматизации через classifier
    try:
        result = classifier.lemmatize_text("тестовый текст")
        print(f"✅ Метод lemmatize_text работает через classifier, результат: {result}")
    except Exception as e:
        print(f"❌ Ошибка при вызове lemmatize_text через classifier: {e}")
        return False
    
    print("\n✅ Все тесты пройдены успешно!")
    return True


if __name__ == "__main__":
    success = asyncio.run(test_keyword_dict_initialization())
    if success:
        print("\n🎉 Тестирование завершено успешно. Проблема с инициализацией lemmatizer исправлена.")
        sys.exit(0)
    else:
        print("\n❌ Тестирование не пройдено. Проблема сохраняется.")
        sys.exit(1)