import pytest
import asyncio
from services.input_parser import InputParser
from utils.category_classifier import classifier
from models.transaction import TransactionData
from datetime import datetime


@pytest.mark.asyncio
async def test_parse_sausages_300():
    """Тест парсинга ввода 'сосиски 300'"""
    parser = InputParser()
    
    # Тестируем ввод "сосиски 300"
    result = parser.parse_user_input("сосиски 300")
    
    assert result is not None
    assert result['amount'] == 300.0
    assert result['comment'] == "сосиски"
    
    # Проверяем, что комментарий не пустой
    assert result['comment'].strip() != ""


@pytest.mark.asyncio
async def test_category_prediction_for_sausages():
    """Тест предсказания категории для 'сосиски'"""
    # Создаем фейковую транзакцию с комментарием "сосиски"
    transaction = TransactionData(
        type="Расход",
        category="",
        amount=300.0,
        comment="сосиски",
        username="test_user",
        retailer_name="",
        items_list="",
        payment_info="",
        transaction_dt=datetime.now()
    )
    
    # Получаем предсказанную категорию и уверенность
    predicted_category, confidence = classifier.predict_category(transaction)
    
    # Проверяем, что категория предсказана
    assert predicted_category is not None
    assert isinstance(predicted_category, str)
    assert len(predicted_category) > 0
    
    # Проверяем, что уверенность в допустимом диапазоне
    assert 0.0 <= confidence <= 1.0


@pytest.mark.asyncio
async def test_keyword_based_category_prediction():
    """Тест предсказания категории по ключевым словам для 'сосиски'"""
    # Тестируем получение категории по ключевому слову
    result = classifier.get_category_by_keyword("сосиски")
    
    # Результат может быть None, если ключевое слово не найдено в словаре
    # Это нормальное поведение для новых/неизвестных слов
    if result is not None:
        category, confidence = result
        assert isinstance(category, str)
        assert 0.0 <= confidence <= 1.0


@pytest.mark.asyncio
async def test_smart_input_parsing():
    """Тест умного парсинга для ввода 'сосиски 300'"""
    parser = InputParser()
    
    # Тестируем оба возможных формата
    result1 = parser.parse_user_input("сосиски 300")
    result2 = parser.parse_user_input("300 сосиски")
    
    # Оба должны успешно распарситься
    assert result1 is not None
    assert result2 is not None
    
    # В обоих случаях сумма должна быть 300
    assert result1['amount'] == 300.0
    assert result2['amount'] == 300.0
    
    # Комментарии должны содержать "сосиски" (в разных местах)
    assert "сосиски" in result1['comment'].lower() or result1['comment'].lower() == "сосиски"
    assert "сосиски" in result2['comment'].lower() or result2['comment'].lower() == "сосиски"


@pytest.mark.asyncio
async def test_edge_cases_parsing():
    """Тест граничных случаев парсинга"""
    parser = InputParser()
    
    # Тест с дробной суммой
    result = parser.parse_user_input("сосиски 30.50")
    assert result is not None
    assert result['amount'] == 30.50
    assert "сосиски" in result['comment'].lower()
    
    # Тест с запятой в сумме
    result = parser.parse_user_input("сосиски 300,50")
    assert result is not None
    assert result['amount'] == 300.50
    assert "сосиски" in result['comment'].lower()
    
    # Тест с несколькими словами в комментарии
    result = parser.parse_user_input("сосиски с хреном 300")
    assert result is not None
    assert result['amount'] == 300.0
    assert "сосиски" in result['comment'].lower()
    assert "хреном" in result['comment'].lower()


if __name__ == "__main__":
    # Запуск тестов
    asyncio.run(test_parse_sausages_300())
    asyncio.run(test_category_prediction_for_sausages())
    asyncio.run(test_keyword_based_category_prediction())
    asyncio.run(test_smart_input_parsing())
    asyncio.run(test_edge_cases_parsing())
    print("Все тесты пройдены успешно!")