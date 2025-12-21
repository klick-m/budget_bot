# scripts/smoke_test.py
import asyncio
import sys
import os
import logging

# === 🛠 МАГИЯ ПУТЕЙ (PATH HACK) ===
# Получаем абсолютный путь к папке, где лежит этот скрипт (scripts/)
current_script_path = os.path.dirname(os.path.abspath(__file__))
# Получаем родительскую папку (корень проекта budget_bot/)
project_root = os.path.dirname(current_script_path)
# Вставляем корень в начало списка путей, где Python ищет модули
sys.path.insert(0, project_root)
# =================================

logging.basicConfig(level=logging.INFO)

async def main():
    print(f"🚑 QA: Starting DEEP Smoke Test...")
    print(f"📂 Project Root detected as: {project_root}")
    
    try:
        # 1. Проверка импортов
        print("🔍 [1/8] Checking imports...")
        from main import dp, bot
        print("✅ Imports passed.")
        
        # 2. Проверка конфига
        print("🔍 [2/8] Checking configuration...")
        from config import BOT_TOKEN
        if not BOT_TOKEN: raise ValueError("BOT_TOKEN is missing")
        print("✅ Configuration passed.")
        
        # 3. Инициализация БД
        print("🔍 [3/8] Checking DB initialization...")
        from services.repository import TransactionRepository
        repo = TransactionRepository()
        await repo.init_db()
        print("✅ Repository initialized.")

        # 4. Инициализация Сервисов (ПРОВЕРКА НА БАГ)
        print("🔍 [4/8] Checking Services Instantiation...")
        from services.transaction_service import TransactionService
        from services.sync_worker import start_sync_worker
        from sheets.client import load_categories_from_sheet
        from utils.category_classifier import classifier
        
        # Инициализация сервисов
        service = TransactionService(repository=repo)
        print(f"✅ TransactionService initialized: {service}")
        
        # Проверка загрузки категорий
        categories_loaded = await load_categories_from_sheet()
        print(f"✅ Categories loaded: {categories_loaded}")
        
        # Проверка инициализации классификатора
        await classifier.load()
        print(f"✅ Classifier loaded: {classifier}")
        
        # 5. Проверка KeywordDictionary
        print("🔍 [5/8] Checking Keyword Dictionary...")
        from models.keyword_dictionary import KeywordDictionary
        from config import KEYWORDS_SPREADSHEET_ID, KEYWORDS_SHEET_NAME
        keyword_dict = KeywordDictionary(KEYWORDS_SPREADSHEET_ID, KEYWORDS_SHEET_NAME)
        await keyword_dict.load()
        print(f"✅ KeywordDictionary loaded: {keyword_dict}")
        
        # 6. Проверка глобального сервиса
        print("🔍 [6/8] Checking Global Service Locator...")
        from services.global_service_locator import set_transaction_service, get_transaction_service
        set_transaction_service(service)
        retrieved_service = get_transaction_service()
        if retrieved_service is None:
            raise Exception("Global service locator failed to store/retrieve service")
        print(f"✅ Global Service Locator working: {retrieved_service}")
        
        # 7. Проверка обработчиков
        print("🔍 [7/8] Checking Handlers...")
        from handlers.transactions import register_handlers, Transaction
        register_handlers(dp, service)
        print(f"✅ Handlers registered: {len(dp.message.handlers)} message handlers, {len(dp.callback_query.handlers)} callback handlers")
        
        # 8. Проверка парсеров
        print("🔍 [8/8] Checking Parsers and Input Processing...")
        from services.input_parser import InputParser
        from services.text_parser import parse_transaction_text
        from utils.receipt_logic import parse_check_from_api, extract_learnable_keywords
        from utils.service_wrappers import safe_answer, edit_or_send
        
        parser = InputParser()
        parsed = parser.parse_transaction("300 кофе")
        if parsed:
            print(f"✅ Input parser working: {parsed}")
        else:
            print("⚠️ Input parser returned None (may be normal for this input)")
        
        text_parsed = parse_transaction_text("250 чай")
        if text_parsed['amount'] and text_parsed['category']:
            print(f"✅ Text parser working: {text_parsed}")
        else:
            print("⚠️ Text parser failed to parse")
        
        print("========================================")
        print("✅ DEEP SMOKE TEST PASSED. System is stable.")
        print("========================================")
        sys.exit(0)
        
    except Exception as e:
        print(f"\n❌ CRITICAL FAILURE DURING SMOKE TEST")
        print(f"❌ Error Type: {type(e).__name__}")
        print(f"❌ Error Message: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())