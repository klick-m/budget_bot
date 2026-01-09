# utils/keyboards.py
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters.callback_data import CallbackData
from typing import Optional
from dataclasses import dataclass
from datetime import datetime
from config import CATEGORY_STORAGE


class HistoryCallbackData(CallbackData, prefix="history"):
    """Callback data для пагинации истории транзакций."""
    offset: int
    direction: str  # 'prev' или 'next'


@dataclass
class TransactionDraft:
    """Структура данных для черновика транзакции"""
    type: Optional[str] = None
    category: Optional[str] = None
    amount: Optional[float] = None
    comment: Optional[str] = ""
    retailer_name: Optional[str] = ""
    items_list: Optional[str] = ""
    payment_info: Optional[str] = ""
    transaction_dt: Optional[datetime] = None


def get_main_keyboard(is_admin: bool = False) -> ReplyKeyboardMarkup:
    """Возвращает основную ReplyKeyboardMarkup."""
    keyboard = [
        [KeyboardButton(text="💸 Добавить транзакцию")],
        [KeyboardButton(text="📜 История транзакций")],
        [KeyboardButton(text="📊 Отчет")]
    ]
    
    # Добавляем админские команды, если пользователь админ
    if is_admin:
        keyboard.insert(-1, [KeyboardButton(text="🛡️ Админ-панель")])  # Добавляем перед последней кнопкой
    
    # Добавляем кнопку проверки листов в самый низ
    keyboard.append([KeyboardButton(text="🧪 Проверить Sheets")])
    
    return ReplyKeyboardMarkup(
        keyboard=keyboard,
        resize_keyboard=True,
        one_time_keyboard=False
    )


# Удаляем устаревшую функцию get_history_keyboard
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
        else: # Иначе создаем новый ряд с кнопкой "Вперед"
            keyboard.append([forward_button])

    # Добавляем кнопки в клавиатуру
    if row:
        keyboard.append(row)

    # Добавляем кнопку "Закрыть" на отдельной строке
    close_button = [InlineKeyboardButton(text="❌ Закрыть", callback_data="close_history")]
    keyboard.append(close_button)

    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_transaction_type_keyboard() -> InlineKeyboardMarkup:
    """Генерирует Inline-клавиатуру для выбора типа транзакции (доход/расход)."""
    keyboard = [
        [InlineKeyboardButton(text="💸 Расход", callback_data="type_Расход")],
        [InlineKeyboardButton(text="💰 Доход", callback_data="type_Доход")]
    ]
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_categories_keyboard(transaction_type: str = "Расход") -> InlineKeyboardMarkup:
    """Генерирует Inline-клавиатуру с категориями для выбора."""
    category_list = CATEGORY_STORAGE.expense if transaction_type == "Расход" else CATEGORY_STORAGE.income
    
    buttons = [
        InlineKeyboardButton(text=cat, callback_data=f"cat_{cat}")
        for cat in category_list
    ]
    
    # Распределяем кнопки по строкам (по 2 в строке)
    keyboard = [buttons[i:i + 2] for i in range(0, len(buttons), 2)]
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_draft_inline_keyboard(draft: TransactionDraft) -> InlineKeyboardMarkup:
    """Создает inline-клавиатуру для редактирования черновика транзакции."""
    keyboard_buttons = []
    
    # Кнопки для редактирования полей
    if not draft.type:
        keyboard_buttons.append([InlineKeyboardButton(text="✏️ Выбрать тип", callback_data="edit_type")])
    else:
        keyboard_buttons.append([InlineKeyboardButton(text="✏️ Изменить тип", callback_data="edit_type")])
    
    if not draft.category:
        keyboard_buttons.append([InlineKeyboardButton(text="🏷️ Выбрать категорию", callback_data="edit_category_draft")])
    else:
        keyboard_buttons.append([InlineKeyboardButton(text="🏷️ Изменить категорию", callback_data="edit_category_draft")])
    
    if not draft.amount:
        keyboard_buttons.append([InlineKeyboardButton(text="💰 Ввести сумму", callback_data="edit_amount")])
    else:
        keyboard_buttons.append([InlineKeyboardButton(text="💰 Изменить сумму", callback_data="edit_amount")])
    
    keyboard_buttons.append([InlineKeyboardButton(text="💬 Изменить комментарий", callback_data="edit_comment")])
    
    # Кнопка завершения
    if draft.type and draft.category and draft.amount:
        keyboard_buttons.append([InlineKeyboardButton(text="✅ Подтвердить и записать", callback_data="confirm_draft")])
    else:
        keyboard_buttons.append([InlineKeyboardButton(text="❌ Отменить", callback_data="cancel_draft")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)


def get_dynamic_draft_keyboard(draft: TransactionDraft) -> InlineKeyboardMarkup:
    """Создает динамическую inline-клавиатуру для редактирования черновика транзакции,
    обновляющуюся в зависимости от состояния черновика."""
    keyboard_buttons = []
    
    # Кнопки для редактирования полей
    type_text = "✏️ Изменить тип" if draft.type else "✏️ Выбрать тип"
    category_text = "🏷️ Изменить категорию" if draft.category else "🏷️ Выбрать категорию"
    amount_text = "💰 Изменить сумму" if draft.amount else "💰 Ввести сумму"
    
    keyboard_buttons.append([InlineKeyboardButton(text=type_text, callback_data="edit_type")])
    keyboard_buttons.append([InlineKeyboardButton(text=category_text, callback_data="edit_category_draft")])
    keyboard_buttons.append([InlineKeyboardButton(text=amount_text, callback_data="edit_amount")])
    keyboard_buttons.append([InlineKeyboardButton(text="💬 Изменить комментарий", callback_data="edit_comment")])
    
    # Кнопка завершения - меняет текст в зависимости от заполненности полей
    if draft.type and draft.category and draft.amount:
        keyboard_buttons.append([InlineKeyboardButton(text="✅ Подтвердить и записать", callback_data="confirm_draft")])
    else:
        keyboard_buttons.append([InlineKeyboardButton(text="❌ Отменить", callback_data="cancel_draft")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)


def get_transaction_type_keyboard() -> InlineKeyboardMarkup:
    """Генерирует Inline-клавиатуру для выбора типа транзакции (доход/расход)."""
    keyboard = [
        [InlineKeyboardButton(text="💸 Расход", callback_data="type_Расход")],
        [InlineKeyboardButton(text="💰 Доход", callback_data="type_Доход")]
    ]
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_categories_keyboard(transaction_type: str = "Расход") -> InlineKeyboardMarkup:
    """Генерирует Inline-клавиатуру с категориями для выбора."""
    category_list = CATEGORY_STORAGE.expense if transaction_type == "Расход" else CATEGORY_STORAGE.income
    
    buttons = [
        InlineKeyboardButton(text=cat, callback_data=f"cat_{cat}")
        for cat in category_list
    ]
    
    # Распределяем кнопки по строкам (по 2 в строке)
    keyboard = [buttons[i:i + 2] for i in range(0, len(buttons), 2)]
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_amount_entry_keyboard() -> InlineKeyboardMarkup:
    """Генерирует Inline-клавиатуру с кнопкой 'Без суммы' для ввода суммы."""
    keyboard = [
        [InlineKeyboardButton(text="Без суммы", callback_data="amount_none")]
    ]
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_comment_entry_keyboard() -> InlineKeyboardMarkup:
    """Генерирует Inline-клавиатуру с кнопкой 'Без комментария' для ввода комментария."""
    keyboard = [
        [InlineKeyboardButton(text="Без комментария", callback_data="comment_none_draft")]
    ]
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_admin_main_keyboard() -> InlineKeyboardMarkup:
    """Генерирует Inline-клавиатуру для главного меню админ-панели."""
    keyboard = [
        [InlineKeyboardButton(text="👥 Управление пользователями", callback_data="manage_users")],
        [InlineKeyboardButton(text="📊 Статистика и отчеты", callback_data="view_stats")],
        [InlineKeyboardButton(text="📈 Настройки", callback_data="admin_settings")],
        [InlineKeyboardButton(text="❌ Выйти из админ-панели", callback_data="cancel_admin")]
    ]
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_admin_users_keyboard() -> InlineKeyboardMarkup:
    """Генерирует Inline-клавиатуру для меню управления пользователями."""
    keyboard = [
        [InlineKeyboardButton(text="➕ Добавить пользователя", callback_data="add_user_admin")],
        [InlineKeyboardButton(text="🗑️ Удалить пользователя", callback_data="remove_user_admin")],
        [InlineKeyboardButton(text="✏️ Изменить роль", callback_data="set_role_admin")],
        [InlineKeyboardButton(text="📋 Список пользователей", callback_data="list_users_admin")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_back_to_main")],
        [InlineKeyboardButton(text="❌ Выйти из админ-панели", callback_data="cancel_admin")]
    ]
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_admin_stats_keyboard() -> InlineKeyboardMarkup:
    """Генерирует Inline-клавиатуру для меню статистики."""
    keyboard = [
        [InlineKeyboardButton(text="📈 Общая статистика", callback_data="general_stats")],
        [InlineKeyboardButton(text="📊 По пользователям", callback_data="user_stats")],
        [InlineKeyboardButton(text="📋 Отчеты", callback_data="reports")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_back_to_main")],
        [InlineKeyboardButton(text="❌ Выйти из админ-панели", callback_data="cancel_admin")]
    ]
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)