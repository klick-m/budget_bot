from aiogram import Router

# Функции регистрации хендлеров
def register_all_handlers(dp: Router):
    """Регистрирует все хендлеры (сервисы инжектируются через DI)"""
    from .common import register_common_handlers
    from .receipts import register_receipt_handlers
    from .manual import register_manual_handlers, register_draft_handlers
    from .smart_input import register_smart_input_handlers
    
    # Регистрируем хендлеры
    register_common_handlers(dp)
    register_receipt_handlers(dp)
    register_manual_handlers(dp)
    register_draft_handlers(dp)
    # register_text_parser_handler(dp)  # Эта функция больше не используется
    register_smart_input_handlers(dp)

# Создаем главный роутер
dp = Router()

__all__ = [
    "dp",  # Главный роутер
    "register_all_handlers"
]