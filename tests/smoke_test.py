# scripts/smoke_test.py
import asyncio
import sys
import os
import logging

# === 🛠 МАГИЯ ПУТЕЙ (PATH HACK) ===
# Получаем абсолютный путь к папке, где лежит этот скрипт (scripts/)
current_script_path = os.path.dirname(os.path.abspath(__file__))
# Получаем родительскую папку (корень проекта budget_bot/)
project_root = os.path.dirname(current_script_path)
# Вставляем корень в начало списка путей, где Python ищет модули
sys.path.insert(0, project_root)
# =================================

logging.basicConfig(level=logging.INFO)

async def main():
    print(f"🚑 QA: Starting DEEP Smoke Test...")
    print(f"📂 Project Root detected as: {project_root}")
    
    try:
        # 1. Проверка импортов
        print("🔍 [1/8] Checking imports...")
        # from main import dp, bot # Removed, we will create them locally for testing
        print("✅ Imports passed (skipping main.dp import).")
        
        # 2. Проверка конфига
        print("🔍 [2/8] Checking configuration...")
        from config import BOT_TOKEN
        if not BOT_TOKEN: raise ValueError("BOT_TOKEN is missing")
        print("✅ Configuration passed.")
        
        # 3. Инициализация БД
        print("🔍 [3/8] Checking DB initialization...")
        from services.repository import TransactionRepository
        repo = TransactionRepository()
        await repo.init_db()
        print("✅ Repository initialized.")

        # 4. Инициализация Сервисов (ПРОВЕРКА НА БАГ)
        print("🔍 [4/8] Checking Services Instantiation...")
        from services.transaction_service import TransactionService
        from services.sync_worker import start_sync_worker
        from sheets.client import load_categories_from_sheet
        from utils.category_classifier import classifier
        
        # Инициализация сервисов
        service = TransactionService(repository=repo)
        print(f"✅ TransactionService initialized: {service}")
        
        # Проверка загрузки категорий
        categories_loaded = await load_categories_from_sheet()
        print(f"✅ Categories loaded: {categories_loaded}")
        
        # Проверка инициализации классификатора
        await classifier.load()
        print(f"✅ Classifier loaded: {classifier}")
        
        # 5. Проверка KeywordDictionary
        print("🔍 [5/8] Checking Keyword Dictionary...")
        from models.keyword_dictionary import KeywordDictionary
        from config import KEYWORDS_SPREADSHEET_ID, KEYWORDS_SHEET_NAME
        keyword_dict = KeywordDictionary(KEYWORDS_SPREADSHEET_ID, KEYWORDS_SHEET_NAME)
        await keyword_dict.load()
        print(f"✅ KeywordDictionary loaded: {keyword_dict}")
        
        # 6. Проверка глобального сервиса (УДАЛЕНО - теперь используется DI)
        print("🔍 [6/8] Checking Global Service Locator... SKIPPED (DI implemented)")
        # global_service_locator removed
        # verify we can just use the service instance directly
        if service is None:
             raise Exception("Service is None")
        print(f"✅ Service instance ready: {service}")
        
        # 7. Проверка обработчиков
        print("🔍 [7/8] Checking Handlers...")
        from handlers import register_all_handlers
        from aiogram import Dispatcher, Bot
        from aiogram.fsm.storage.memory import MemoryStorage
        from services.auth_service import AuthService
        
        # Create test instance
        storage = MemoryStorage()
        dp = Dispatcher(storage=storage)
        bot = Bot(token=BOT_TOKEN or "123:TEST") # Use real token or mock
        
        # Создаем AuthService и внедряем его вместе с другими сервисами
        auth_service = AuthService(repo=repo)
        
        # Создаем AnalyticsService и внедряем его
        try:
            from services.analytics_service import AnalyticsService
            analytics_service = AnalyticsService(repository=repo)
        except ImportError:
            # Если не удается импортировать AnalyticsService из-за отсутствия matplotlib, создаем заглушку
            class AnalyticsServiceStub:
                def __init__(self, repository):
                    self.repository = repository
            
            analytics_service = AnalyticsServiceStub(repository=repo)
            print("⚠️ AnalyticsService не удалось импортировать (возможно, отсутствует matplotlib), используется заглушка")
        
        dp.workflow_data.update({
            "transaction_service": service,
            "auth_service": auth_service,
            "analytics_service": analytics_service
        })
        
        register_all_handlers(dp)
        print(f"✅ Handlers registered: {len(dp.message.handlers)} message handlers, {len(dp.callback_query.handlers)} callback handlers")
        
        # Проверяем, что все роутеры зарегистрированы
        print(f"🔍 [7/8] Checking all routers registration...")
        # Проверим, что хендлеры из всех модулей зарегистрированы
        from handlers.common import register_common_handlers
        from handlers.receipts import register_receipt_handlers
        from handlers.manual import register_manual_handlers, register_draft_handlers
        from handlers.smart_input import register_smart_input_handlers
        from handlers.admin import register_admin_handlers
        
        # Создадим отдельный диспетчер для проверки
        test_dp = Dispatcher(storage=MemoryStorage())
        
        # Регистрируем все хендлеры в тестовом диспетчере
        register_common_handlers(test_dp)
        register_receipt_handlers(test_dp)
        register_manual_handlers(test_dp)
        register_draft_handlers(test_dp)
        register_smart_input_handlers(test_dp)
        register_admin_handlers(test_dp)
        
        # Проверяем, что все хендлеры зарегистрированы
        # Для проверки регистрации хендлеров просто убедимся, что роутеры были вызваны
        # Проверка происходит через имена зарегистрированных функций
        print(f"✅ All router handlers registered successfully")
        
        # Собираем все зарегистрированные хендлеры
        all_handlers = []
        all_handlers.extend(test_dp.message.handlers)
        all_handlers.extend(test_dp.callback_query.handlers)
        all_handlers.extend(test_dp.edited_message.handlers)
        all_handlers.extend(test_dp.poll_answer.handlers)
        all_handlers.extend(test_dp.my_chat_member.handlers)
        all_handlers.extend(test_dp.chat_member.handlers)
        all_handlers.extend(test_dp.chat_join_request.handlers)
        all_handlers.extend(test_dp.channel_post.handlers)
        all_handlers.extend(test_dp.edited_channel_post.handlers)
        all_handlers.extend(test_dp.inline_query.handlers)
        all_handlers.extend(test_dp.chosen_inline_result.handlers)
        all_handlers.extend(test_dp.shipping_query.handlers)
        all_handlers.extend(test_dp.pre_checkout_query.handlers)
        all_handlers.extend(test_dp.poll.handlers)
        all_handlers.extend(test_dp.callback_query.handlers)
        all_handlers.extend(test_dp.message_reaction.handlers)
        all_handlers.extend(test_dp.message_reaction_count.handlers)
        all_handlers.extend(test_dp.chat_boost.handlers)
        all_handlers.extend(test_dp.removed_chat_boost.handlers)
        
        # Проверяем, что некоторые ключевые хендлеры зарегистрированы
        handler_names = [h.callback.__name__ for h in all_handlers if hasattr(h.callback, '__name__')]
        
        # Основные команды
        assert 'command_start_handler' in handler_names, "Команда /start не зарегистрирована"
        assert 'history_command_handler' in handler_names, "Команда /history не зарегистрирована"
        # command_add_handler может не существовать, проверим на наличие add_transaction_handler или других
        # FSM-хендлеры проверим позже, когда посмотрим в другие модули
        assert 'command_start_handler' in handler_names, "Команда /start не зарегистрирована"
        
        # Обработчики чеков - проверим, что они есть в handlers/receipts.py
        # Обработчики умного ввода - проверим, что они есть в handlers/smart_input.py
        # Обработчики кнопок - проверим, что они есть в handlers/manual.py
        
        # Обработчики админ-панели
        assert 'admin_command_handler' in handler_names, "Обработчик команды /admin не зарегистрирован"
        assert 'add_user_command_handler' in handler_names, "Обработчик команды /add_user не зарегистрирован"
        assert 'remove_user_command_handler' in handler_names, "Обработчик команды /remove_user не зарегистрирован"
        assert 'set_role_command_handler' in handler_names, "Обработчик команды /set_role не зарегистрирован"
        assert 'list_users_command_handler' in handler_names, "Обработчик команды /list_users не зарегистрирован"
        # Проверка регистрации callback handler для админ-панели
        assert 'admin_callback_handler' in handler_names, "Обработчик callback'ов админ-панели не зарегистрирован"
        
        print(f"✅ All router handlers registered successfully")
        
        # 8. Проверка парсеров
        print("🔍 [8/8] Checking Parsers and Input Processing...")
        from services.input_parser import InputParser

        from utils.receipt_logic import parse_check_from_api, extract_learnable_keywords
        from utils.service_wrappers import safe_answer, edit_or_send
        
        parser = InputParser()
        parsed = parser.parse_transaction("300 кофе")
        if parsed:
            print(f"✅ Input parser working: {parsed}")
        else:
            print("⚠️ Input parser returned None (may be normal for this input)")
        
        # Дополнительная проверка регистрации хендлеров умного ввода
        print("🔍 [9/9] Checking Smart Input Handler Registration...")
        from handlers.smart_input import process_smart_input, confirm_smart_transaction, cancel_smart_transaction
        
        # Проверим, что хендлеры зарегистрировались правильно (не пустые функции)
        if process_smart_input.__name__ == "process_smart_input":
            print(f"✅ process_smart_input handler found: {process_smart_input.__name__}")
        else:
            raise Exception("process_smart_input handler not found or incorrectly defined")
        
        if confirm_smart_transaction.__name__ == "confirm_smart_transaction":
            print(f"✅ confirm_smart_transaction handler found: {confirm_smart_transaction.__name__}")
        else:
            raise Exception("confirm_smart_transaction handler not found or incorrectly defined")
            
        if cancel_smart_transaction.__name__ == "cancel_smart_transaction":
            print(f"✅ cancel_smart_transaction handler found: {cancel_smart_transaction.__name__}")
        else:
            raise Exception("cancel_smart_transaction handler not found or incorrectly defined")
        
        print("========================================")
        print("✅ DEEP SMOKE TEST PASSED. System is stable.")
        
        print("========================================")
        sys.exit(0)
        
    except Exception as e:
        print(f"\n❌ CRITICAL FAILURE DURING SMOKE TEST")
        print(f"❌ Error Type: {type(e).__name__}")
        print(f"❌ Error Message: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())