# -*- coding: utf-8 -*-
# services/transaction_service.py
import asyncio
import traceback
from typing import Optional, Dict, Any, List
from datetime import datetime

from models.transaction import TransactionData, CheckData
from sheets.client import write_transaction, add_keywords_to_sheet, load_categories_from_sheet
from utils.exceptions import SheetWriteError, CheckApiTimeout, CheckApiRecognitionError
from utils.receipt_logic import parse_check_from_api, extract_learnable_keywords
from utils.category_classifier import classifier

from config import logger


class TransactionService:
    """
    Сервис для обработки транзакций.
    Объединяет логику валидации, DTO, и записи транзакций.
    """
    
    def __init__(self, repository=None):
        self.classifier = classifier
        self.repository = repository

    async def create_transaction_from_check(self, image_bytes: bytes) -> Optional[CheckData]:
        """
        Создает транзакцию из изображения чека.
        """
        try:
            parsed_data: CheckData = await parse_check_from_api(image_bytes)
        except (CheckApiTimeout, CheckApiRecognitionError) as e:
            raise e

        if parsed_data.amount <= 0:
            raise ValueError("Чек распознан, но сумма равна нулю или отрицательна")

        return parsed_data

    async def process_check_data(self, check_data: CheckData, user_username: str) -> TransactionData:
        """
        Обрабатывает данные чека, применяет классификацию и возвращает TransactionData.
        """
        # Создаем временную транзакцию для классификации
        temp_transaction = TransactionData(
            type=check_data.type,
            category=check_data.category,
            amount=check_data.amount,
            comment=check_data.comment,
            username=user_username,
            retailer_name=check_data.retailer_name,
            items_list=check_data.items_list,
            payment_info=check_data.payment_info,
            transaction_dt=check_data.transaction_datetime
        )

        # Применяем улучшенную классификацию
        keyword_result = self.classifier.get_category_by_keyword(f"{check_data.retailer_name} {check_data.items_list}")
        if keyword_result and keyword_result[1] > 0.7:  # Если уверенность выше 0.7
            predicted_category, confidence = keyword_result
        else:
            # Если новая система не дала результата или уверенность низкая, используем ML-классификатор
            predicted_category, confidence = self.classifier.predict_category(temp_transaction)

        # Обновляем категорию на основе предсказания улучшенного классификатора
        if confidence > 0.7:
            check_data.category = predicted_category

        # Формируем финальную транзакцию
        transaction = TransactionData(
            type=check_data.type,
            category=check_data.category,
            amount=check_data.amount,
            comment=check_data.comment,
            username=user_username,
            retailer_name=check_data.retailer_name,
            items_list=check_data.items_list,
            payment_info=check_data.payment_info,
            transaction_dt=check_data.transaction_datetime
        )

        return transaction

    async def save_transaction(self, transaction: TransactionData) -> bool:
        """
        Сохраняет транзакцию в SQLite (First Write pattern) и обучает классификатор.
        """
        try:
            # Обучаем классификатор на новой транзакции перед записью
            self.classifier.train([transaction])

            # Проверяем, что репозиторий доступен
            if self.repository is None:
                raise Exception("Repository not initialized for TransactionService")
            
            # Извлекаем user_id из username (в реальной реализации user_id должен приходить из контекста пользователя)
            # Для тестирования используем фиктивный user_id
            user_id = 1 # В реальной реализации это должно быть получено из контекста
            
            # Записываем транзакцию в SQLite синхронно (First Write pattern)
            await self.repository.add_transaction(
                user_id=user_id,
                amount=transaction.amount,
                category=transaction.category,
                comment=transaction.comment
            )
            
            return True
        except Exception as e:
            logger.error(f"Ошибка при записи транзакции в SQLite: {e}")
            logger.debug(f"Стек вызова: {traceback.format_exc()}")
            raise SheetWriteError(f"Ошибка при записи транзакции в SQLite: {e}")

    async def add_keywords_for_transaction(self, category: str, retailer_name: str, items_list: str) -> bool:
        """
        Добавляет ключевые слова для транзакции в Google Sheets.
        """
        keywords_to_learn = extract_learnable_keywords(retailer_name, items_list)
        return await add_keywords_to_sheet(category, keywords_to_learn)

    async def finalize_transaction(self, transaction: TransactionData) -> Dict[str, Any]:
        """
        Финализирует транзакцию: сохраняет в Google Sheets и возвращает результат.
        """
        try:
            # Сохраняем транзакцию
            save_success = await self.save_transaction(transaction)
            
            if save_success:
                transaction_dt_str = transaction.transaction_dt.strftime('%d.%m.%Y %H:%M')
                
                result = {
                    'success': True,
                    'summary': (
                        f"✅ **Транзакция записана!**\n\n"
                        f"Дата операции: **{transaction_dt_str}**\n"
                        f"Тип: **{transaction.type}**\n"
                        f"Категория: **{transaction.category}**\n"
                        f"Сумма: **{transaction.amount}** руб.\n"
                        f"Комментарий: *{transaction.comment or 'Нет'}*"
                    )
                }
                return result
            else:
                return {
                    'success': False,
                    'error': 'Не удалось сохранить транзакцию'
                }
        except SheetWriteError as e:
            return {
                'success': False,
                'error': f"Ошибка записи в Google Sheets! Ошибка: {e}"
            }
        except asyncio.TimeoutError:
            return {
                'success': False,
                'error': f"Ошибка записи в Google Sheets! Превышено время ожидания"
            }
        except Exception as e:
            logger.error(f"Неизвестная ошибка при финализации транзакции: {e}")
            logger.debug(f"Стек вызова: {traceback.format_exc()}")
            return {
                'success': False,
                'error': f"Неизвестная ошибка: {e}"
            }

    async def load_categories(self) -> bool:
        """
        Загружает категории из Google Sheets.
        """
        return await load_categories_from_sheet()