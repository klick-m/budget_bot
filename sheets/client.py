# sheets/client.py
"""
Модуль для работы с Google Sheets API в асинхронном режиме.
Все синхронные вызовы обернуты в asyncio.to_thread() для предотвращения блокировки event loop.
"""
# sheets/client.py
import asyncio
import gspread
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from functools import lru_cache

# Импортируем переменные из нашего нового модуля конфигурации
from config import (
    SERVICE_KEY,
    GOOGLE_SHEET_URL,
    DATA_SHEET_NAME,
    CATEGORIES_SHEET_NAME,
    KEYWORDS_SHEET_NAME,
    CATEGORY_STORAGE,
    logger,
    SHEET_WRITE_TIMEOUT
)
# Импортируем наши Pydantic модели
# --- АРХИТЕКТУРНЫЙ СТАНДАРТ ---
# Все синхронные функции, использующиеся в асинхронном контексте, должны быть обернуты в asyncio.to_thread()
# Это предотвращает блокировку event loop и обеспечивает асинхронную производительность
# --- КЕШИРОВАНИЕ КЛИЕНТОВ И РАБОЧИХ ЛИСТОВ ---
from models.transaction import TransactionData
# Импортируем наши кастомные исключения
from utils.exceptions import SheetConnectionError, SheetWriteError

# --- СТАРЫЙ КЛАСС GoogleSheetsClient ДЛЯ СОВМЕСТИМОСТИ ---
class GoogleSheetsClient:
    """Старый класс для синхронной работы с Google Sheets, используется в KeywordDictionary"""
    def __init__(self):
        self._gc = None
        self._sheets = {}
        self._last_gc_time = None
        self._gc_timeout = 3600  # Переподключаться каждый час

    def _get_client(self):
        """Получает (или создаёт) синхронный Google Sheets клиент."""
        import gspread
        from config import SERVICE_KEY
        from datetime import datetime
        from config import logger

        now = datetime.now()

        # Переподключаемся если прошло > часа или клиент не инициализирован
        if self._gc is None or (
            self._last_gc_time and
            (now - self._last_gc_time).total_seconds() > self._gc_timeout
        ):
            try:
                self._gc = gspread.service_account(filename=SERVICE_KEY)
                self._last_gc_time = now
                self._sheets.clear()  # Очищаем кеш листов при переподключении
                logger.info("✅ Переподключение к Google Sheets выполнено успешно (синхронный клиент)")
            except Exception as e:
                logger.error(f"❌ Критическая ошибка подключения к Google Sheets: {e}")
                self._gc = None
                raise e

        return self._gc

    def get_sheet_data(self, spreadsheet_url, sheet_name):
        """Получает данные из указанного листа"""
        from config import logger
        from config import GOOGLE_SHEET_URL

        # Если spreadsheet_url пустой, используем глобальный
        if not spreadsheet_url:
            spreadsheet_url = GOOGLE_SHEET_URL

        try:
            # Проверяем, есть ли закэшированные данные в новом кэше
            cached_data = _sheets_cache.get_cached_data(sheet_name)
            if cached_data is not None:
                return cached_data

            gc = self._get_client()
            sh = gc.open_by_url(spreadsheet_url)
            ws = sh.worksheet(sheet_name)
            # Используем batch-запрос для получения всех значений за один вызов API
            data = ws.get_all_values()
            # Кэшируем данные в новом кэше
            _sheets_cache.cache_data(sheet_name, data)
            return data
        except Exception as e:
            # Проверяем, является ли ошибка ошибкой превышения квоты
            is_rate_limit = False
            if hasattr(e, 'response') and getattr(e.response, 'status_code', None) == 429:
                is_rate_limit = True
            elif "429" in str(e) or "quota" in str(e).lower() or "RATE_LIMIT_EXCEEDED" in str(e):
                is_rate_limit = True

            if is_rate_limit:
                logger.warning(f"Превышена квота Google API при получении данных из листа {sheet_name}: {e}")
            else:
                logger.error(f"❌ Ошибка получения данных из листа {sheet_name}: {e}")
            raise e


# --- КЕШИРОВАНИЕ КЛИЕНТОВ И РАБОЧИХ ЛИСТОВ ---
class GoogleSheetsCache:
    """Кеширует подключения к Google Sheets для избежания переподключений."""
    def __init__(self):
        self._gc = None
        self._sheets: Dict[str, gspread.Worksheet] = {}
        self._last_gc_time = None
        self._gc_timeout = 3600  # Переподключаться каждый час
        # Добавляем кэш для данных с TTL
        self._data_cache: Dict[str, Dict] = {}
        self._cache_timestamps: Dict[str, datetime] = {}
        self._cache_ttl_seconds = 300  # 5 минут TTL для кэша данных
    
    async def get_client(self):
        """Получает (или создаёт) кешированный Google Sheets клиент."""
        now = datetime.now()
        
        # Переподключаемся если прошло > часа или клиент не инициализирован
        if self._gc is None or (
            self._last_gc_time and 
            (now - self._last_gc_time).total_seconds() > self._gc_timeout
        ):
            try:
                self._gc = await asyncio.to_thread(gspread.service_account, filename=SERVICE_KEY)
                self._last_gc_time = now
                self._sheets.clear()  # Очищаем кеш листов при переподключении
                logger.info("✅ Переподключение к Google Sheets выполнено успешно")
            except Exception as e:
                logger.error(f"❌ Критическая ошибка подключения к Google Sheets: {e}")
                self._gc = None
                raise SheetConnectionError(f"Не удалось подключиться к Google Sheets: {e}")
        
        return self._gc
    
    async def get_worksheet(self, sheet_name: str) -> gspread.Worksheet:
        """Получает кешированный рабочий лист."""
        if sheet_name not in self._sheets:
            try:
                gc = await self.get_client()
                sh = await asyncio.to_thread(gc.open_by_url, GOOGLE_SHEET_URL)
                
                # Обработка ошибки превышения квоты с надежным циклом
                retries = 5
                base_delay = 10  # seconds

                for attempt in range(retries):
                    try:
                        # Try to fetch the worksheet
                        ws = await asyncio.to_thread(sh.worksheet, sheet_name)
                        self._sheets[sheet_name] = ws
                        break
                    except Exception as e:
                        # Check for Rate Limit Error (429)
                        is_rate_limit = False
                        if hasattr(e, 'response') and getattr(e.response, 'status_code', None) == 429:
                            is_rate_limit = True
                        elif "429" in str(e) or "quota" in str(e).lower() or "RATE_LIMIT_EXCEEDED" in str(e):
                            is_rate_limit = True

                        if is_rate_limit:
                            # Используем экспоненциальную задержку с jitter
                            base_wait = base_delay * (2 ** attempt)  # Экспоненциальная задержка
                            import random
                            jitter = random.uniform(0, base_wait * 0.1)  # Добавляем небольшой jitter
                            wait_time = base_wait + jitter
                            
                            # CRITICAL: Log this so the user knows the bot is NOT frozen
                            print(f"⚠️ Google API Quota exceeded (429). Waiting {wait_time:.2f}s before retry {attempt+1}/{retries}...")
                            logger.warning(f"Google API Quota exceeded (429). Waiting {wait_time:.2f}s before retry {attempt+1}/{retries}...")
                            await asyncio.sleep(wait_time)
                        else:
                            # If it's a real error (e.g. Sheet not found), raise it immediately
                            raise e
                else:
                    # Если не удалось подключиться после всех попыток
                    raise SheetConnectionError(f"Could not connect to sheet '{sheet_name}' after {retries} retries.")
                    
            except SheetConnectionError:
                raise
            except Exception as e:
                logger.error(f"❌ Ошибка получения листа '{sheet_name}': {e}")
                raise SheetConnectionError(f"Не удалось подключиться к листу {sheet_name}.")
        
        return self._sheets[sheet_name]

    def _is_cache_valid(self, sheet_name: str) -> bool:
        """Проверяет, действителен ли кэш для указанного листа."""
        if sheet_name not in self._cache_timestamps:
            return False
        return (datetime.now() - self._cache_timestamps[sheet_name]).total_seconds() < self._cache_ttl_seconds

    def get_cached_data(self, sheet_name: str) -> Optional[List]:
        """Получает закэшированные данные для указанного листа."""
        if self._is_cache_valid(sheet_name):
            return self._data_cache.get(sheet_name)
        return None

    def cache_data(self, sheet_name: str, data: List):
        """Кэширует данные для указанного листа."""
        self._data_cache[sheet_name] = data
        self._cache_timestamps[sheet_name] = datetime.now()

# Глобальный кеш (один на приложение)
_sheets_cache = GoogleSheetsCache()


async def get_google_sheet_client(sheet_name: str) -> gspread.Worksheet:
    """Устанавливает асинхронное соединение с листом Google Sheets (с кешированием)."""
    try:
        return await _sheets_cache.get_worksheet(sheet_name)
    except SheetConnectionError:
        raise

async def get_sheet_data_with_cache(sheet_name: str) -> List:
    """Получает данные из листа с использованием кэширования."""
    # Проверяем, есть ли закэшированные данные
    cached_data = _sheets_cache.get_cached_data(sheet_name)
    if cached_data is not None:
        return cached_data

    # Если данных нет в кэше, получаем их из Google Sheets
    try:
        ws = await get_google_sheet_client(sheet_name)
        data = await asyncio.to_thread(ws.get_all_values)
    except Exception as e:
        # Проверяем, является ли ошибка ошибкой превышения квоты
        is_rate_limit = False
        if hasattr(e, 'response') and getattr(e.response, 'status_code', None) == 429:
            is_rate_limit = True
        elif "429" in str(e) or "quota" in str(e).lower() or "RATE_LIMIT_EXCEEDED" in str(e):
            is_rate_limit = True

        if is_rate_limit:
            logger.warning(f"Превышена квота Google API при получении данных из листа {sheet_name}: {e}")
            # В случае ошибки квоты, возвращаем пустой список вместо падения
            return []
        else:
            logger.error(f"❌ Ошибка при получении данных из листа {sheet_name}: {e}")
            raise

    # Кэшируем данные
    _sheets_cache.cache_data(sheet_name, data)
    return data


async def load_categories_from_sheet() -> bool:
    """Загружает списки категорий и ключевые слова в CATEGORY_STORAGE."""
    try:
        # Получаем данные с использованием кэширования
        all_values = await get_sheet_data_with_cache(CATEGORIES_SHEET_NAME)

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
        
        # Обновляем KeywordDictionary после загрузки категорий
        try:
            # Импортируем classifier внутри функции, чтобы избежать циклического импорта
            from utils.category_classifier import classifier
            # Обновляем словарь ключевых слов в KeywordDictionary
            for category, keywords in CATEGORY_STORAGE.keywords.items():
                try:
                    for keyword in keywords:
                        classifier.add_keyword(keyword, category, save_to_sheet=False)
                except (KeyError, ValueError) as e:
                    logger.warning(f"⚠️ Категория mapping failed для '{category}', используем raw string: {e}")
                    # Продолжаем с другими категориями
                    continue
            logger.info(f"✅ KeywordDictionary обновлен с {len(CATEGORY_STORAGE.keywords)} категориями.")
        except Exception as e:
            logger.error(f"❌ Ошибка обновления KeywordDictionary: {e}")
            
        return True

    except Exception as e:
        # Проверяем, является ли ошибка ошибкой превышения квоты
        is_rate_limit = False
        if hasattr(e, 'response') and getattr(e.response, 'status_code', None) == 429:
            is_rate_limit = True
        elif "429" in str(e) or "quota" in str(e).lower() or "RATE_LIMIT_EXCEEDED" in str(e):
            is_rate_limit = True

        if is_rate_limit:
            logger.warning(f"Превышена квота Google API при загрузке категорий: {e}")
        else:
            logger.error(f"❌ Ошибка обработки данных категорий: {e}")
        return False


async def write_transaction(transaction: TransactionData):
    """
    Асинхронно записывает транзакцию в лист 'Транзакции', используя Pydantic модель.
    """
    max_retries = 3
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            ws = await get_google_sheet_client(DATA_SHEET_NAME)
            break
        except SheetConnectionError as e:
            retry_count += 1
            if retry_count >= max_retries:
                raise SheetWriteError(f"Не удалось подключиться к Google Sheets после {max_retries} попыток: {e}")
            await asyncio.sleep(1)  # Ждем 1 секунду перед повторной попыткой

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
    
    retry_count = 0
    while retry_count < max_retries:
        try:
            # Используем append_rows вместо append_row - это быстрее! (Пункт 9 в рекомендациях)
            await asyncio.to_thread(ws.append_rows, [row])
            # Инвалидируем кэш данных транзакций, так как данные изменились
            if DATA_SHEET_NAME in _sheets_cache._data_cache:
                del _sheets_cache._data_cache[DATA_SHEET_NAME]
            if DATA_SHEET_NAME in _sheets_cache._cache_timestamps:
                del _sheets_cache._cache_timestamps[DATA_SHEET_NAME]
            break
        except Exception as e:
            # Проверяем, является ли ошибка ошибкой превышения квоты
            is_rate_limit = False
            if hasattr(e, 'response') and getattr(e.response, 'status_code', None) == 429:
                is_rate_limit = True
            elif "429" in str(e) or "quota" in str(e).lower() or "RATE_LIMIT_EXCEEDED" in str(e):
                is_rate_limit = True

            if is_rate_limit:
                logger.warning(f"Превышена квота Google API при записи транзакции: {e}")
                # Используем экспоненциальную задержку с jitter
                import random
                base_delay = 10 # базовая задержка
                wait_time = base_delay * (2 ** retry_count) + random.uniform(0, base_delay * 0.1)
                await asyncio.sleep(wait_time)
            else:
                logger.error(f"❌ Ошибка записи транзакции: {e}")
                retry_count += 1
                if retry_count >= max_retries:
                    raise SheetWriteError(f"Не удалось записать транзакцию в Sheets: {e}")
                await asyncio.sleep(1)  # Ждем 1 секунду перед повторной попыткой


async def add_keywords_to_sheet(category: str, new_keywords: List[str]) -> bool:
    """
    Добавляет список новых ключевых слов к указанной категории в листе Categories.
    """
    if not new_keywords:
        return True

    normalized_keywords_to_add = list(set([k.strip().lower() for k in new_keywords if k.strip()]))
    
    max_retries = 3
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            ws = await get_google_sheet_client(CATEGORIES_SHEET_NAME)
            break
        except SheetConnectionError:
            retry_count += 1
            if retry_count >= max_retries:
                return False
            await asyncio.sleep(1)  # Ждем 1 секунду перед повторной попыткой

    try:
        # Вместо получения всех значений, ищем только нужную строку
        try:
            # Ищем категорию в первом столбце
            cell = await asyncio.to_thread(ws.find, category, in_column=1)
            row_index = cell.row
            
            # Получаем только строку с нужной категорией
            row = await asyncio.to_thread(ws.row_values, row_index, value_render_option='UNFORMATTED_VALUE')
            
            if row and row[0].strip() == category:
                
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

                # Инвалидируем кэш категорий, так как данные изменились
                invalidate_categories_cache()

                logger.info(f"✅ Добавлено {len(unique_new_keywords)} новых ключевых слов к категории '{category}'.")
                return True
        except gspread.exceptions.CellNotFound:
            logger.warning(f"Категория '{category}' не найдена в столбце A листа 'Categories'. Ключевые слова не добавлены.")
            return False
        
        logger.warning(f"Категория '{category}' не найдена в столбце A листа 'Categories'. Ключевые слова не добавлены.")
        return False

    except SheetConnectionError:
        return False
    except Exception as e:
        # Проверяем, является ли ошибка ошибкой превышения квоты
        is_rate_limit = False
        if hasattr(e, 'response') and getattr(e.response, 'status_code', None) == 429:
            is_rate_limit = True
        elif "429" in str(e) or "quota" in str(e).lower() or "RATE_LIMIT_EXCEEDED" in str(e):
            is_rate_limit = True

        if is_rate_limit:
            logger.warning(f"Превышена квота Google API при добавлении ключевых слов: {e}")
        else:
            logger.error(f"❌ Ошибка при добавлении ключевых слов в Google Sheets: {e}")
        return False


async def get_latest_transactions(user_id: str, limit: int = 5, offset: int = 0) -> list[dict]:
    """
    Извлекает последние limit транзакций пользователя user_id из таблицы RawData,
    начиная со смещения offset. Функция возвращает список словарей.
    """
    try:
        # Получаем данные с использованием кэширования
        all_values = await get_sheet_data_with_cache(DATA_SHEET_NAME)
        
        # Пропускаем заголовок (если он есть)
        if all_values and len(all_values) > 0:
            headers = all_values[0]  # Предполагаем, что первая строка - заголовки
            rows = all_values[1:]
        else:
            return []
        
        # Фильтруем транзакции по username (user_id)
        user_transactions = []
        for row in rows:
            if len(row) > 6:  # Убедимся, что индекс username (6) доступен
                username = row[6] if len(row) > 6 else ""
                if username == user_id:
                    # Создаем словарь с данными транзакции
                    transaction_dict = {
                        "date": row[0] if len(row) > 0 else "",
                        "time": row[1] if len(row) > 1 else "",
                        "type": row[2] if len(row) > 2 else "",
                        "category": row[3] if len(row) > 3 else "",
                        "amount": row[4] if len(row) > 4 else "",
                        "comment": row[5] if len(row) > 5 else "",
                        "username": row[6] if len(row) > 6 else "",
                        "retailer_name": row[7] if len(row) > 7 else "",
                        "items_list": row[8] if len(row) > 8 else "",
                        "payment_info": row[9] if len(row) > 9 else ""
                    }
                    user_transactions.append(transaction_dict)
        
        # Сортируем транзакции по дате и времени (предполагаем формат DD.MM.YYYY HH:MM:SS)
        def parse_datetime(transaction):
            try:
                dt_str = f"{transaction['date']} {transaction['time']}"
                return datetime.strptime(dt_str, "%d.%m.%Y %H:%M:%S")
            except ValueError as e:
                # Если формат даты не распознан, возвращаем минимальную дату
                logger.warning(f"Ошибка парсинга даты и времени: {e}")
                return datetime.min

        user_transactions.sort(key=parse_datetime, reverse=True)
        
        # Применяем лимит и смещение
        start_idx = offset
        end_idx = offset + limit
        paginated_transactions = user_transactions[start_idx:end_idx]
        
        return paginated_transactions

    except Exception as e:
        # Проверяем, является ли ошибка ошибкой превышения квоты
        is_rate_limit = False
        if hasattr(e, 'response') and getattr(e.response, 'status_code', None) == 429:
            is_rate_limit = True
        elif "429" in str(e) or "quota" in str(e).lower() or "RATE_LIMIT_EXCEEDED" in str(e):
            is_rate_limit = True

        if is_rate_limit:
            logger.warning(f"Превышена квота Google API при получении транзакций: {e}")
        else:
            logger.error(f"❌ Ошибка при получении транзакций пользователя {user_id}: {e}")
        return []


async def add_keyword_to_sheet(keyword: str, category: str, confidence: float = 1.0) -> bool:
    """
    Добавляет новое ключевое слово в лист Keywords.
    """
    max_retries = 3
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            ws = await get_google_sheet_client(KEYWORDS_SHEET_NAME)
            break
        except SheetConnectionError:
            retry_count += 1
            if retry_count >= max_retries:
                return False
            await asyncio.sleep(1)  # Ждем 1 секунду перед повторной попыткой

    try:
        # Подготовляем строку для добавления
        row = [keyword, category, confidence]
        
        # Добавляем строку в таблицу
        await asyncio.to_thread(ws.append_rows, [row])
        
        # Инвалидируем кэш ключевых слов, так как данные изменились
        if KEYWORDS_SHEET_NAME in _sheets_cache._data_cache:
            del _sheets_cache._data_cache[KEYWORDS_SHEET_NAME]
        if KEYWORDS_SHEET_NAME in _sheets_cache._cache_timestamps:
            del _sheets_cache._cache_timestamps[KEYWORDS_SHEET_NAME]
        
        logger.info(f"✅ Ключевое слово '{keyword}' добавлено в таблицу '{KEYWORDS_SHEET_NAME}' с категорией '{category}'.")
        return True
        
    except Exception as e:
        # Проверяем, является ли ошибка ошибкой превышения квоты
        is_rate_limit = False
        if hasattr(e, 'response') and getattr(e.response, 'status_code', None) == 429:
            is_rate_limit = True
        elif "429" in str(e) or "quota" in str(e).lower() or "RATE_LIMIT_EXCEEDED" in str(e):
            is_rate_limit = True

        if is_rate_limit:
            logger.warning(f"Превышена квота Google API при добавлении ключевого слова: {e}")
        else:
            logger.error(f"❌ Ошибка при добавлении ключевого слова в Google Sheets: {e}")
        return False

# Обновляем кэш после добавления ключевых слов
def invalidate_categories_cache():
    """Инвалидирует кэш данных для листа категорий."""
    if CATEGORIES_SHEET_NAME in _sheets_cache._data_cache:
        del _sheets_cache._data_cache[CATEGORIES_SHEET_NAME]
    if CATEGORIES_SHEET_NAME in _sheets_cache._cache_timestamps:
        del _sheets_cache._cache_timestamps[CATEGORIES_SHEET_NAME]

