# utils/keyboards.py
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters.callback_data import CallbackData


class HistoryCallbackData(CallbackData, prefix="history"):
    """Callback data для пагинации истории транзакций."""
    offset: int
    direction: str  # 'prev' или 'next'


def get_main_keyboard() -> ReplyKeyboardMarkup:
    """Возвращает основную ReplyKeyboardMarkup."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="💸 Добавить транзакцию")],
            [KeyboardButton(text="📜 История транзакций")],
            [KeyboardButton(text="🧪 Проверить Sheets")]
        ],
        resize_keyboard=True,
        one_time_keyboard=False
    )


def get_history_keyboard(offset: int, has_next: bool) -> InlineKeyboardMarkup:
    """Генерирует Inline-клавиатуру с кнопками пагинации для истории транзакций."""
    keyboard = []
    row = []
    
    # Кнопка "Назад", если смещение больше 0
    if offset > 0:
        prev_offset = max(0, offset - 5) # Предыдущее смещение (шаг 5)
        back_button = InlineKeyboardButton(
            text="<< Назад",
            callback_data=HistoryCallbackData(offset=prev_offset, direction="prev").pack()
        )
        row.append(back_button)
    
    # Кнопка "Вперед", если есть следующие транзакции
    if has_next:
        next_offset = offset + 5  # Следующее смещение (шаг 5)
        forward_button = InlineKeyboardButton(
            text="Вперед >>",
            callback_data=HistoryCallbackData(offset=next_offset, direction="next").pack()
        )
        if row: # Если уже есть кнопка "Назад", добавляем в тот же ряд
            row.append(forward_button)
        else:  # Иначе создаем новый ряд с кнопкой "Вперед"
            keyboard.append([forward_button])
    
    # Добавляем кнопки в клавиатуру
    if row:
        keyboard.append(row)
    
    # Добавляем кнопку "Закрыть" на отдельной строке
    close_button = [InlineKeyboardButton(text="❌ Закрыть", callback_data="close_history")]
    keyboard.append(close_button)
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)