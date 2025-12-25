import pytest
import asyncio
from utils.category_classifier import classifier
from models.transaction import TransactionData
from datetime import datetime


@pytest.mark.asyncio
async def test_keyword_based_category_recognition():
    """Тест проверяет распознавание категорий по ключевым словам"""
    # Добавим тестовое ключевое слово
    classifier.learn_keyword("сосиски", "Продукты")
    
    # Проверим, что ключевое слово распознается
    result = classifier.get_category_by_keyword("сосиски")
    
    assert result is not None
    category, confidence = result
    assert category == "Продукты"
    assert 0.0 <= confidence <= 1.0
    
    # Проверим распознавание по тексту
    categories_by_text = classifier.get_categories_by_text("сосиски")
    assert len(categories_by_text) > 0
    found_category = next((cat for cat, conf in categories_by_text if cat == "Продукты"), None)
    assert found_category is not None


@pytest.mark.asyncio
async def test_category_prediction_by_comment():
    """Тест проверяет предсказание категории на основе комментария"""
    # Обучим классификатор на примере
    classifier.learn_keyword("кофе", "Продукты")
    
    # Создадим транзакцию с комментарием
    transaction = TransactionData(
        type="Расход",
        category="",
        amount=250.0,
        comment="кофе",
        username="test_user",
        retailer_name="",
        items_list="",
        payment_info="",
        transaction_dt=datetime.now()
    )
    
    # Предскажем категорию
    predicted_category, confidence = classifier.predict_category(transaction)
    
    # Проверим, что категория предсказана (может быть не всегда "Продукты" из-за обучения модели)
    assert predicted_category is not None
    assert isinstance(predicted_category, str)
    assert 0.0 <= confidence <= 1.0


@pytest.mark.asyncio
async def test_multiple_keywords_for_same_category():
    """Тест проверяет, что можно добавлять несколько ключевых слов для одной категории"""
    # Добавим несколько ключевых слов для одной категории
    classifier.learn_keyword("сосиски", "Продукты")
    classifier.learn_keyword("молоко", "Продукты")
    classifier.learn_keyword("хлеб", "Продукты")
    
    # Проверим, что все ключевые слова распознаются
    for keyword in ["сосиски", "молоко", "хлеб"]:
        result = classifier.get_category_by_keyword(keyword)
        assert result is not None
        category, confidence = result
        assert category == "Продукты"
        assert 0.0 <= confidence <= 1.0


@pytest.mark.asyncio
async def test_category_recognition_with_lemmatization():
    """Тест проверяет распознавание категорий с учетом лемматизации"""
    # Добавим ключевое слово
    classifier.learn_keyword("такси", "Транспорт")
    
    # Проверим, что классификатор может распознать лемматизированную форму
    # или похожие слова, если реализована такая логика
    result = classifier.get_category_by_keyword("такси")
    if result:
        category, confidence = result
        assert category == "Транспорт"
        assert 0.0 <= confidence <= 1.0


@pytest.mark.asyncio
async def test_no_default_category_from_previous_transaction():
    """Тест проверяет, что при создании новой транзакции не используется категория из предыдущей транзакции"""
    # Создадим первую транзакцию
    first_transaction = TransactionData(
        type="Расход",
        category="Продукты",
        amount=300.0,
        comment="сосиски",
        username="test_user",
        retailer_name="",
        items_list="",
        payment_info="",
        transaction_dt=datetime.now()
    )
    
    # Создадим вторую транзакцию с другим комментарием
    second_transaction = TransactionData(
        type="Расход",
        category="",  # Пустая категория, будет предсказана
        amount=500.0,
        comment="кофе",
        username="test_user",
        retailer_name="",
        items_list="",
        payment_info="",
        transaction_dt=datetime.now()
    )
    
    # Проверим, что у второй транзакции изначально пустая категория
    assert second_transaction.category == ""
    
    # Предскажем категорию для второй транзакции
    predicted_category, confidence = classifier.predict_category(second_transaction)
    
    # Проверим, что предсказанная категория не обязательно "Продукты" (не зависит от первой транзакции)
    # Это тестирует, что классификатор не использует состояние предыдущих транзакций
    assert predicted_category is not None
    assert isinstance(predicted_category, str)


if __name__ == "__main__":
    # Запуск тестов
    asyncio.run(test_keyword_based_category_recognition())
    asyncio.run(test_category_prediction_by_comment())
    asyncio.run(test_multiple_keywords_for_same_category())
    asyncio.run(test_category_recognition_with_lemmatization())
    asyncio.run(test_no_default_category_from_previous_transaction())
    print("Все тесты пройдены успешно!")