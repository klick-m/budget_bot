from pydantic import BaseModel
from typing import Optional


class User(BaseModel):
    """
    Модель пользователя для системы авторизации
    """
    id: Optional[int] = None
    telegram_id: int
    username: Optional[str] = None
    role: str = "user"  # 'admin' или 'user'