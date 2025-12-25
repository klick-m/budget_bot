# utils/receipt_logic.py
import re
import aiohttp
import asyncio
from typing import Optional, List

# Импорт из нашей структуры
from config import CHECK_API_TOKEN, CHECK_API_URL, CHECK_API_TIMEOUT, CATEGORY_STORAGE, logger
from utils.category_classifier import classifier

from models.transaction import CheckData
from utils.exceptions import CheckApiTimeout, CheckApiRecognitionError

def map_category_by_keywords(search_string: str) -> str:
    """Присваивает категорию на основе ключевых слов в строке поиска."""
    # Используем новую систему KeywordDictionary для определения категории
    result = classifier.get_category_by_keyword(search_string)
    if result:
        category, confidence = result
        # Проверяем, что категория существует в списке расходов
        if category in CATEGORY_STORAGE.expense:
            return category
    
    # Если новая система не дала результата, используем старую логику
    normalized_comment = search_string.lower()
    
    # Ищем совпадения по ключевым словам в хранилище CATEGORY_STORAGE
    for category, keywords in CATEGORY_STORAGE.keywords.items():
        # Проверяем, что категория существует в списке расходов
        if category in CATEGORY_STORAGE.expense:
            for keyword in keywords:
                if keyword in normalized_comment:
                    return category # Возвращаем первое совпадение
                
    # Если совпадений нет, возвращаем последнюю категорию (обычно "Прочее Расход")
    if CATEGORY_STORAGE.expense:
        return CATEGORY_STORAGE.expense[-1]
    else:
        # Если список расходов пуст, возвращаем стандартную категорию
        return "Прочее Расход"


def extract_learnable_keywords(retailer_name: str, items_list_str: str) -> List[str]:
    """Извлекает значимые слова из чека (продавца и товаров) для обучения."""
    
    keywords = [retailer_name.strip()]

    item_names = [name.strip() for name in items_list_str.split('|') if name.strip()]

    # Список незначащих слов для фильтрации
    stop_words = {
        'руб', 'шт', 'скидка', 'скидки', 'акция', 'товар', 'услуга', 'чек', 'касса',
        'продажа', 'возврат', 'ру', 'руc', 'рф', 'ооо', 'ип', 'оао', 'пао', 'ао',
        'безнал', 'нал', 'оплата', 'цена', 'итого', 'наименование', 'артикул', 'код'
    }
    
    for name in item_names:
        cleaned_name = re.sub(r'[\d\.\,\/\-\(\)\*\"]', ' ', name.lower())
        words = cleaned_name.split()
        
        for word in words:
            word = word.strip()
            # Фильтруем короткие (меньше 3 символов) и стоп-слова
            if len(word) > 2 and word not in stop_words and not word.isdigit():
                # Проверяем, что слово содержит хотя бы одну букву
                if any(c.isalpha() for c in word):
                    keywords.append(word)

    return list(set([k.lower() for k in keywords]))


async def parse_check_from_api(image_data: bytes, session: Optional[aiohttp.ClientSession] = None) -> CheckData:
    """
    Отправляет файл изображения чека в API Proverkacheka.com и возвращает Pydantic-модель CheckData.
    """
    if not CHECK_API_TOKEN:
        logger.error("⛔ CHECK_API_TOKEN не найден.")
        raise CheckApiRecognitionError('API ключ Proverkacheka.com отсутствует.')

    # Подготовим данные для отправки
    data = aiohttp.FormData()
    # CHECK_API_TOKEN берется из config.py
    data.add_field('token', CHECK_API_TOKEN)
    data.add_field(
        'qrfile',
        image_data,
        filename='qrimage.jpg',
        content_type='image/jpeg'
    )
    
    # Максимальное количество попыток
    max_retries = 5
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            # Используем переданный сеанс или создаем новый
            session_to_use = session if session is not None else aiohttp.ClientSession()
            own_session = session is None  # Флаг для определения, нужно ли закрывать сеанс
            
            try:
                # CHECK_API_TIMEOUT берется из config.py
                async with asyncio.timeout(CHECK_API_TIMEOUT):
                    async with session_to_use.post(CHECK_API_URL, data=data) as response:
                        
                        # Обработка специфических HTTP ошибок
                        if response.status == 400:
                            error_text = await response.text()
                            logger.error(f"❌ HTTP Error 400 (Bad Request): {error_text}. URL: {CHECK_API_URL}")
                            raise CheckApiRecognitionError(f'HTTP Error 400: Некорректный запрос. {error_text}')
                        elif response.status == 401:
                            error_text = await response.text()
                            logger.error(f"❌ HTTP Error 401 (Unauthorized): {error_text}. URL: {CHECK_API_URL}")
                            raise CheckApiRecognitionError(f'HTTP Error 401: Неавторизованный доступ. Проверьте API токен. {error_text}')
                        elif response.status == 403:
                            error_text = await response.text()
                            logger.error(f"❌ HTTP Error 403 (Forbidden): {error_text}. URL: {CHECK_API_URL}")
                            raise CheckApiRecognitionError(f'HTTP Error 403: Доступ запрещен. {error_text}')
                        elif response.status == 429:
                            error_text = await response.text()
                            logger.warning(f"⚠️ HTTP Error 429 (Too Many Requests): {error_text}. URL: {CHECK_API_URL}")
                            
                            # Используем экспоненциальную задержку с jitter
                            import random
                            base_delay = 10  # базовая задержка в секундах
                            jitter = random.uniform(0, base_delay * 0.1)  # jitter 10% от базовой задержки
                            wait_time = base_delay * (2 ** retry_count) + jitter  # экспоненциальная задержка
                            
                            logger.info(f"⚠️ Превышено количество запросов. Повторная попытка через {wait_time:.2f} секунд...")
                            await asyncio.sleep(wait_time)
                            retry_count += 1
                            continue  # Повторная попытка
                        elif response.status == 500:
                            error_text = await response.text()
                            logger.error(f"❌ HTTP Error 500 (Internal Server Error): {error_text}. URL: {CHECK_API_URL}")
                            
                            # Используем экспоненциальную задержку с jitter
                            import random
                            base_delay = 5  # базовая задержка в секундах
                            jitter = random.uniform(0, base_delay * 0.1)
                            wait_time = base_delay * (2 ** retry_count) + jitter
                            
                            logger.info(f"⚠️ Внутренняя ошибка сервера. Повторная попытка через {wait_time:.2f} секунд...")
                            await asyncio.sleep(wait_time)
                            retry_count += 1
                            continue  # Повторная попытка
                        elif response.status == 502:
                            error_text = await response.text()
                            logger.error(f"❌ HTTP Error 502 (Bad Gateway): {error_text}. URL: {CHECK_API_URL}")
                            
                            # Используем экспоненциальную задержку с jitter
                            import random
                            base_delay = 5
                            jitter = random.uniform(0, base_delay * 0.1)
                            wait_time = base_delay * (2 ** retry_count) + jitter
                            
                            logger.info(f"⚠️ Ошибка шлюза. Повторная попытка через {wait_time:.2f} секунд...")
                            await asyncio.sleep(wait_time)
                            retry_count += 1
                            continue  # Повторная попытка
                        elif response.status == 503:
                            error_text = await response.text()
                            logger.error(f"❌ HTTP Error 503 (Service Unavailable): {error_text}. URL: {CHECK_API_URL}")
                            
                            # Используем экспоненциальную задержку с jitter
                            import random
                            base_delay = 5
                            jitter = random.uniform(0, base_delay * 0.1)
                            wait_time = base_delay * (2 ** retry_count) + jitter
                            
                            logger.info(f"⚠️ Сервис недоступен. Повторная попытка через {wait_time:.2f} секунд...")
                            await asyncio.sleep(wait_time)
                            retry_count += 1
                            continue  # Повторная попытка
                        elif response.status != 200:
                            error_text = await response.text()
                            logger.error(f"❌ HTTP Error {response.status}: {error_text}. URL: {CHECK_API_URL}")
                            raise CheckApiRecognitionError(f'HTTP Error {response.status}. Ответ API: {error_text}')

                        api_json = await response.json()
                        response_code = api_json.get('code')
                        
                        if response_code == 1:
                            check_data = api_json['data']['json']
                            
                            retailer = check_data.get('user', 'Неизвестный Продавец')
                            total_sum_kopecks = check_data.get('totalSum', 0)
                            amount = round(total_sum_kopecks / 100, 2)
                            
                            # Проверяем, что сумма положительная и не превышает разумный лимит
                            if amount <= 0:
                                raise CheckApiRecognitionError('Сумма в чеке должна быть положительной.')
                            if amount > 100000:  # Ограничение максимальной суммы
                                raise CheckApiRecognitionError('Сумма в чеке слишком велика.')

                            items = check_data.get('items', [])
                            item_names = [item['name'] for item in items]
                            items_list_str = " | ".join(item_names)
                            
                            # Определение типа оплаты
                            if check_data.get('ecashTotalSum', 0) > 0:
                                payment_info = "Карта/Электронный платеж"
                            elif check_data.get('cashTotalSum', 0) > 0:
                                 payment_info = "Наличные"
                            else:
                                payment_info = "Неизвестно"
                                
                            search_string = retailer.lower() + " " + items_list_str.lower()
                            auto_category = map_category_by_keywords(search_string)

                            # Создаем и возвращаем Pydantic модель
                            return CheckData(
                                category=auto_category,
                                amount=amount,
                                comment=items_list_str,
                                retailer_name=retailer,
                                items_list=items_list_str,
                                payment_info=payment_info,
                                check_datetime_str=check_data.get('dateTime')
                            )

                        else:
                            error_map = {0: "чек некорректен", 2: "данные чека пока не получены", 3: "превышено кол-во запросов", 4: "ожидание перед повторным запросом", 5: "прочее (данные не получены)"}
                            error_detail = error_map.get(response_code, f"Неизвестный код {response_code}")
                            raise CheckApiRecognitionError(f'Proverkacheka API: {error_detail}')

            except asyncio.TimeoutError:
                logger.error(f"❌ Check API request timed out after {CHECK_API_TIMEOUT} seconds. URL: {CHECK_API_URL}")
                raise CheckApiTimeout(f'Превышено время ожидания ответа от Check API ({CHECK_API_TIMEOUT} сек).')
            except CheckApiRecognitionError:
                raise # Перебрасываем нашу же ошибку
            except aiohttp.ClientConnectorError as e:
                logger.error(f"❌ Ошибка подключения к API: {e}. URL: {CHECK_API_URL}")
                
                # Используем экспоненциальную задержку с jitter
                import random
                base_delay = 5
                jitter = random.uniform(0, base_delay * 0.1)
                wait_time = base_delay * (2 ** retry_count) + jitter
                
                logger.info(f"⚠️ Ошибка подключения. Повторная попытка через {wait_time:.2f} секунд...")
                await asyncio.sleep(wait_time)
                retry_count += 1
                continue  # Повторная попытка
            except aiohttp.ClientOSError as e:
                logger.error(f"❌ Сетевая ошибка при обращении к API: {e}. URL: {CHECK_API_URL}")
                
                # Используем экспоненциальную задержку с jitter
                import random
                base_delay = 5
                jitter = random.uniform(0, base_delay * 0.1)
                wait_time = base_delay * (2 ** retry_count) + jitter
                
                logger.info(f"⚠️ Сетевая ошибка. Повторная попытка через {wait_time:.2f} секунд...")
                await asyncio.sleep(wait_time)
                retry_count += 1
                continue  # Повторная попытка
            except asyncio.CancelledError:
                # Обработка отмены операции (например, при остановке приложения)
                logger.info(f"⚠️ Запрос к API был отменен (возможно, приложение завершает работу). URL: {CHECK_API_URL}")
                raise  # Передаем дальше CancelledError, чтобы корректно обработать отмену
            except Exception as e:
                logger.error(f"❌ Критическая ошибка соединения/обработки API: {e}. URL: {CHECK_API_URL}")
                import traceback
                logger.debug(f"Стек вызова: {traceback.format_exc()}")
                raise CheckApiRecognitionError(f'Критическая ошибка: {e}')
        finally:
            # Закрываем сеанс только если создали его сами
            if own_session:
                await session_to_use.close()
    
    # Если все попытки исчерпаны
    raise CheckApiRecognitionError(f'Не удалось выполнить запрос к API после {max_retries} попыток')