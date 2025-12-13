# config.py
import os
import logging
from dotenv import load_dotenv

# Инициализация логгера с правильной кодировкой UTF-8
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Устанавливаем обработчик с явной кодировкой UTF-8 для Windows
import sys
import io

# Проверяем, является ли stdout консолью Windows
if sys.stdout.encoding != 'utf-8':
    # Если нет, то устанавливаем кодировку UTF-8 для вывода
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    else:
        # Альтернативный способ для старых версий Python
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Также устанавливаем кодировку для stderr
if sys.stderr.encoding != 'utf-8':
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8')
    else:
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# Устанавливаем переменную окружения для правильной обработки UTF-8 в Windows
os.environ['PYTHONIOENCODING'] = 'utf-8'

load_dotenv()

# --- Настройки Telegram и доступа ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
ALLOWED_USER_IDS_RAW = os.getenv("ALLOWED_USER_IDS", "")
ALLOWED_USER_IDS = [int(i.strip()) for i in ALLOWED_USER_IDS_RAW.split(',') if i.strip().isdigit()]

# --- Настройки Google Sheets ---
GOOGLE_SHEET_URL = os.getenv("GOOGLE_SHEET_URL")
SERVICE_KEY = os.getenv("SERVICE_ACCOUNT_FILE", "service_account.json") 
DATA_SHEET_NAME = os.getenv("DATA_SHEET_NAME", "RawData")
CATEGORIES_SHEET_NAME = os.getenv("CATEGORIES_SHEET_NAME", "Categories") 

# --- Настройки API Чеков ---
CHECK_API_TOKEN = os.getenv("CHECK_API_TOKEN") 
CHECK_API_URL = "https://proverkacheka.com/api/v1/check/get" 
CHECK_API_TIMEOUT = 25 

# --- Тайм-ауты и ограничения ---
SHEET_WRITE_TIMEOUT = 15  # Таймаут для операций с Google Sheets

# --- Настройки Keyword Dictionary ---
KEYWORDS_SPREADSHEET_ID = os.getenv("KEYWORDS_SPREADSHEET_ID", GOOGLE_SHEET_URL)
KEYWORDS_SHEET_NAME = os.getenv("KEYWORDS_SHEET_NAME", "Keywords")

# --- ХРАНИЛИЩЕ КАТЕГОРИЙ (замена глобальных переменных) ---
class CategoryStorage:
    def __init__(self):
        self.expense = []
        self.income = []
        self.keywords = {}
        self.last_loaded = None

# Единственный экземпляр для доступа ко всем категориям
CATEGORY_STORAGE = CategoryStorage()


# Проверка базовой конфигурации
if not BOT_TOKEN or not GOOGLE_SHEET_URL:
    logger.error("❌ КРИТИЧЕСКАЯ ОШИБКА: BOT_TOKEN или GOOGLE_SHEET_URL не найдены в .env.")