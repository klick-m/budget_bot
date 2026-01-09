from typing import Optional, Dict, Any
from models.user import User
from services.repository import UserRepository


class AuthService:
    """
    Сервис для работы с пользователями и авторизацией в системе Budget Bot.
    Обеспечивает CRUD операции для пользователей с хранением данных в SQLite базе данных.
    """
    
    
    def __init__(self, user_repo: UserRepository):
        self.user_repo = user_repo

    async def get_user_by_telegram_id(self, telegram_id: int) -> Optional[User]:
        """
        Получить пользователя по его Telegram ID
        """
        return await self.user_repo.get_user_by_telegram_id(telegram_id)

    async def get_user_by_id(self, user_id: int) -> Optional[User]:
        """
        Получить пользователя по его ID в базе данных
        """
        return await self.user_repo.get_user_by_id(user_id)

    async def create_user(self, telegram_id: int, username: Optional[str] = None,
                         role: str = "user", monthly_limit: float = 0.0) -> User:
        """
        Создать нового пользователя
        """
        # Проверяем, существует ли уже пользователь
        existing_user = await self.get_user_by_telegram_id(telegram_id)
        if existing_user:
            raise ValueError(f"Пользователь с telegram_id {telegram_id} уже существует")
        
        # Подготовим данные для создания пользователя
        user_data = {
            'telegram_id': telegram_id,
            'username': username,
            'role': role,
            'monthly_limit': monthly_limit
        }
        
        # Создаем пользователя через репозиторий
        return await self.user_repo.create_user(user_data)

    async def delete_user(self, telegram_id: int) -> bool:
        """
        Удалить пользователя по его Telegram ID
        Сначала получаем пользователя по telegram_id, чтобы получить его id в базе данных
        """
        user = await self.get_user_by_telegram_id(telegram_id)
        if user:
            return await self.user_repo.delete_user(user.id)
        return False

    async def update_user_role(self, telegram_id: int, role: str) -> bool:
        """
        Обновить роль пользователя
        """
        user = await self.get_user_by_telegram_id(telegram_id)
        if user:
            fields = {'role': role}
            return await self.user_repo.update_user_fields(user.id, fields)
        return False

    async def update_monthly_limit(self, telegram_id: int, monthly_limit: float) -> bool:
        """
        Обновить месячный лимит пользователя
        """
        user = await self.get_user_by_telegram_id(telegram_id)
        if user:
            fields = {'monthly_limit': monthly_limit}
            return await self.user_repo.update_user_fields(user.id, fields)
        return False

    async def get_all_users(self) -> list[User]:
        """
        Получить список всех пользователей
        """
        return await self.user_repo.get_all_users()

    async def get_user_count(self) -> int:
        """
        Получить количество пользователей в системе
        """
        all_users = await self.get_all_users()
        return len(all_users)

    async def update_user_username(self, telegram_id: int, username: str) -> bool:
        """
        Обновить имя пользователя
        """
        user = await self.get_user_by_telegram_id(telegram_id)
        if user:
            fields = {'username': username}
            return await self.user_repo.update_user_fields(user.id, fields)
        return False

    async def update_user_profile(self, telegram_id: int, username: Optional[str] = None,
                                role: Optional[str] = None, monthly_limit: Optional[float] = None) -> bool:
        """
        Обновить профиль пользователя (несколько полей за раз)
        """
        user = await self.get_user_by_telegram_id(telegram_id)
        if not user:
            return False

        # Подготовим словарь полей для обновления
        fields = {}
        if username is not None:
            fields['username'] = username
        if role is not None:
            fields['role'] = role
        if monthly_limit is not None:
            fields['monthly_limit'] = monthly_limit

        if not fields:
            return False

        # Обновляем пользователя через репозиторий
        return await self.user_repo.update_user_fields(user.id, fields)