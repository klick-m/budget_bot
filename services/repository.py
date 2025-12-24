import aiosqlite
from typing import List, Optional
import sqlite3
from contextlib import asynccontextmanager


class TransactionRepository:
    def __init__(self, db_path: str = "transactions.db"):
        self.db_path = db_path

    async def init_db(self):
        """Initialize the database and create the transactions table if it doesn't exist."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("PRAGMA journal_mode=WAL;")
            await db.execute("PRAGMA synchronous=NORMAL;")
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS transactions (
                    id INTEGER PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    amount REAL NOT NULL,
                    category TEXT NOT NULL,
                    comment TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    is_synced BOOLEAN DEFAULT 0
                )
                """
            )
            await db.commit()

    @asynccontextmanager
    async def _get_connection(self):
        """Context manager to get database connection."""
        async with aiosqlite.connect(self.db_path) as db:
            yield db

    async def add_transaction(self, user_id: int, amount: float, category: str, comment: Optional[str] = None) -> int:
        """Add a new transaction and return its ID."""
        async with self._get_connection() as db:
            cursor = await db.execute(
                """
                INSERT INTO transactions (user_id, amount, category, comment)
                VALUES (?, ?, ?, ?)
                """,
                (user_id, amount, category, comment)
            )
            transaction_id = cursor.lastrowid
            await db.commit()
            return transaction_id

    async def get_unsynced(self) -> List[dict]:
        """Get all unsynced transactions."""
        async with self._get_connection() as db:
            cursor = await db.execute(
                """
                SELECT id, user_id, amount, category, comment, created_at, is_synced
                FROM transactions
                WHERE is_synced = 0
                ORDER BY created_at
                """
            )
            rows = await cursor.fetchall()
            columns = [column[0] for column in cursor.description]
            return [dict(zip(columns, row)) for row in rows]

    async def mark_as_synced(self, transaction_id: int) -> bool:
        """Mark a transaction as synced. Returns True if the transaction was found and updated."""
        async with self._get_connection() as db:
            cursor = await db.execute(
                """
                UPDATE transactions
                SET is_synced = 1
                WHERE id = ?
                """,
                (transaction_id,)
            )
            await db.commit()
            
            # Check if any row was actually updated
            return cursor.rowcount > 0