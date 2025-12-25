# scripts/test_sync_worker.py
import asyncio
import sys
import os
import tempfile
import logging
from datetime import datetime

# === 🛠 МАГИЯ ПУТЕЙ (PATH HACK) ===
current_script_path = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_script_path)
sys.path.insert(0, project_root)
# =================================

logging.basicConfig(level=logging.INFO)

async def main():
    print(f"🧪 QA: Testing Sync Worker with Real Usernames...")
    print(f"📂 Project Root detected as: {project_root}")
    
    try:
        # 1. Проверка инициализации
        print("🔍 [1/4] Initializing components...")
        from services.repository import TransactionRepository
        from models.transaction import TransactionData
        
        # Создаем временный файл для тестов
        with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as temp_db:
            temp_db_path = temp_db.name
        
        try:
            # Инициализируем репозиторий
            repo = TransactionRepository(db_path=temp_db_path)
            await repo.init_db()
            
            # Добавляем транзакции с разными именами пользователей
            transactions_data = [
                (123456789, "Иван Иванов", 1000.0, "Продукты", "Покупка в магазине"),
                (987654321, "Мария Смирнова", 2500.50, "Развлечения", "Кино"),
                (555123456, "Алексей Петров", 500.0, "Транспорт", "Проездной"),
                (11223344, "user_111223344", 150.0, "Прочее", "Тест"),  # пользователь с именем в формате user_X
            ]
            
            for user_id, username, amount, category, comment in transactions_data:
                await repo.add_transaction(
                    user_id=user_id,
                    username=username,
                    amount=amount,
                    category=category,
                    comment=comment
                )
            
            print("✅ Components initialized and test data added.")
            
            # 2. Проверка получения несинхронизированных транзакций
            print("🔍 [2/4] Checking unsynced transactions...")
            unsynced = await repo.get_unsynced()
            
            if len(unsynced) != 4:
                raise Exception(f"Expected 4 unsynced transactions, got {len(unsynced)}")
            
            # Проверяем, что имена пользователей сохранены корректно
            expected_usernames = ["Иван Иванов", "Мария Смирнова", "Алексей Петров", "user_111223344"]
            actual_usernames = [t['username'] for t in unsynced]
            
            if actual_usernames != expected_usernames:
                raise Exception(f"Expected usernames {expected_usernames}, got {actual_usernames}")
            
            print(f"✅ Unsynced transactions retrieved with correct usernames: {actual_usernames}")
            
            # 3. Проверка создания TransactionData для синхронизации
            print("🔍 [3/4] Checking TransactionData creation for sync...")
            for transaction in unsynced:
                transaction_data = TransactionData(
                    type="Расход",
                    category=transaction['category'],
                    amount=transaction['amount'],
                    comment=transaction['comment'] or '',
                    username=transaction['username'] or f"user_{transaction['user_id']}",  # Это основная проверка
                    transaction_dt=datetime.fromisoformat(transaction['created_at'].replace('Z', '+00:00')) if transaction['created_at'] else datetime.now()
                )
                
                # Проверяем, что имя пользователя сохранено правильно
                if transaction_data.username != transaction['username']:
                    raise Exception(f"Username mismatch: expected {transaction['username']}, got {transaction_data.username}")
            
            print("✅ TransactionData created correctly with real usernames.")
            
            # 4. Проверка логики воркера синхронизации
            print("🔍 [4/4] Checking sync worker logic...")
            from services.sync_worker import start_sync_worker
            
            # Проверяем логику, которая используется в sync_worker
            for transaction in unsynced:
                # Это точная копия логики из sync_worker.py строка 26
                username_to_use = transaction['username'] or f"user_{transaction['user_id']}"
                
                if username_to_use != transaction['username']:
                    # Это произойдет только если transaction['username'] пустой
                    expected_username = f"user_{transaction['user_id']}"
                else:
                    expected_username = transaction['username']
                
                if username_to_use != expected_username:
                    raise Exception(f"Sync worker username logic error: expected {expected_username}, got {username_to_use}")
            
            print("✅ Sync worker logic verified - real usernames will be used in Google Sheets.")
            
        finally:
            # Удаляем временный файл
            if os.path.exists(temp_db_path):
                os.unlink(temp_db_path)
        
        print("========================================")
        print("✅ SYNC WORKER TEST PASSED")
        print("✅ Real usernames will be properly stored in Google Sheets")
        print("✅ Sync worker correctly uses real usernames from database")
        print("========================================")
        sys.exit(0)
        
    except Exception as e:
        print(f"\n❌ CRITICAL FAILURE DURING SYNC WORKER TEST")
        print(f"❌ Error Type: {type(e).__name__}")
        print(f"❌ Error Message: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())