# main.py
import asyncio
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command

# Импортируем из нашей новой структуры
from config import BOT_TOKEN, logger, DATA_SHEET_NAME, CATEGORY_STORAGE
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
    history_command_handler,
    history_callback_handler,
    close_history_handler,
    AllowedUsersFilter,
    Transaction
)
from handlers.transactions import register_draft_handlers, register_text_parser_handler, register_confirmation_handlers
from sheets.client import load_categories_from_sheet
from utils.keyboards import get_main_keyboard, HistoryCallbackData
from aiogram.types import BotCommand, MenuButtonWebApp

# Импорты для Local First архитектуры
from services.repository import TransactionRepository
from services.sync_worker import start_sync_worker


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
    dp.message.register(history_command_handler, Command("history"), AllowedUsersFilter())

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
    
    # Обработчик для истории транзакций и пагинации
    dp.message.register(history_command_handler, F.text == "📜 История транзакций", AllowedUsersFilter())
    dp.callback_query.register(history_callback_handler, HistoryCallbackData.filter(), AllowedUsersFilter())
    dp.callback_query.register(close_history_handler, F.data == "close_history", AllowedUsersFilter())


# Функция set_default_commands удалена, так как команды теперь отображаются в inline-клавиатуре


async def main():
    if not BOT_TOKEN:
        logger.error("❌ Невозможно запустить: BOT_TOKEN не найден.")
        return
    
    # Инициализация репозитория и синхронизация
    transaction_repository = TransactionRepository()
    await transaction_repository.init_db()
    
    logger.info("Загрузка категорий из Google Sheets...")
    if not await load_categories_from_sheet():
         logger.error("❌ Критическая ошибка: Не удалось загрузить категории. Бот не будет запущен.")
         return
    logger.info(f"Категории загружены. Расход: {len(CATEGORY_STORAGE.expense)}, Доход: {len(CATEGORY_STORAGE.income)}.")
         
    # Инициализируем classifier после загрузки категорий
    from utils.category_classifier import classifier
    try:
        logger.info("Загрузка классификатора и словарей...")
        # Импортируй classifier, если нужно
        await classifier.load()
        logger.info("Классификатор готов.")
    except Exception as e:
        logger.error(f"Ошибка загрузки данных: {e}")
     
    register_handlers(dp)
    register_draft_handlers(dp)
    register_text_parser_handler(dp)
    register_confirmation_handlers(dp)
     
    # Запуск фонового воркера синхронизации
    from sheets.client import get_google_sheet_client
    sheets_client = await get_google_sheet_client(DATA_SHEET_NAME)
    sync_task = asyncio.create_task(start_sync_worker(bot, transaction_repository, sheets_client))
     
    logger.info("🚀 Бот запущен! Ожидание команд...")
     
    # Устанавливаем основную Reply клавиатуру, чтобы она была доступна
    # В aiogram 3+ MenuButtonWebApp не используется для обычной ReplyKeyboardMarkup,
    # мы просто запускаем start_polling. ReplyKeyboardMarkup будет отображена после /start.
     
    try:
        await dp.start_polling(bot)
    except asyncio.CancelledError:
        logger.info("Бот остановлен пользователем")
    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем")
    finally:
        # Остановка задачи синхронизации при завершении
        sync_task.cancel()
        try:
            await sync_task
        except asyncio.CancelledError:
            pass

if __name__ == "__main__":
    asyncio.run(main())