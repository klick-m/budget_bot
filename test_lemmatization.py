# -*- coding: utf-8 -*-
"""
Тестирование лемматизации и классификации для улучшенной ML-системы
"""
import asyncio
from utils.category_classifier import TransactionCategoryClassifier
from models.keyword_dictionary import KeywordDictionary
from models.transaction import TransactionData
from datetime import datetime


async def test_lemmatization():
    """Тестирование лемматизации и классификации"""
    print("=== Тестирование лемматизации и классификации ===")
    
    # Создаем экземпляр классификатора
    # Для тестирования создадим полноценный KeywordDictionary
    keyword_dict = KeywordDictionary("test_id", "test_sheet")
    classifier = TransactionCategoryClassifier(keyword_dict=keyword_dict)
    
    # Проверяем, доступна ли лемматизация
    if classifier.morph_analyzer is None:
        print("⚠️ pymorphy3 не установлен, лемматизация недоступна")
        return False
    
    # Тестируем лемматизацию отдельных слов
    print("\n1. Тестирование лемматизации отдельных слов:")
    test_words = ["такси", "таксисты", "таксист", "таксистов", "поездка", "поездки", "автобус", "автобусы"]
    
    for word in test_words:
        lemma = classifier.lemmatize_word(word)
        print(f"   '{word}' -> '{lemma}'")
    
    # Тестируем лемматизацию фраз
    print("\n2. Тестирование лемматизации фраз:")
    test_phrases = ["на такси", "на автобусе", "поездка на такси", "таксист привез", "еду на такси"]
    
    for phrase in test_phrases:
        lemmatized = classifier.lemmatize_text(phrase)
        print(f"   '{phrase}' -> '{lemmatized}'")
    
    # Добавим тестовые ключевые слова в словарь
    print("\n3. Добавление тестовых ключевых слов в словарь:")
    classifier.keyword_dict.add_keyword("такси", "Транспорт", 0.9)
    classifier.keyword_dict.add_keyword("поездка", "Транспорт", 0.8)
    classifier.keyword_dict.add_keyword("автобус", "Транспорт", 0.9)
    classifier.keyword_dict.add_keyword("кофе", "Продукты", 0.9)
    
    # Тестируем классификацию
    print("\n4. Тестирование классификации с лемматизацией:")
    test_inputs = [
        "на такси",
        "на таксисте",  # несуществительное слово, но с лемматизацией может сработать
        "такси", 
        "таксисты",
        "поездка на такси",
        "еду на такси",
        "кофе",
        "купил кофе"
    ]
    
    for text in test_inputs:
        # Проверяем обычный поиск
        keyword_result = classifier.get_category_by_keyword(text)
        if keyword_result:
            print(f"   '{text}' -> {keyword_result}")
        else:
            # Создаем фейковую транзакцию для ML-классификации
            fake_transaction = TransactionData(
                type="Расход",
                category="",
                amount=0.0,
                comment=text,
                username="",
                retailer_name="",
                items_list="",
                payment_info="",
                transaction_dt=datetime.now()
            )
            
            predicted_category, confidence = classifier.predict_category(fake_transaction)
            print(f"   '{text}' -> {predicted_category} (уверенность: {confidence:.2f})")
    
    print("\n5. Тестирование обратной связи (обучение):")
    # Обучаем систему новому соответствию
    classifier.learn_keyword("поездка на такси", "Транспорт")
    classifier.learn_keyword("еду на такси", "Транспорт")
    
    # Проверяем, как теперь классифицируется "на такси"
    result = classifier.get_category_by_keyword("на такси")
    if result:
        print(f"   После обучения 'на такси' -> {result}")
    else:
        fake_transaction = TransactionData(
            type="Расход",
            category="",
            amount=0.0,
            comment="на такси",
            username="",
            retailer_name="",
            items_list="",
            payment_info="",
            transaction_dt=datetime.now()
        )
        predicted_category, confidence = classifier.predict_category(fake_transaction)
        print(f"   После обучения 'на такси' -> {predicted_category} (уверенность: {confidence:.2f})")
    
    print("\n✅ Тестирование лемматизации завершено")
    return True


def test_basic_lemmatization():
    """Базовое тестирование лемматизации без асинхронности"""
    print("=== Базовое тестирование лемматизации ===")
    
    try:
        from pymorphy3 import MorphAnalyzer
    except ImportError:
        print("⚠️ pymorphy3 не установлен")
        return False
    
    try:
        morph = MorphAnalyzer()
    except Exception as e:
        print(f"⚠️ Не удалось инициализировать MorphAnalyzer: {e}")
        return False
    
    # Тестируем лемматизацию
    test_words = ["такси", "на", "такси", "таксисты", "поездка", "поездки"]
    print("\nЛемматизация тестовых слов:")
    for word in test_words:
        parsed = morph.parse(word)[0]
        normal_form = parsed.normal_form
        print(f"   '{word}' -> '{normal_form}' (тег: {parsed.tag})")
    
    # Тестируем лемматизацию фраз
    test_phrase = "на такси"
    words = test_phrase.split()
    lemmatized_words = [morph.parse(word)[0].normal_form for word in words]
    lemmatized_phrase = " ".join(lemmatized_words)
    print(f"\n   '{test_phrase}' -> '{lemmatized_phrase}'")
    
    print("\n✅ Базовое тестирование лемматизации завершено")
    return True


if __name__ == "__main__":
    print("Запуск тестов лемматизации...")
    
    # Сначала базовое тестирование
    basic_success = test_basic_lemmatization()
    
    if basic_success:
        # Потом асинхронное тестирование
        try:
            asyncio.run(test_lemmatization())
        except Exception as e:
            print(f"❌ Ошибка при выполнении асинхронного теста: {e}")
    else:
        print("❌ Базовое тестирование не удалось, пропускаем асинхронное тестирование")