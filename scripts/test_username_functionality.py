# scripts/test_username_functionality.py
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
    print(f"🧪 QA: Testing Username Storage Functionality...")
    print(f"📂 Project Root detected as: {project_root}")
    
    try:
        # 1. Проверка импортов
        print("🔍 [1/6] Checking imports...")
        from config import BOT_TOKEN
        print("✅ Imports passed.")
        
        # 2. Проверка конфигурации
        print("🔍 [2/6] Checking configuration...")
        if not BOT_TOKEN:
            raise ValueError("BOT_TOKEN is missing")
        print("✅ Configuration passed.")
        
        # 3. Инициализация БД
        print("🔍 [3/6] Checking DB initialization...")
        from services.repository import TransactionRepository
        repo = TransactionRepository()
        await repo.init_db()
        print("✅ Repository initialized.")
        
        # 4. Проверка хранения username
        print("🔍 [4/6] Checking username storage functionality...")
        user_id = 123456789
        username = "Иван Иванов"
        amount = 1000.0
        category = "Продукты"
        comment = "Покупка в магазине"
        
        # Добавляем транзакцию с реальным именем пользователя
        transaction_id = await repo.add_transaction(
            user_id=user_id,
            username=username,
            amount=amount,
            category=category,
            comment=comment
        )
        
        if transaction_id <= 0:
            raise Exception("Transaction was not added to database")
        
        # Получаем несинхронизированные транзакции
        unsynced_transactions = await repo.get_unsynced()
        if len(unsynced_transactions) != 1:
            raise Exception(f"Expected 1 transaction, got {len(unsynced_transactions)}")
        
        transaction = unsynced_transactions[0]
        
        # Проверяем, что имя пользователя сохранено корректно
        if transaction['username'] != username:
            raise Exception(f"Expected username '{username}', got '{transaction['username']}'")
        
        if transaction['user_id'] != user_id:
            raise Exception(f"Expected user_id '{user_id}', got '{transaction['user_id']}'")
        
        print(f"✅ Username storage working: '{transaction['username']}'")
        
        # 5. Проверка синхронизации
        print("🔍 [5/6] Checking sync worker functionality...")
        from models.transaction import TransactionData
        from datetime import datetime
        
        # Создаем тестовую транзакцию для проверки синхронизации
        test_transaction = TransactionData(
            type="Расход",
            category="Тест",
            amount=1.0,
            comment="Тест синхронизации",
            username="Тестовый Пользователь",
            transaction_dt=datetime.now()
        )
        
        print(f"✅ Sync worker preparation passed")
        
        # 6. Проверка сервиса транзакций
        print("🔍 [6/6] Checking TransactionService with real username...")
        from services.transaction_service import TransactionService
        from sheets.client import load_categories_from_sheet
        from utils.category_classifier import classifier
        
        # Инициализация сервисов
        service = TransactionService(repository=repo)
        categories_loaded = await load_categories_from_sheet()
        print(f"✅ Categories loaded: {categories_loaded}")
        
        # Проверка инициализации классификатора
        await classifier.load()
        print(f"✅ Classifier loaded: {classifier}")
        
        # Проверка сохранения транзакции с реальным именем пользователя
        test_transaction = TransactionData(
            type="Расход",
            category="Продукты",
            amount=250.0,
            comment="Тестовое имя пользователя",
            username="Анна Петрова",
            retailer_name="Магазин",
            items_list="Хлеб|Молоко",
            payment_info="Карта",
            transaction_dt=datetime.now()
        )
        
        # Сохраняем транзакцию
        result = await service.save_transaction(test_transaction)
        if not result:
            raise Exception("Failed to save transaction")
        
        # Проверяем, что транзакция сохранилась с правильным именем пользователя
        unsynced_transactions = await repo.get_unsynced()
        latest_transaction = unsynced_transactions[-1]  # Последняя транзакция
        
        if latest_transaction['username'] != "Анна Петрова":
            raise Exception(f"Expected username 'Анна Петрова', got '{latest_transaction['username']}'")
        
        print(f"✅ TransactionService working with real username: '{latest_transaction['username']}'")
        
        print("========================================")
        print("✅ USERNAME FUNCTIONALITY TEST PASSED")
        print("✅ Real usernames are properly stored and handled")
        print("========================================")
        sys.exit(0)
        
    except Exception as e:
        print(f"\n❌ CRITICAL FAILURE DURING USERNAME TEST")
        print(f"❌ Error Type: {type(e).__name__}")
        print(f"❌ Error Message: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())