# models/transaction.py
import traceback
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, Literal # <--- Добавлен Literal

from config import logger

class CheckData(BaseModel):
    """Модель данных, извлекаемых из API чека."""
    # Используем Literal для указания, что значение может быть только "Расход"
    type: Literal["Расход"] = Field('Расход')
    
    category: str
    amount: float = Field(..., gt=0, le=100000)  # Ограничение максимальной суммы
    comment: str
    retailer_name: str = ''
    items_list: str = ''
    payment_info: str = ''
    check_datetime_str: Optional[str] = None # Дата в сыром виде из API

    @property
    def transaction_datetime(self) -> datetime:
        """Парсит дату чека, или возвращает текущее время, если парсинг не удался."""
        if self.check_datetime_str:
            try:
                # Пытаемся парсить с секундами (стандарт FNS)
                try:
                    return datetime.strptime(self.check_datetime_str, "%Y-%m-%dT%H:%M:%S")
                except ValueError:
                    # Если секунд нет, парсим без них
                    return datetime.strptime(self.check_datetime_str, "%Y-%m-%dT%H:%M")
            except ValueError as e:
                logger.warning(f"Ошибка парсинга даты транзакции '{self.check_datetime_str}': {e}")
                logger.debug(f"Стек вызова: {traceback.format_exc()}")

        return datetime.now()

class TransactionData(BaseModel):
    """Полная модель данных для записи в Google Sheets."""
    type: str
    category: str
    amount: float
    comment: str = ""
    username: str
    retailer_name: str = ""
    items_list: str = ""
    payment_info: str = ""
    transaction_dt: datetime = Field(default_factory=datetime.now)