
import asyncio
import os
import aiosqlite
from services.repository import TransactionRepository

async def verify():
    db_path = "verify_transactions.db"
    if os.path.exists(db_path):
        os.remove(db_path)
    
    print(f"--- Initializing repository at {db_path} ---")
    repo = TransactionRepository(db_path=db_path)
    await repo.init_db()
    
    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute("PRAGMA table_info(transactions)")
        columns = await cursor.fetchall()
        column_names = [column[1] for column in columns]
        print(f"Columns in table: {column_names}")
        
        if 'type' in column_names and 'username' in column_names:
            print("✅ Schema verification: SUCCESS")
        else:
            print("❌ Schema verification: FAILED")
            return

    print("--- Testing add_transaction ---")
    try:
        t_id = await repo.add_transaction(
            user_id=123,
            username="testuser",
            amount=100.5,
            category="Test",
            transaction_type="Доход",
            comment="Test comment"
        )
        print(f"Transaction added with ID: {t_id}")
        
        unsynced = await repo.get_unsynced()
        if len(unsynced) == 1 and unsynced[0]['type'] == "Доход":
            print("✅ Data storage: SUCCESS")
        else:
            print(f"❌ Data storage: FAILED. Received: {unsynced}")
    except Exception as e:
        print(f"❌ Error during transaction test: {e}")
    finally:
        await repo.close()
        if os.path.exists(db_path):
            os.remove(db_path)

if __name__ == "__main__":
    asyncio.run(verify())
