from typing import Optional, Dict, Any
from models.user import User
from services.repository import TransactionRepository


class AuthService:
    """
    Сервис для работы с пользователями и авторизацией в системе Budget Bot.
    Обеспечивает CRUD операции для пользователей с хранением данных в SQLite базе данных.
    """
    
    
    def __init__(self, repo: TransactionRepository):
        self.repo = repo

    async def get_user_by_telegram_id(self, telegram_id: int) -> Optional[User]:
        """
        Получить пользователя по его Telegram ID
        """
        user_data = await self.repo.get_user_by_telegram_id(telegram_id)
        if user_data:
            return User(**user_data)
        return None

    async def get_user_by_id(self, user_id: int) -> Optional[User]:
        """
        Получить пользователя по его ID в базе данных
        """
        async with self.repo._get_connection() as db:
            cursor = await db.execute(
                """
                SELECT id, telegram_id, username, role, monthly_limit
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

    async def create_user(self, telegram_id: int, username: Optional[str] = None,
                         role: str = "user", monthly_limit: float = 0.0) -> User:
        """
        Создать нового пользователя
        """
        # Проверяем, существует ли уже пользователь
        existing_user = await self.get_user_by_telegram_id(telegram_id)
        if existing_user:
            raise ValueError(f"Пользователь с telegram_id {telegram_id} уже существует")
        
        # Вставляем пользователя в базу данных
        async with self.repo._get_connection() as db:
            cursor = await db.execute(
                """
                INSERT INTO users (telegram_id, username, role, monthly_limit)
                VALUES (?, ?, ?, ?)
                """,
                (telegram_id, username, role, monthly_limit)
            )
            user_id = cursor.lastrowid
            await db.commit()
        
        # Возвращаем созданного пользователя
        return User(
            id=user_id,
            telegram_id=telegram_id,
            username=username,
            role=role,
            monthly_limit=monthly_limit
        )

    async def delete_user(self, telegram_id: int) -> bool:
        """
        Удалить пользователя по его Telegram ID
        """
        async with self.repo._get_connection() as db:
            cursor = await db.execute(
                """
                DELETE FROM users WHERE telegram_id = ?
                """,
                (telegram_id,)
            )
            await db.commit()
            return cursor.rowcount > 0

    async def update_user_role(self, telegram_id: int, role: str) -> bool:
        """
        Обновить роль пользователя
        """
        async with self.repo._get_connection() as db:
            cursor = await db.execute(
                """
                UPDATE users
                SET role = ?
                WHERE telegram_id = ?
                """,
                (role, telegram_id)
            )
            await db.commit()
            return cursor.rowcount > 0

    async def update_monthly_limit(self, telegram_id: int, monthly_limit: float) -> bool:
        """
        Обновить месячный лимит пользователя
        """
        async with self.repo._get_connection() as db:
            cursor = await db.execute(
                """
                UPDATE users
                SET monthly_limit = ?
                WHERE telegram_id = ?
                """,
                (monthly_limit, telegram_id)
            )
            await db.commit()
            return cursor.rowcount > 0

    async def get_all_users(self) -> list[User]:
        """
        Получить список всех пользователей
        """
        async with self.repo._get_connection() as db:
            cursor = await db.execute(
                """
                SELECT id, telegram_id, username, role, monthly_limit
                FROM users
                ORDER BY id
                """
            )
            rows = await cursor.fetchall()
            columns = [column[0] for column in cursor.description]
            users_data = [dict(zip(columns, row)) for row in rows]
            return [User(**user_data) for user_data in users_data]

    async def get_user_count(self) -> int:
        """
        Получить количество пользователей в системе
        """
        async with self.repo._get_connection() as db:
            cursor = await db.execute("SELECT COUNT(*) FROM users")
            result = await cursor.fetchone()
            return result[0] if result else 0

    async def update_user_username(self, telegram_id: int, username: str) -> bool:
        """
        Обновить имя пользователя
        """
        async with self.repo._get_connection() as db:
            cursor = await db.execute(
                """
                UPDATE users
                SET username = ?
                WHERE telegram_id = ?
                """,
                (username, telegram_id)
            )
            await db.commit()
            return cursor.rowcount > 0

    async def update_user_profile(self, telegram_id: int, username: Optional[str] = None,
                                role: Optional[str] = None, monthly_limit: Optional[float] = None) -> bool:
        """
        Обновить профиль пользователя (несколько полей за раз)
        """
        update_fields = []
        params = []
        if username is not None:
            update_fields.append("username = ?")
            params.append(username)
        if role is not None:
            update_fields.append("role = ?")
            params.append(role)
        if monthly_limit is not None:
            update_fields.append("monthly_limit = ?")
            params.append(monthly_limit)

        if not update_fields:
            return False

        params.append(telegram_id)

        async with self.repo._get_connection() as db:
            cursor = await db.execute(
                f"""
                UPDATE users
                SET {', '.join(update_fields)}
                WHERE telegram_id = ?
                """,
                params
            )
            await db.commit()
            return cursor.rowcount > 0