# main.py
import asyncio
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

# Импортируем из нашей новой структуры
from config import BOT_TOKEN, logger
from handlers import register_all_handlers
from services.transaction_service import TransactionService
from services.repository import TransactionRepository
from sheets.client import load_categories_from_sheet, write_transaction
from services.sync_worker import start_sync_worker
from utils.service_wrappers import AuthMiddleware
from services.analytics_service import AnalyticsService


async def main():
    if not BOT_TOKEN:
        logger.error("❌ Невозможно запустить: BOT_TOKEN не найден.")
        return

    # Инициализация репозитория
    transaction_repository = TransactionRepository()
    await transaction_repository.init_db()

    # Попытка загрузки категорий из Google Sheets
    logger.info("Загрузка категорий из Google Sheets...")
    try:
        if not await load_categories_from_sheet():
            logger.warning("⚠️ Не удалось загрузить категории из Google Sheets. Бот будет запущен с пустым кэшем.")
    except Exception as e:
        logger.error(f"⚠️ Ошибка при обращении к Google Sheets: {e}. Бот продолжает запуск.")

    # Создаем TransactionService с внедренным репозиторием
    transaction_service = TransactionService(repository=transaction_repository)
    # Асинхронная инициализация сервиса
    await transaction_service.initialize()

    # Создаем диспетчер с хранилищем состояний
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)
    
    # Регистрируем middleware авторизации
    auth_middleware = AuthMiddleware(repo=transaction_repository)
    dp.message.middleware(auth_middleware)
    dp.callback_query.middleware(auth_middleware)
    # Внедрение зависимостей
    analytics_service = AnalyticsService(repository=transaction_repository)
    dp.workflow_data.update({
        "transaction_service": transaction_service,
        "analytics_service": analytics_service
    })


    # Регистрируем обработчики
    register_all_handlers(dp)


    # Создаем бота
    bot = Bot(token=BOT_TOKEN)

    logger.info("🚀 Бот запущен! Ожидание команд...")

    # Удаляем меню команд (синюю кнопку), чтобы не мешала основной клавиатуре
    await bot.delete_my_commands()

    # Запускаем polling с корректной обработкой ошибок
    sync_task = None
    try:
        # Запускаем фоновый воркер синхронизации
        sync_task = asyncio.create_task(
            start_sync_worker(bot, transaction_repository, None)
        )
        logger.info("🔄 Фоновая синхронизация запущена.")
        
        # Запускаем polling с обработкой конфликтов
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    except KeyboardInterrupt:
        logger.info("Получен сигнал KeyboardInterrupt. Завершение работы...")
    except Exception as e:
        logger.error(f"Критическая ошибка в polling: {e}")
        import traceback
        logger.error(f"Стек вызова: {traceback.format_exc()}")
    finally:
        # Корректно завершаем фоновую задачу синхронизации
        if sync_task and not sync_task.done():
            sync_task.cancel()
            try:
                await sync_task
            except asyncio.CancelledError:
                logger.info("Фоновая задача синхронизации завершена.")
        
        # Закрываем соединение с ботом
        await bot.session.close()
        
        # Закрываем соединение с базой данных при завершении
        await transaction_repository.close()
        logger.info("Соединение с базой данных закрыто.")
        logger.info("Бот завершил работу корректно.")


if __name__ == "__main__":
    asyncio.run(main())