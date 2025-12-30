
import pytest
import os
import pytest_asyncio
from services.repository import TransactionRepository

DB_PATH = "test_transactions.db"

@pytest.fixture
async def repository():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    
    repo = TransactionRepository(db_path=DB_PATH)
    await repo.init_db()
    yield repo
    await repo.close()
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)

@pytest.mark.asyncio
async def test_schema_migration(repository):
    """Test that the schema has the new 'type' column."""
    async with repository._get_connection() as db:
        cursor = await db.execute("PRAGMA table_info(transactions)")
        columns = await cursor.fetchall()
        column_names = [column[1] for column in columns]
        
        assert 'type' in column_names, "Column 'type' missing in transactions table"
        assert 'username' in column_names, "Column 'username' missing in transactions table"

@pytest.mark.asyncio
async def test_add_and_get_transaction(repository):
    """Test adding and retrieving a transaction with the new fields."""
    user_id = 12345
    username = "test_user"
    amount = 500.0
    category = "Food"
    comment = "Lunch"
    t_type = "Расход"
    
    # Add transaction
    t_id = await repository.add_transaction(
        user_id=user_id,
        username=username,
        amount=amount,
        category=category,
        transaction_type=t_type,
        comment=comment
    )
    
    assert t_id is not None
    
    # Get unsynced
    unsynced = await repository.get_unsynced()
    assert len(unsynced) == 1
    t = unsynced[0]
    
    assert t['user_id'] == user_id
    assert t['username'] == username
    assert t['amount'] == amount
    assert t['category'] == category
    assert t['type'] == t_type
    assert t['comment'] == comment
    assert t['is_synced'] == 0

@pytest.mark.asyncio
async def test_income_transaction(repository):
    """Test adding an INCOME transaction."""
    t_id = await repository.add_transaction(
        user_id=999,
        username="earner",
        amount=10000.0,
        category="Salary",
        transaction_type="Доход",
        comment="Bonus"
    )
    
    unsynced = await repository.get_unsynced()
    t = unsynced[0]
    assert t['type'] == "Доход"
