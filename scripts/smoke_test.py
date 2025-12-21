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
        print("🔍 [1/4] Checking imports...")
        from main import dp, bot
        print("✅ Imports passed.")
        
        # 2. Проверка конфига
        print("🔍 [2/4] Checking configuration...")
        from config import BOT_TOKEN
        if not BOT_TOKEN: raise ValueError("BOT_TOKEN is missing")
        print("✅ Configuration passed.")
        
        # 3. Инициализация БД
        print("🔍 [3/4] Checking DB initialization...")
        from services.repository import TransactionRepository
        repo = TransactionRepository()
        print("✅ Repository initialized.")

        # 4. Инициализация Сервисов (ПРОВЕРКА НА БАГ)
        print("🔍 [4/4] Checking Services Instantiation...")
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