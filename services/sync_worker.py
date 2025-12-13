import asyncio
import logging
from datetime import datetime
from .repository import TransactionRepository
from sheets.client import write_transaction
from models.transaction import TransactionData


logger = logging.getLogger(__name__)


async def start_sync_worker(bot, repository: TransactionRepository, sheets_client):
    while True:
        try:
            await asyncio.sleep(60)
            unsynced_transactions = await repository.get_unsynced()
            
            for transaction in unsynced_transactions:
                try:
                    # Преобразование данных из SQLite в модель TransactionData
                    transaction_data = TransactionData(
                        type="Расход",  # По умолчанию для транзакций из SQLite
                        category=transaction['category'],
                        amount=transaction['amount'],
                        comment=transaction['comment'] or '',
                        username=f"user_{transaction['user_id']}",  # Генерация username
                        transaction_dt=datetime.fromisoformat(transaction['created_at'].replace('Z', '+00:00')) if transaction['created_at'] else datetime.now()
                    )
                    
                    # Отправка в Google Sheets (асинхронный вызов)
                    await write_transaction(transaction_data)
                    
                    # Пометка как синхронизированной при успехе
                    await repository.mark_as_synced(transaction['id'])
                    
                except Exception as e:
                    logger.error(f"Failed to sync transaction {transaction['id']}: {e}")
                    
        except Exception as e:
            logger.error(f"Sync worker error: {e}")
            await asyncio.sleep(60)  # Пауза перед следующей итерацией при ошибке