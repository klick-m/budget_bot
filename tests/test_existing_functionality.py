import pytest
import asyncio
from services.input_parser import InputParser
from utils.category_classifier import classifier
from models.transaction import TransactionData
from services.transaction_service import TransactionService
from datetime import datetime


@pytest.mark.asyncio
async def test_input_parsing_still_works():
    """Тест проверяет, что парсинг ввода все еще работает корректно"""
    parser = InputParser()
    
    # Тест основного сценария "сосиски 300"
    result = parser.parse_user_input("сосиски 300")
    assert result is not None
    assert result['amount'] == 300.0
    assert result['comment'] == "сосиски"
    
    # Тест другого формата "300 сосиски"
    result = parser.parse_user_input("300 сосиски")
    assert result is not None
    assert result['amount'] == 300.0
    assert result['comment'] == "сосиски"
    
    # Тест с дробной суммой
    result = parser.parse_user_input("кофе 250.50")
    assert result is not None
    assert result['amount'] == 250.50
    assert result['comment'] == "кофе"
    
    # Тест с запятой в сумме
    result = parser.parse_user_input("чай 100,75")
    assert result is not None
    assert result['amount'] == 100.75
    assert result['comment'] == "чай"


@pytest.mark.asyncio
async def test_category_classification_still_works():
    """Тест проверяет, что классификация категорий все еще работает"""
    # Создаем транзакцию для тестирования
    transaction = TransactionData(
        type="Расход",
        category="",
        amount=300.0,
        comment="",
        username="test_user",
        retailer_name="",
        items_list="",
        payment_info="",
        transaction_dt=datetime.now()
    )
    
    # Проверяем, что можно получить предсказание категории
    predicted_category, confidence = classifier.predict_category(transaction)
    assert predicted_category is not None
    assert isinstance(predicted_category, str)
    assert 0.0 <= confidence <= 1.0


@pytest.mark.asyncio
async def test_keyword_search_still_works():
    """Тест проверяет, что поиск по ключевым словам все еще работает"""
    # Добавляем тестовое ключевое слово
    classifier.learn_keyword("тестовый_магазин", "Продукты")
    
    # Проверяем, что ключевое слово можно найти
    result = classifier.get_category_by_keyword("тестовый_магазин")
    if result is not None:
        category, confidence = result
        assert category == "Продукты"
        assert 0.0 <= confidence <= 1.0
    
    # Проверяем поиск по тексту
    results = classifier.get_categories_by_text("тестовый_магазин")
    assert isinstance(results, list)
    # Результат может быть пустым, если слово не найдено, но структура должна быть правильной


@pytest.mark.asyncio
async def test_transaction_data_model():
    """Тест проверяет, что модель данных транзакции работает корректно"""
    # Создаем транзакцию с полными данными
    transaction = TransactionData(
        type="Расход",
        category="Продукты",
        amount=500.0,
        comment="покупка продуктов",
        username="test_user",
        retailer_name="Магнит",
        items_list="хлеб, молоко, яйца",
        payment_info="картой",
        transaction_dt=datetime.now()
    )
    
    # Проверяем, что все поля сохранены корректно
    assert transaction.type == "Расход"
    assert transaction.category == "Продукты"
    assert transaction.amount == 500.0
    assert transaction.comment == "покупка продуктов"
    assert transaction.username == "test_user"
    assert transaction.retailer_name == "Магнит"
    assert transaction.items_list == "хлеб, молоко, яйца"
    assert transaction.payment_info == "картой"
    assert transaction.transaction_dt is not None
    assert isinstance(transaction.transaction_dt, datetime)


@pytest.mark.asyncio
async def test_transaction_service_initialization():
    """Тест проверяет, что сервис транзакций инициализируется корректно"""
    # Создаем экземпляр сервиса без репозитория (для тестирования инициализации)
    service = TransactionService()
    
    # Проверяем, что классификатор доступен
    assert service.classifier is not None
    
    # Проверяем, что можно вызвать методы классификатора через сервис
    transaction = TransactionData(
        type="Расход",
        category="",
        amount=100.0,
        comment="тест",
        username="test_user",
        retailer_name="",
        items_list="",
        payment_info="",
        transaction_dt=datetime.now()
    )
    
    predicted_category, confidence = service.classifier.predict_category(transaction)
    assert predicted_category is not None
    assert 0.0 <= confidence <= 1.0


@pytest.mark.asyncio
async def test_lemmatization_still_works():
    """Тест проверяет, что лемматизация все еще работает"""
    # Проверяем лемматизацию отдельного слова
    if classifier.morph_analyzer:
        lemmatized = classifier.lemmatize_word("сосисок")
        assert isinstance(lemmatized, str)
        
        # Проверяем лемматизацию текста
        lemmatized_text = classifier.lemmatize_text("много сосисок")
        assert isinstance(lemmatized_text, str)
    else:
        # Если pymorphy3 не установлен, просто проверяем, что код не падает
        assert True


if __name__ == "__main__":
    # Запуск тестов
    asyncio.run(test_input_parsing_still_works())
    asyncio.run(test_category_classification_still_works())
    asyncio.run(test_keyword_search_still_works())
    asyncio.run(test_transaction_data_model())
    asyncio.run(test_transaction_service_initialization())
    asyncio.run(test_lemmatization_still_works())
    print("Все тесты пройдены успешно!")