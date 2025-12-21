# -*- coding: utf-8 -*-
"""
Специальный тест для проверки классификации различных форм слова "такси"
"""
from utils.category_classifier import TransactionCategoryClassifier
from models.keyword_dictionary import KeywordDictionary
from models.transaction import TransactionData
from datetime import datetime
import asyncio


async def test_taxi_classification():
    """Тестирование классификации различных форм слова 'такси'"""
    print("=== Тестирование классификации форм слова 'такси' ===")
    
    # Создаем полноценный классификатор с KeywordDictionary
    keyword_dict = KeywordDictionary("test_id", "test_sheet")
    classifier = TransactionCategoryClassifier(keyword_dict=keyword_dict)
    
    # Добавляем ключевое слово "такси" в категорию "Транспорт"
    classifier.add_keyword("такси", "Транспорт", 0.9)
    
    # Тестируемые формы
    test_forms = [
        "такси",           # начальная форма
        "на такси",       # предлог + существительное
        "на таксике",     # форма с притяжательным местоимением? Нет, это ошибка - "на такси" в предложном падеже
        "таксист",        # родственное слово
        "таксисты",       # родственное слово, множественное число
        "таксиист",       # опечатка
        "таксует",        # глагол (ошибка в слове)
        "заказал такси",  # фраза
        "еду на такси",   # фраза
        "поехал на такси", # фраза
    ]
    
    print(f"\nКлассификация различных форм:")
    all_correct = True
    
    for form in test_forms:
        # Попробуем получить категорию по ключевому слову
        keyword_result = classifier.get_category_by_keyword(form)
        
        if keyword_result:
            category, confidence = keyword_result
            print(f"   '{form}' -> {category} (уверенность: {confidence:.2f})")
            # Проверяем, что категория - транспорт или что-то связанное
            if "Транспорт" not in category and "такси" not in category.lower():
                if form in ["таксист", "таксисты", "еду на такси", "поехал на такси", "заказал такси"]:
                    # Для родственных форм и фраз, которые должны быть распознаны, отмечаем как потенциальную проблему
                    print(f"     ⚠️  '{form}' не распознан как транспорт, хотя мог бы быть")
        else:
            # Если не найдено по ключевому слову, используем ML-классификацию
            fake_transaction = TransactionData(
                type="Расход",
                category="",
                amount=0.0,
                comment=form,
                username="",
                retailer_name="",
                items_list="",
                payment_info="",
                transaction_dt=datetime.now()
            )
            
            predicted_category, confidence = classifier.predict_category(fake_transaction)
            print(f"   '{form}' -> {predicted_category} (уверенность: {confidence:.2f})")
            
            # Проверяем, что похожие на транспорт фразы распознаются правильно
            if form in ["на такси", "еду на такси", "поехал на такси", "заказал такси"] and "Транспорт" not in predicted_category:
                all_correct = False
                print(f"     ❌ '{form}' не распознан как транспорт, ожидалась категория 'Транспорт'")
    
    # Проверим также лемматизацию этих форм
    print(f"\nЛемматизация форм:")
    for form in test_forms:
        lemmatized = classifier.lemmatize_text(form)
        print(f"   '{form}' -> '{lemmatized}'")
    
    # Обучим систему нескольким формам
    print(f"\nОбучение системе новых форм:")
    classifier.learn_keyword("еду на такси", "Транспорт")
    classifier.learn_keyword("поехал на такси", "Транспорт")
    classifier.learn_keyword("заказал такси", "Транспорт")
    
    # Проверим, как теперь классифицируется форма, которую мы не обучали напрямую
    test_phrase = "на такси"
    result = classifier.get_category_by_keyword(test_phrase)
    if result:
        category, confidence = result
        print(f"   После обучения '{test_phrase}' -> {category} (уверенность: {confidence:.2f})")
    
    print(f"\n✅ Тестирование форм слова 'такси' завершено")
    return all_correct


def main():
    print("Запуск специального теста для форм слова 'такси'...")
    try:
        result = asyncio.run(test_taxi_classification())
        if result:
            print("\n✅ Все тесты пройдены успешно")
        else:
            print("\n⚠️  Требуется ручная проверка некоторых результатов")
    except Exception as e:
        print(f"❌ Ошибка при выполнении теста: {e}")


if __name__ == "__main__":
    main()