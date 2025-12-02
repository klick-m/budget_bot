# sheets/client.py
import asyncio
import gspread
from datetime import datetime
from typing import List

# Импортируем переменные из нашего нового модуля конфигурации
from config import (
    SERVICE_KEY, 
    GOOGLE_SHEET_URL, 
    DATA_SHEET_NAME, 
    CATEGORIES_SHEET_NAME, 
    CATEGORY_STORAGE, 
    logger
)
# Импортируем наши Pydantic модели
from models.transaction import TransactionData
# Импортируем наши кастомные исключения
from utils.exceptions import SheetConnectionError, SheetWriteError


async def get_google_sheet_client(sheet_name: str) -> gspread.Worksheet:
    """Устанавливает асинхронное соединение с листом Google Sheets."""
    try:
        # SERVICE_KEY берется из config.py, который прочитал его из .env
        gc = await asyncio.to_thread(gspread.service_account, filename=SERVICE_KEY) 
        # GOOGLE_SHEET_URL берется из config.py
        sh = await asyncio.to_thread(gc.open_by_url, GOOGLE_SHEET_URL)
        # sheet_name - это либо 'Транзакции', либо 'Categories' (из config.py)
        ws = await asyncio.to_thread(sh.worksheet, sheet_name)
        return ws
    except Exception as e:
        logger.error(f"❌ Ошибка подключения к Google Sheets (лист {sheet_name}): {e}")
        raise SheetConnectionError(f"Не удалось подключиться к листу {sheet_name}.")


async def load_categories_from_sheet() -> bool:
    """Загружает списки категорий и ключевые слова в CATEGORY_STORAGE."""
    try:
        ws = await get_google_sheet_client(CATEGORIES_SHEET_NAME)
    except SheetConnectionError:
        return False

    try:
        # Выполняем синхронную операцию в отдельном потоке
        all_values = await asyncio.to_thread(ws.get_all_values)

        # Очищаем хранилище перед обновлением
        CATEGORY_STORAGE.expense.clear()
        CATEGORY_STORAGE.income.clear()
        CATEGORY_STORAGE.keywords.clear() 

        for row in all_values[1:]: # Пропускаем заголовок
            expense_cat = row[0].strip() if len(row) > 0 else ''     
            keywords_str = row[1].strip() if len(row) > 1 else ''   
            income_cat = row[2].strip() if len(row) > 2 else ''    
            
            if expense_cat:
                CATEGORY_STORAGE.expense.append(expense_cat)
                
                if keywords_str:
                    keywords_list = [k.strip().lower() for k in keywords_str.split(',') if k.strip()]
                    if keywords_list:
                        CATEGORY_STORAGE.keywords[expense_cat] = keywords_list 
                        
            if income_cat:
                CATEGORY_STORAGE.income.append(income_cat)
        
        CATEGORY_STORAGE.last_loaded = datetime.now()
        
        logger.info(f"✅ Категории загружены. Расход: {len(CATEGORY_STORAGE.expense)}, Доход: {len(CATEGORY_STORAGE.income)}. Ключевых слов: {len(CATEGORY_STORAGE.keywords)}")
        return True

    except Exception as e:
        logger.error(f"❌ Ошибка обработки данных категорий: {e}")
        return False


async def write_transaction(transaction: TransactionData):
    """
    Асинхронно записывает транзакцию в лист 'Транзакции', используя Pydantic модель.
    """
    try:
        ws = await get_google_sheet_client(DATA_SHEET_NAME)
    except SheetConnectionError as e:
        raise SheetWriteError(e)

    # Преобразуем Pydantic модель в список для записи
    row = [
        transaction.transaction_dt.strftime("%d.%m.%Y"),
        transaction.transaction_dt.strftime("%H:%M:%S"),
        transaction.type,
        transaction.category,
        transaction.amount,
        transaction.comment,
        transaction.username,
        transaction.retailer_name,
        transaction.items_list,
        transaction.payment_info
    ]
    
    try:
        # Используем append_rows вместо append_row - это быстрее! (Пункт 9 в рекомендациях)
        await asyncio.to_thread(ws.append_rows, [row])
    except Exception as e:
        logger.error(f"❌ Ошибка записи транзакции: {e}")
        raise SheetWriteError(f"Не удалось записать транзакцию в Sheets: {e}")


async def add_keywords_to_sheet(category: str, new_keywords: List[str]) -> bool:
    """
    Добавляет список новых ключевых слов к указанной категории в листе Categories.
    """
    if not new_keywords:
        return True 

    normalized_keywords_to_add = list(set([k.strip().lower() for k in new_keywords if k.strip()]))
    
    try:
        ws = await get_google_sheet_client(CATEGORIES_SHEET_NAME)

        list_of_lists = await asyncio.to_thread(ws.get_all_values, value_render_option='UNFORMATTED_VALUE')
        
        for i, row in enumerate(list_of_lists):
            if i > 0 and row and row[0].strip() == category:
                
                row_index = i + 1 
                current_keywords_str = row[1].strip() if len(row) > 1 else '' 
                
                current_keywords = [k.strip().lower() for k in current_keywords_str.split(',') if k.strip()]
                unique_new_keywords = [k for k in normalized_keywords_to_add if k not in current_keywords]

                if not unique_new_keywords:
                    logger.info(f"Все ключевые слова уже существуют для категории '{category}'. Пропуск записи в Sheets.")
                    return True

                # Логика добавления новых слов к существующей строке
                new_keywords_str = current_keywords_str
                if new_keywords_str and not new_keywords_str.endswith(','):
                    new_keywords_str += ','
                    
                new_keywords_str += ', '.join(unique_new_keywords)

                # Выполняем обновление ячейки в отдельном потоке
                await asyncio.to_thread(ws.update_cell, row_index, 2, new_keywords_str.strip(' ,'))

                # Обновляем локальное хранилище CATEGORY_STORAGE
                if category not in CATEGORY_STORAGE.keywords: CATEGORY_STORAGE.keywords[category] = []
                for k in unique_new_keywords:
                    if k not in CATEGORY_STORAGE.keywords[category]:
                        CATEGORY_STORAGE.keywords[category].append(k)

                logger.info(f"✅ Добавлено {len(unique_new_keywords)} новых ключевых слов к категории '{category}'.")
                return True
        
        logger.warning(f"Категория '{category}' не найдена в столбце A листа 'Categories'. Ключевые слова не добавлены.")
        return False

    except SheetConnectionError:
        return False
    except Exception as e:
        logger.error(f"❌ Ошибка при добавлении ключевых слов в Google Sheets: {e}")
        return False