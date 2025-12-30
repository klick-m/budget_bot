
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from models.transaction import CheckItem

def get_items_keyboard(items: list[CheckItem], selected_indices: set[int]) -> InlineKeyboardMarkup:
    """Генерирует клавиатуру для выбора товаров."""
    buttons = []
    for i, item in enumerate(items):
        # Если товар уже выбран, ставим галочку
        mark = "✅" if i in selected_indices else "⬜"
        # Обрезаем название, если слишком длинное
        name = item.name[:30] + "..." if len(item.name) > 30 else item.name
        text = f"{mark} {name} - {item.sum:.2f}"
        buttons.append([InlineKeyboardButton(text=text, callback_data=f"toggle_item_{i}")])
    
    # Кнопки управления
    controls = []
    if selected_indices:
        controls.append(InlineKeyboardButton(text=f"➡ Далее ({len(selected_indices)})", callback_data="split_next_step"))
    
    controls.append(InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_check"))
    buttons.append(controls)
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_categories_inline_keyboard(categories: list[str], prefix: str = "splitcat") -> InlineKeyboardMarkup:
    """Кнопки категорий для сплита"""
    buttons = [
        InlineKeyboardButton(text=cat, callback_data=f"{prefix}_{cat}")
        for cat in categories
    ]
    # Разбиваем на ряды по 2
    rows = [buttons[i:i + 2] for i in range(0, len(buttons), 2)]
    return InlineKeyboardMarkup(inline_keyboard=rows)
