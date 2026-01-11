import aiosqlite
from typing import List, Optional
import sqlite3
from contextlib import asynccontextmanager

from models.user import User
from config import logger


class UserRepository:
    def __init__(self, db_path: str = "transactions.db"):
        self.db_path = db_path

    async def init_db(self):
        """Initialize the database and create the users table if it doesn't exist."""
        async with aiosqlite.connect(self.db_path) as db:
            # Создаем таблицу пользователей, если она не существует
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    telegram_id INTEGER UNIQUE NOT NULL,
                    username TEXT,
                    role TEXT DEFAULT 'user'
                )
                """
            )
            await db.commit()

    @asynccontextmanager
    async def _get_connection(self):
        """Context manager to get database connection."""
        async with aiosqlite.connect(self.db_path) as db:
            yield db

    async def get_user_by_id(self, user_id: int) -> Optional[User]:
        """Get user by database ID."""
        async with self._get_connection() as db:
            cursor = await db.execute(
                """
                SELECT id, telegram_id, username, role
                FROM users
                WHERE id = ?
                """,
                (user_id,)
            )
            row = await cursor.fetchone()
            if row:
                columns = [column[0] for column in cursor.description]
                user_data = dict(zip(columns, row))
                return User(**user_data)
            return None

    async def create_user(self, user_data: dict) -> User:
        """Create a new user."""
        telegram_id = user_data['telegram_id']
        username = user_data.get('username')
        role = user_data.get('role', 'user')

        async with self._get_connection() as db:
            cursor = await db.execute(
                """
                INSERT INTO users (telegram_id, username, role)
                VALUES (?, ?, ?)
                """,
                (telegram_id, username, role)
            )
            user_id = cursor.lastrowid
            await db.commit()
        
        return User(
            id=user_id,
            telegram_id=telegram_id,
            username=username,
            role=role
        )

    async def update_user_fields(self, user_id: int, fields: dict) -> bool:
        """Update user fields by user ID."""
        if not fields:
            return False

        set_clause = ", ".join([f"{field} = ?" for field in fields.keys()])
        values = list(fields.values()) + [user_id]

        async with self._get_connection() as db:
            cursor = await db.execute(
                "UPDATE users SET {} WHERE id = ?".format(set_clause),
                values
            )
            await db.commit()
            return cursor.rowcount > 0

    async def delete_user(self, user_id: int) -> bool:
        """Delete user by database ID."""
        async with self._get_connection() as db:
            cursor = await db.execute(
                """
                DELETE FROM users WHERE id = ?
                """,
                (user_id,)
            )
            await db.commit()
            return cursor.rowcount > 0

    async def get_all_users(self) -> List[User]:
        """Get all users."""
        async with self._get_connection() as db:
            cursor = await db.execute(
                """
                SELECT id, telegram_id, username, role
                FROM users
                ORDER BY id
                """
            )
            rows = await cursor.fetchall()
            columns = [column[0] for column in cursor.description]
            users_data = [dict(zip(columns, row)) for row in rows]
            return [User(**user_data) for user_data in users_data]

    async def get_user_by_telegram_id(self, telegram_id: int) -> Optional[User]:
        """Get user by telegram_id. Returns user data if exists, None otherwise."""
        async with self._get_connection() as db:
            cursor = await db.execute(
                """
                SELECT id, telegram_id, username, role
                FROM users
                WHERE telegram_id = ?
                """,
                (telegram_id,)
            )
            row = await cursor.fetchone()
            if row:
                columns = [column[0] for column in cursor.description]
                user_data = dict(zip(columns, row))
                return User(**user_data)
            return None

    async def update_user_profile(self, user_id: int, username: Optional[str] = None,
                                role: Optional[str] = None) -> bool:
        """Update user profile (multiple fields at once)"""
        user = await self.get_user_by_id(user_id)
        if not user:
            return False

        # Prepare dictionary of fields to update
        fields = {}
        if username is not None:
            fields['username'] = username
        if role is not None:
            fields['role'] = role

        if not fields:
            return False

        return await self.update_user_fields(user_id, fields)

    async def close(self):
        """Close the database connection if it was opened."""
        pass  # В текущей реализации aiosqlite использует контекстные менеджеры, поэтому отдельное закрытие не требуется


class TransactionRepository(UserRepository):
    def __init__(self, db_path: str = "transactions.db"):
        super().__init__(db_path)
        self._connection = None

    async def init_db(self):
        """Initialize the database and create the transactions table if it doesn't exist."""
        # Сначала инициализируем родительскую базу данных (таблицу users)
        await super().init_db()
        
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("PRAGMA journal_mode=WAL;")
            await db.execute("PRAGMA synchronous=NORMAL;")
            
            # Создаем таблицу транзакций, если она не существует
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS transactions (
                    id INTEGER PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    username TEXT,
                    type TEXT DEFAULT 'Расход',
                    amount REAL NOT NULL,
                    category TEXT NOT NULL,
                    comment TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    is_synced BOOLEAN DEFAULT 0
                )
                """
            )
            
            # Проверяем структуру таблицы для миграций
            cursor = await db.execute("PRAGMA table_info(transactions)")
            columns = await cursor.fetchall()
            column_names = [column[1] for column in columns]
            
            # Миграция: добавляем username, если нет
            if 'username' not in column_names:
                await db.execute("ALTER TABLE transactions ADD COLUMN username TEXT")
                logger.info("Добавлен столбец username в таблицу transactions")

            # Миграция: добавляем type, если нет
            if 'type' not in column_names:
                await db.execute("ALTER TABLE transactions ADD COLUMN type TEXT DEFAULT 'Расход'")
                logger.info("Добавлен столбец type в таблицу transactions")
            
            await db.commit()

    @asynccontextmanager
    async def _get_connection(self):
        """Context manager to get database connection."""
        async with aiosqlite.connect(self.db_path) as db:
            yield db

    async def add_transaction(self, user_id: int, username: str, amount: float, category: str, transaction_type: str, comment: Optional[str] = None) -> int:
        """Add a new transaction and return its ID."""
        async with self._get_connection() as db:
            cursor = await db.execute(
                """
                INSERT INTO transactions (user_id, username, amount, category, type, comment)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (user_id, username, amount, category, transaction_type, comment)
            )
            transaction_id = cursor.lastrowid
            await db.commit()
            return transaction_id

    async def get_unsynced(self) -> List[dict]:
        """Get all unsynced transactions."""
        async with self._get_connection() as db:
            cursor = await db.execute(
                """
                SELECT id, user_id, username, type, amount, category, comment, created_at, is_synced
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

    async def delete_transaction_by_details(self, user_id: str, date: str, time: str, amount: float) -> bool:
        """Delete a transaction by user_id, date, time, and amount."""
        async with self._get_connection() as db:
            # Формат даты в SQLite может отличаться от формата в приложении,
            # поэтому ищем по user_id и amount, и дополнительно проверяем дату
            cursor = await db.execute(
                """
                DELETE FROM transactions
                WHERE user_id = ? AND amount = ? AND created_at LIKE ?
                """,
                (int(user_id), amount, f"{date}%")
            )
            await db.commit()
            
            # Check if any row was actually deleted
            return cursor.rowcount > 0

    async def close(self):
        """Close the database connection if it was opened."""
        pass  # В текущей реализации aiosqlite использует контекстные менеджеры, поэтому отдельное закрытие не требуется