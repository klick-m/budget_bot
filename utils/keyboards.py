# utils/keyboards.py
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

def get_main_keyboard() -> ReplyKeyboardMarkup:
    """Возвращает основную ReplyKeyboardMarkup."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="💸 Добавить транзакцию")],
            [KeyboardButton(text="🧪 Проверить Sheets")]
        ],
        resize_keyboard=True,
        one_time_keyboard=False
    )

# Можно добавить другие функции для генерации Inline-клавиатур, если понадобится