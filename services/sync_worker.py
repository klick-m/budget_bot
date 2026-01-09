import asyncio
import logging
from datetime import datetime
from .repository import TransactionRepository
from sheets.client import write_transaction
from models.transaction import TransactionData


logger = logging.getLogger(__name__)


async def start_sync_worker(bot, repository: TransactionRepository, sheets_client):
    logger.info("Sync worker started.")
    while True:
        try:
            # Сначала проверяем, есть ли что-то для синхронизации
            unsynced_transactions = await repository.get_unsynced()
            
            if unsynced_transactions:
                logger.info(f"Найдено {len(unsynced_transactions)} несинхронизированных транзакций. Начинаю процесс...")
            
            for transaction in unsynced_transactions:
                try:
                    # Преобразование данных из SQLite в модель TransactionData
                    # Проверяем, что amount - это число, а category - строка
                    try:
                        # Обработка строки суммы: замена запятой на точку и удаление пробелов
                        amount_raw = str(transaction['amount']).replace(',', '.').replace(' ', '').replace('\xa0', '')
                        amount_value = float(amount_raw)
                        # Убедимся, что category - это строка
                        category_value = str(transaction['category']) if transaction['category'] is not None else ''
                        
                        transaction_data = TransactionData(
                            type=transaction.get('type', 'Расход'),  # Получаем тип из БД
                            category=category_value,
                            amount=amount_value,
                            comment=transaction['comment'] or '',
                            username=transaction['username'] or f"user_{transaction['user_id']}",  # Используем реальное имя пользователя из базы данных
                            transaction_dt=datetime.fromisoformat(transaction['created_at'].replace('Z', '+00:00')) if transaction['created_at'] else datetime.now()
                        )
                    except (ValueError, TypeError) as validation_error:
                        logger.error(f"Неверный формат данных для транзакции {transaction['id']}: amount={transaction['amount']}, category={transaction['category']}")
                        logger.debug(f"Стек вызова: {validation_error}")
                        # НЕ помечаем как синхронизированную, чтобы админ мог исправить данные в БД
                        continue  # Переходим к следующей транзакции
                    
                    # Отправка в Google Sheets (асинхронный вызов)
                    await write_transaction(transaction_data)
                    
                    # Пометка как синхронизированной ТОЛЬКО при успехе
                    await repository.mark_as_synced(transaction['id'])
                    
                except Exception as e:
                    # Ошибки Google Sheets логируются, но не крашат бота
                    # Транзакция остается несинхронизированной и будет повторена в следующий раз
                    logger.error(f"Failed to sync transaction {transaction['id']} to Google Sheets: {e}")
                    logger.debug(f"Transaction details: {transaction}")
            
            # Ждем перед следующей проверкой
            await asyncio.sleep(60)
            
        except asyncio.CancelledError:
            # Обработка отмены задачи (например, при завершении бота)
            logger.info("Sync worker received cancellation signal. Stopping...")
            break  # Выход из бесконечного цикла
        except Exception as e:
            # Общие ошибки воркера также логируются, но не крашат бота
            logger.error(f"Sync worker error: {e}")
            await asyncio.sleep(60)  # Пауза перед следующей итерацией при ошибке