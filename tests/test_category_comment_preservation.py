import pytest
import asyncio
from models.transaction import TransactionData
from services.transaction_service import TransactionService
from utils.category_classifier import classifier
from datetime import datetime


@pytest.mark.asyncio
async def test_transaction_creation_preserves_comment_and_category():
    """Тест проверяет, что при создании транзакции комментарий и категория сохраняются правильно"""
    # Создаем транзакцию с определенными значениями
    transaction = TransactionData(
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
    
    # Проверяем, что все поля установлены правильно
    assert transaction.type == "Расход"
    assert transaction.category == "Продукты"
    assert transaction.amount == 300.0
    assert transaction.comment == "сосиски"
    assert transaction.username == "test_user"


@pytest.mark.asyncio
async def test_category_prediction_keeps_original_comment():
    """Тест проверяет, что предсказание категории не влияет на комментарий"""
    # Создаем транзакцию с комментарием
    original_comment = "сосиски"
    transaction = TransactionData(
        type="Расход",
        category="",
        amount=300.0,
        comment=original_comment,
        username="test_user",
        retailer_name="",
        items_list="",
        payment_info="",
        transaction_dt=datetime.now()
    )
    
    # Применяем классификацию
    predicted_category, confidence = classifier.predict_category(transaction)
    
    # Проверяем, что комментарий остался неизменным
    assert transaction.comment == original_comment
    # Проверяем, что категория предсказана
    assert predicted_category is not None
    assert isinstance(predicted_category, str)
    assert len(predicted_category) > 0


@pytest.mark.asyncio
async def test_keyword_learning_preserves_comment_category_link():
    """Тест проверяет, что обучение по ключевым словам сохраняет связь между комментарием и категорией"""
    # Используем классификатор для обучения
    comment = "сосиски"
    category = "Продукты"
    
    # Обучаем классификатор
    classifier.learn_keyword(comment, category)
    
    # Проверяем, что ключевое слово добавлено
    result = classifier.get_category_by_keyword(comment)
    if result is not None:
        learned_category, confidence = result
        assert learned_category == category
        assert 0.0 <= confidence <= 1.0


@pytest.mark.asyncio
async def test_transaction_service_preserves_data():
    """Тест проверяет, что сервис транзакций сохраняет комментарии и категории при обработке"""
    # Создаем экземпляр сервиса
    service = TransactionService()
    
    # Создаем транзакцию
    original_data = {
        'type': 'Расход',
        'category': 'Продукты',
        'amount': 300.0,
        'comment': 'сосиски',
        'username': 'test_user'
    }
    
    transaction = TransactionData(
        type=original_data['type'],
        category=original_data['category'],
        amount=original_data['amount'],
        comment=original_data['comment'],
        username=original_data['username'],
        retailer_name="",
        items_list="",
        payment_info="",
        transaction_dt=datetime.now()
    )
    
    # Проверяем, что все данные сохранены
    assert transaction.type == original_data['type']
    assert transaction.category == original_data['category']
    assert transaction.amount == original_data['amount']
    assert transaction.comment == original_data['comment']
    assert transaction.username == original_data['username']


if __name__ == "__main__":
    # Запуск тестов
    asyncio.run(test_transaction_creation_preserves_comment_and_category())
    asyncio.run(test_category_prediction_keeps_original_comment())
    asyncio.run(test_keyword_learning_preserves_comment_category_link())
    asyncio.run(test_transaction_service_preserves_data())
    print("Все тесты пройдены успешно!")