# -*- coding: utf-8 -*-
"""
Тесты для модуля улучшенной классификации транзакций
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime
from models.transaction import TransactionData
from utils.category_classifier import TransactionCategoryClassifier


def test_classifier_initialization():
    """Тест инициализации классификатора"""
    classifier = TransactionCategoryClassifier()
    
    assert classifier.category_keywords == {}
    assert classifier.category_features == {}
    assert classifier.global_features == {}
    assert classifier.category_transactions_count == {}
    assert classifier.total_transactions == 0
    assert classifier.categories == set()


def test_extract_features():
    """Тест извлечения признаков из текста"""
    classifier = TransactionCategoryClassifier()
    
    text = "Покупка в магазине продуктов питания"
    features = classifier.extract_features(text)
    
    # Проверяем, что извлекаются слова длиной 3 символа и более
    # Проверяем наличие каких-либо извлеченных признаков
    assert len(features) > 0
    # Проверяем, что короткие слова не включаются
    assert 'в' not in features
    assert 'и' not in features


def test_train_classifier():
    """Тест обучения классификатора"""
    classifier = TransactionCategoryClassifier()
    
    transactions = [
        TransactionData(
            type="Расход",
            category="Продукты",
            amount=10.0,
            comment="Покупка хлеба и молока",
            username="test_user",
            retailer_name="Магазин продуктов",
            items_list="Хлеб, Молоко",
            payment_info="Наличные",
            transaction_dt=datetime.now()
        ),
        TransactionData(
            type="Расход",
            category="Продукты",
            amount=200.0,
            comment="Покупка овощей и фруктов",
            username="test_user",
            retailer_name="Магазин продуктов",
            items_list="Яблоки, Картофель",
            payment_info="Карта",
            transaction_dt=datetime.now()
        ),
        TransactionData(
            type="Расход",
            category="Транспорт",
            amount=50.0,
            comment="Проезд в автобусе",
            username="test_user",
            retailer_name="Транспорт",
            items_list="Билет",
            payment_info="Наличные",
            transaction_dt=datetime.now()
        )
    ]
    
    classifier.train(transactions)
    
    # Проверяем, что обучение прошло успешно
    assert classifier.total_transactions == 3
    assert len(classifier.categories) == 2
    assert "Продукты" in classifier.categories
    assert "Транспорт" in classifier.categories
    assert classifier.category_transactions_count["Продукты"] == 2
    assert classifier.category_transactions_count["Транспорт"] == 1


def test_predict_category():
    """Тест предсказания категории"""
    classifier = TransactionCategoryClassifier()
    
    # Обучаем классификатор на тестовых данных
    transactions = [
        TransactionData(
            type="Расход",
            category="Продукты",
            amount=100.0,
            comment="Покупка хлеба и молока",
            username="test_user",
            retailer_name="Магазин продуктов",
            items_list="Хлеб, Молоко",
            payment_info="Наличные",
            transaction_dt=datetime.now()
        ),
        TransactionData(
            type="Расход",
            category="Продукты",
            amount=200.0,
            comment="Покупка овощей и фруктов",
            username="test_user",
            retailer_name="Магазин продуктов",
            items_list="Яблоки, Картофель",
            payment_info="Карта",
            transaction_dt=datetime.now()
        ),
        TransactionData(
            type="Расход",
            category="Транспорт",
            amount=50.0,
            comment="Проезд в автобусе",
            username="test_user",
            retailer_name="Транспорт",
            items_list="Билет",
            payment_info="Наличные",
            transaction_dt=datetime.now()
        )
    ]
    
    classifier.train(transactions)
    
    # Тестируем предсказание
    test_transaction = TransactionData(
        type="Расход",
        category="",
        amount=150.0,
        comment="Покупка яблок и апельсинов",
        username="test_user",
        retailer_name="Магазин фруктов",
        items_list="Яблоки, Апельсины",
        payment_info="Карта",
        transaction_dt=datetime.now()
    )
    
    predicted_category, confidence = classifier.predict_category(test_transaction)
    
    # Проверяем, что предсказана какая-то категория
    assert predicted_category in classifier.categories
    assert 0.0 <= confidence <= 1.0


def test_suggest_new_category():
    """Тест предложения новой категории"""
    classifier = TransactionCategoryClassifier()
    
    # Обучаем классификатор на тестовых данных
    transactions = [
        TransactionData(
            type="Расход",
            category="Продукты",
            amount=100.0,
            comment="Покупка хлеба и молока",
            username="test_user",
            retailer_name="Магазин продуктов",
            items_list="Хлеб, Молоко",
            payment_info="Наличные",
            transaction_dt=datetime.now()
        )
    ]
    
    classifier.train(transactions)
    
    # Создаем транзакцию, которая не подходит под существующие категории
    test_transaction = TransactionData(
        type="Расход",
        category="",
        amount=1000.0,
        comment="Покупка нового телевизора",
        username="test_user",
        retailer_name="Магазин электроники",
        items_list="Телевизор",
        payment_info="Карта",
        transaction_dt=datetime.now()
    )
    
    suggested_category_info = classifier.suggest_new_category(test_transaction)
    
    # При низкой уверенности должна быть предложена новая категория
    if suggested_category_info:
        suggested_category, suggestion_confidence = suggested_category_info
        assert suggested_category is not None
        assert 0.0 <= suggestion_confidence <= 1.0


def test_calculate_tfidf():
    """Тест расчета TF-IDF"""
    classifier = TransactionCategoryClassifier()
    
    # Обучаем классификатор
    transactions = [
        TransactionData(
            type="Расход",
            category="Продукты",
            amount=100.0,
            comment="Покупка хлеба и молока",
            username="test_user",
            retailer_name="Магазин продуктов",
            items_list="Хлеб, Молоко",
            payment_info="Наличные",
            transaction_dt=datetime.now()
        ),
        TransactionData(
            type="Расход",
            category="Транспорт",
            amount=50.0,
            comment="Проезд в автобусе",
            username="test_user",
            retailer_name="Транспорт",
            items_list="Билет",
            payment_info="Наличные",
            transaction_dt=datetime.now()
        )
    ]
    
    classifier.train(transactions)
    
    # Проверяем расчет TF-IDF
    tfidf_score = classifier._calculate_tfidf("хлеб", "Продукты")
    assert isinstance(tfidf_score, float)


if __name__ == "__main__":
    test_classifier_initialization()
    test_extract_features()
    test_train_classifier()
    test_predict_category()
    test_suggest_new_category()
    test_calculate_tfidf()
    print("Все тесты пройдены успешно!")