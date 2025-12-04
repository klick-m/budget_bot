# main.py
import asyncio  
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command

# Импортируем из нашей новой структуры
from config import BOT_TOKEN, logger
from handlers.transactions import (
    command_start_handler, 
    test_sheets_handler, 
    new_transaction_handler, 
    handle_photo, 
    process_type_choice,
    process_category_choice,
    process_category_choice_after_check,
    process_edit_category,
    process_amount_entry,
    process_comment_entry,
    process_comment_skip,
    cancel_check,
    AllowedUsersFilter,
    Transaction 
)
from sheets.client import load_categories_from_sheet
from utils.keyboards import get_main_keyboard 
from aiogram.types import BotCommand, MenuButtonWebApp


# 2. Инициализация Бота и Диспетчера
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# --- Регистрация хендлеров ---
def register_handlers(dp: Dispatcher):
    
    # 1. Команды и Основные кнопки
    # ВНИМАНИЕ: CommandStart не требует AllowedUsersFilter, 
    # так как мы хотим, чтобы все могли вызвать /start, но фильтр можно оставить для контроля.
    dp.message.register(command_start_handler, F.text.startswith('/start'), AllowedUsersFilter()) 
    dp.message.register(test_sheets_handler, Command("test_sheets"), AllowedUsersFilter())
    dp.message.register(test_sheets_handler, F.text == "🧪 Проверить Sheets", AllowedUsersFilter())
    dp.message.register(new_transaction_handler, Command("new_transaction"), AllowedUsersFilter())
    dp.message.register(new_transaction_handler, F.text == "💸 Добавить транзакцию", AllowedUsersFilter())

    # 2. Обработка чеков
    dp.message.register(handle_photo, F.photo | F.document, AllowedUsersFilter())

    # 3. FSM 
    dp.callback_query.register(process_type_choice, F.data.startswith("type_"), Transaction.choosing_type, AllowedUsersFilter())
    dp.callback_query.register(process_category_choice, F.data.startswith("cat_"), Transaction.choosing_category, AllowedUsersFilter())
    
    # FSM для чеков
    dp.callback_query.register(process_category_choice_after_check, F.data.startswith("checkcat_"), Transaction.choosing_category_after_check, AllowedUsersFilter())
    
    # Подтверждение и отмена чека
    dp.callback_query.register(process_comment_skip, F.data == "confirm_and_record", Transaction.confirming_check, AllowedUsersFilter())
    dp.callback_query.register(cancel_check, F.data == "cancel_check", Transaction.confirming_check, AllowedUsersFilter())
    
    # Подтверждение автоматически распознанного чека
    dp.callback_query.register(process_comment_skip, F.data == "comment_none", Transaction.confirming_auto_check, AllowedUsersFilter())
    dp.callback_query.register(cancel_check, F.data == "cancel_check", Transaction.confirming_auto_check, AllowedUsersFilter())
    dp.callback_query.register(process_edit_category, F.data == "edit_category", Transaction.confirming_auto_check, AllowedUsersFilter())
    
    dp.message.register(process_amount_entry, Transaction.entering_amount, F.text, AllowedUsersFilter())
    dp.message.register(process_comment_entry, Transaction.entering_comment, F.text, AllowedUsersFilter())
    dp.callback_query.register(process_comment_skip, F.data == "comment_none", Transaction.entering_comment, AllowedUsersFilter())


async def set_commands(bot: Bot):
    """Устанавливает команды для меню бота (минимальный набор)."""
    commands = [
        BotCommand(command="start", description="🔄 Перезапустить бота"),
        BotCommand(command="new_transaction", description="💸 Добавить транзакцию вручную")
    ]
    await bot.set_my_commands(commands)
    logger.info("✅ Меню команд успешно установлено.")


async def main():
    if not BOT_TOKEN:
        logger.error("❌ Невозможно запустить: BOT_TOKEN не найден.")
        return
    
    logger.info("Загрузка категорий из Google Sheets...")
    if not await load_categories_from_sheet():
         logger.error("❌ Критическая ошибка: Не удалось загрузить категории. Бот не будет запущен.")
         return
    
    register_handlers(dp)
    
    await set_commands(bot) 
        
    logger.info("🚀 Бот запущен! Ожидание команд...")
    
    # Устанавливаем основную Reply клавиатуру, чтобы она была доступна
    # В aiogram 3+ MenuButtonWebApp не используется для обычной ReplyKeyboardMarkup,
    # мы просто запускаем start_polling. ReplyKeyboardMarkup будет отображена после /start.
    
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())