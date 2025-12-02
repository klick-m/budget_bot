# handlers/transactions.py
import asyncio
import re
import aiohttp
from datetime import datetime
from aiogram import Dispatcher, Bot, types, F
from aiogram.filters import BaseFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import BotCommand, ReplyKeyboardMarkup, KeyboardButton 

# Импорт из нашей структуры
from config import ALLOWED_USER_IDS, CATEGORY_STORAGE, logger, SHEET_WRITE_TIMEOUT
from sheets.client import write_transaction, add_keywords_to_sheet
from models.transaction import TransactionData, CheckData
from utils.exceptions import SheetWriteError, CheckApiTimeout, CheckApiRecognitionError
from utils.service_wrappers import safe_answer, edit_or_send
from utils.receipt_logic import parse_check_from_api, extract_learnable_keywords


# --- A. ФИЛЬТР И FSM ---
# ----------------------------------------------------------------------

class AllowedUsersFilter(BaseFilter):
    """Проверяет, является ли отправитель сообщения разрешенным пользователем."""
    async def __call__(self, message: types.Message) -> bool:
        if not ALLOWED_USER_IDS:
             return True # Если список разрешенных ID пуст, разрешаем всем
             
        return message.from_user.id in ALLOWED_USER_IDS

class Transaction(StatesGroup):
    choosing_type = State()
    choosing_category = State()
    choosing_category_after_check = State() 
    entering_amount = State()
    entering_comment = State()


# --- B. ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---
# ----------------------------------------------------------------------

def get_main_keyboard():
    """Возвращает основную ReplyKeyboardMarkup."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="💸 Добавить транзакцию")],
            [KeyboardButton(text="🧪 Проверить Sheets")]
        ],
        resize_keyboard=True,
        one_time_keyboard=False
    )

async def finalize_transaction(message_to_edit: types.Message, state: FSMContext, bot: Bot):
    """Финализирует транзакцию: собирает данные, записывает в Sheets, отправляет финальное сообщение."""
    
    data = await state.get_data()
    
    # 1. Формируем Pydantic модель TransactionData из FSM-данных
    try:
        transaction = TransactionData(
            type=data['type'],
            category=data['category'],
            amount=data['amount'],
            comment=data.get('comment', ''),
            username=message_to_edit.chat.username or message_to_edit.chat.full_name,
            retailer_name=data.get('retailer_name', ''),
            items_list=data.get('items_list', ''),
            payment_info=data.get('payment_info', ''),
            # Используем transaction_dt, если она была сохранена из чека, иначе default_factory
            transaction_dt=data.get('transaction_dt', datetime.now()) 
        )
    except Exception as e:
        logger.error(f"Ошибка при создании TransactionData: {e}")
        await edit_or_send(bot, message_to_edit, "❌ Критическая ошибка: Не удалось собрать данные транзакции.", parse_mode="Markdown")
        await state.clear()
        return

    # 2. Запись в Google Sheets с таймаутом
    try:
        async with asyncio.timeout(SHEET_WRITE_TIMEOUT):
            await write_transaction(transaction) 
            
        transaction_dt_str = transaction.transaction_dt.strftime('%d.%m.%Y %H:%M')
        
        summary = (
            f"✅ **Транзакция записана!**\n\n"
            f"Дата операции: **{transaction_dt_str}**\n"
            f"Тип: **{transaction.type}**\n"
            f"Категория: **{transaction.category}**\n"
            f"Сумма: **{transaction.amount}** руб.\n"
            f"Комментарий: *{transaction.comment or 'Нет'}*"
        )
        
        await edit_or_send(bot, message_to_edit, summary, parse_mode="Markdown")
    
    except asyncio.TimeoutError:
        await edit_or_send(bot, message_to_edit, f"❌ **Ошибка записи в Google Sheets!** Превышено время ожидания ({SHEET_WRITE_TIMEOUT} сек). Попробуйте повторить транзакцию позже.", parse_mode="Markdown")
    
    except SheetWriteError as e:
        await edit_or_send(bot, message_to_edit, f"❌ **Ошибка записи в Google Sheets!** Ошибка: {e}", parse_mode="Markdown")
    
    await state.clear()


# --- C. ХЕНДЛЕРЫ КОМАНД И ОСНОВНЫЕ ФУНКЦИИ ---
# ----------------------------------------------------------------------

async def command_start_handler(message: types.Message):
    await message.answer(
        f"Привет, **{message.from_user.full_name}**! 👋\n"
        "Выберите действие на клавиатуре ниже, или просто отправьте фото чека с QR-кодом для быстрого добавления.",
        parse_mode="Markdown",
        reply_markup=get_main_keyboard()
    )


async def test_sheets_handler(message: types.Message):
    status_msg = await message.answer("⏳ **Записываю тестовую транзакцию...** Ожидайте.") 

    test_data = TransactionData(
        type='ТЕСТ',
        category='Связь',
        amount=1.00,
        comment='Проверка связи с ботом',
        username=message.from_user.username or message.from_user.full_name,
        transaction_dt=datetime.now()
    )
    
    try:
        async with asyncio.timeout(SHEET_WRITE_TIMEOUT):
            await write_transaction(test_data) 
        
        await edit_or_send(
            message.bot, 
            status_msg,
            text="✅ **Успех!** Тестовая запись успешно добавлена в Google Таблицу.", 
            parse_mode="Markdown"
        )
    except (asyncio.TimeoutError, SheetWriteError) as e:
         await edit_or_send(
            message.bot, 
            status_msg,
            text=f"❌ **Ошибка!** Не удалось записать транзакцию: {e}", 
            parse_mode="Markdown"
        )


async def new_transaction_handler(message: types.Message, state: FSMContext):
    await state.clear()
    await state.set_state(Transaction.choosing_type)
    
    keyboard = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [types.InlineKeyboardButton(text="💸 Расход", callback_data="type_Расход")],
            [types.InlineKeyboardButton(text="💰 Доход", callback_data="type_Доход")]
        ]
    )
    await message.answer("Выберите тип операции:", reply_markup=keyboard)


# --- D. ХЕНДЛЕР ЧЕКОВ (СЛОЖНЫЙ) ---
# ----------------------------------------------------------------------

async def handle_photo(message: types.Message, state: FSMContext):
    await state.clear()
    
    # Определяем файл для скачивания
    if message.photo: file_object = message.photo[-1] 
    elif message.document and message.document.mime_type and message.document.mime_type.startswith('image'): file_object = message.document
    else: return 

    status_msg = await message.answer("⏳ **Чек получен.** Отправка изображения в API Proverkacheka.com...")
    
    file_info = await message.bot.get_file(file_object.file_id)
    file_url = f"https://api.telegram.org/file/bot{message.bot.token}/{file_info.file_path}"
    
    # 1. Скачивание файла
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(file_url) as response:
                image_bytes = await response.read()
    except Exception as e:
        await edit_or_send(message.bot, status_msg, f"❌ Ошибка скачивания файла: {e}")
        return

    # 2. Парсинг API (логика в utils/receipt_logic.py)
    try:
        parsed_data: CheckData = await parse_check_from_api(image_bytes) 
    except (CheckApiTimeout, CheckApiRecognitionError) as e:
        await edit_or_send(message.bot, status_msg, f"❌ Анализ чека не удался. {e}\nПопробуйте ввести вручную: /new_transaction")
        return
        
    if parsed_data.amount <= 0:
        await edit_or_send(message.bot, status_msg, "❌ Чек распознан, но сумма равна нулю или отрицательна. Введите вручную: /new_transaction")
        return

    # 3. Сохранение данных в FSM
    # Преобразуем Pydantic-модель в словарь для FSM
    fsm_data = parsed_data.model_dump()
    # Добавляем объект datetime для дальнейшей записи
    fsm_data['transaction_dt'] = parsed_data.transaction_datetime 
    await state.update_data(**fsm_data)
    
    # --- Форматирование предпросмотра ---
    items_list = parsed_data.items_list
    items_parts = [item.strip() for item in items_list.split('|') if item.strip()]
    preview_limit = 5
    if len(items_parts) > preview_limit:
        preview_items = "\n".join([f"• {item}" for item in items_parts[:preview_limit]])
        other_items_count = len(items_parts) - preview_limit
        items_preview = (f"**Первые {preview_limit} позиций:**\n{preview_items}\n"
                         f"*(+ {other_items_count} других позиций.)*")
    else:
        items_preview = "**Позиции:**\n" + "\n".join([f"• {item}" for item in items_parts])
        
    check_date_preview = f"Дата операции: **{parsed_data.transaction_datetime.strftime('%d.%m.%Y %H:%M')}**\n"
    fallback_category = CATEGORY_STORAGE.expense[-1] if CATEGORY_STORAGE.expense else "Прочее Расход"
    # -----------------------------------

    if parsed_data.category == fallback_category:
        
        # --- ЛОГИКА 1: КАТЕГОРИЯ НЕ ОПРЕДЕЛЕНА, ЗАПРАШИВАЕМ РУЧНОЙ ВВОД (С ОБУЧЕНИЕМ) ---
        await state.set_state(Transaction.choosing_category_after_check)
        
        buttons = [
            types.InlineKeyboardButton(text=cat, callback_data=f"checkcat_{cat}")
            for cat in CATEGORY_STORAGE.expense
        ]
        
        keyboard = types.InlineKeyboardMarkup(
            inline_keyboard=[buttons[i:i + 2] for i in range(0, len(buttons), 2)]
        )
        
        summary = (f"🔍 **Чек распознан, но категория не определена!**\n\n"
                   f"Сумма: **{parsed_data.amount}** руб.\n"
                   f"{check_date_preview}"
                   f"Продавец: *{parsed_data.retailer_name}*\n\n" 
                   f"{items_preview}\n\n"
                   f"⚠️ **Внимание:** Выберите категорию, чтобы бот **запомнил** продавца и товары для будущих чеков.")
                   
        await edit_or_send(message.bot, status_msg, summary, reply_markup=keyboard, parse_mode="Markdown")

    else:
        # --- ЛОГИКА 2: КАТЕГОРИЯ ОПРЕДЕЛЕНА ---
        await state.set_state(Transaction.entering_comment) 

        keyboard = types.InlineKeyboardMarkup(
            inline_keyboard=[
                [types.InlineKeyboardButton(text="✅ Подтвердить и Записать", callback_data="comment_none")]
            ]
        )
        
        default_comment_preview = parsed_data.comment.replace('|', '\n• ')
        
        summary = (f"🔍 **Чек распознан и категоризирован!**\n\n"
                   f"Тип: **{parsed_data.type}**\n"
                   f"Категория: **{parsed_data.category}** (Авто)\n"
                   f"Сумма: **{parsed_data.amount}** руб.\n"
                   f"{check_date_preview}"
                   f"Продавец: *{parsed_data.retailer_name}*\n" 
                   f"Оплата: *{parsed_data.payment_info}*\n\n" 
                   f"**Комментарий (по умолчанию):**\n• {default_comment_preview}\n\n"
                   f"Нажмите **Подтвердить**, чтобы записать, или введите другой комментарий.")
                   
        await edit_or_send(message.bot, status_msg, summary, reply_markup=keyboard, parse_mode="Markdown")


# --- E. ХЕНДЛЕРЫ FSM (Ввод данных) ---
# ----------------------------------------------------------------------

async def process_type_choice(callback: types.CallbackQuery, state: FSMContext, bot: Bot):
    
    await safe_answer(callback) # <--- ИСПОЛЬЗУЕМ ОБЕРТКУ safe_answer
    
    transaction_type = callback.data.split('_')[1]
    
    category_list = CATEGORY_STORAGE.expense if transaction_type == "Расход" else CATEGORY_STORAGE.income
    
    if not category_list:
        await edit_or_send(
            bot, 
            callback.message, 
            text=f"❌ Категории для типа '{transaction_type}' не загружены. Проверьте лист 'Categories'!",
        )
        return

    await state.update_data(type=transaction_type)
    await state.set_state(Transaction.choosing_category)
    
    buttons = [
        types.InlineKeyboardButton(text=cat, callback_data=f"cat_{cat}")
        for cat in category_list
    ]
    keyboard = types.InlineKeyboardMarkup(
        inline_keyboard=[buttons[i:i + 2] for i in range(0, len(buttons), 2)]
    )
    
    await edit_or_send(
        bot, 
        callback.message,
        text=f"Выбран тип: **{transaction_type}**. \nВыберите категорию:", 
        parse_mode="Markdown", 
        reply_markup=keyboard
    )


async def process_category_choice(callback: types.CallbackQuery, state: FSMContext, bot: Bot):
    
    await safe_answer(callback) # <--- ИСПОЛЬЗУЕМ ОБЕРТКУ safe_answer
    
    category = callback.data.split('_')[1]
    
    await state.update_data(category=category)
    await state.set_state(Transaction.entering_amount)
    
    await edit_or_send(
        bot, 
        callback.message,
        text=f"Категория: **{category}**. \nТеперь введите **сумму** (только число).",
        parse_mode="Markdown"
    )


async def process_category_choice_after_check(callback: types.CallbackQuery, state: FSMContext, bot: Bot):
    
    await safe_answer(callback) # <--- ИСПОЛЬЗУЕМ ОБЕРТКУ safe_answer
    
    new_category = callback.data.split('_')[1]
    data = await state.get_data()
    
    retailer_name = data.get('retailer_name', 'Неизвестный Продавец')
    items_list_str = data.get('items_list', '')

    keywords_to_learn = extract_learnable_keywords(retailer_name, items_list_str)
    
    # 1. Отправляем статус о сохранении ключевых слов
    status_msg = await edit_or_send(
        bot,
        callback.message,
        text=f"⏳ Категория **{new_category}** выбрана. Запоминаю {len(keywords_to_learn)} ключевых слов ({keywords_to_learn[0]}...) для будущих чеков...",
        parse_mode="Markdown"
    )

    # 2. Записываем ключевые слова в Google Sheets
    await add_keywords_to_sheet(new_category, keywords_to_learn)
    
    # 3. Обновляем FSM и переходим к комментарию
    await state.update_data(category=new_category)
    await state.set_state(Transaction.entering_comment)
    
    keyboard = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [types.InlineKeyboardButton(text="✅ Подтвердить и Записать", callback_data="comment_none")]
        ]
    )
    
    # В тексте сообщения показываем, что будет использовано в качестве комментария:
    default_comment_preview = data['comment'].replace('|', '\n• ')
    
    summary = (f"✅ Категория **{new_category}** запомнена для будущих чеков.\n"
               f"Сумма: **{data['amount']}** руб.\n\n"
               f"**Комментарий (по умолчанию):**\n• {default_comment_preview}\n\n"
               f"Нажмите **Подтвердить**, чтобы записать, или введите комментарий.")
               
    # 4. Выводим финальное подтверждение перед записью
    await edit_or_send(bot, status_msg, summary, reply_markup=keyboard, parse_mode="Markdown")


async def process_amount_entry(message: types.Message, state: FSMContext, bot: Bot):
    
    try:
        amount = round(float(message.text.replace(',', '.')), 2) 
        if amount <= 0:
            raise ValueError
    except ValueError:
        await message.answer("🚫 Сумма должна быть положительным числом. Попробуйте снова:")
        return

    await state.update_data(amount=amount)
    await state.set_state(Transaction.entering_comment)

    keyboard = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [types.InlineKeyboardButton(text="Без комментария", callback_data="comment_none")]
        ]
    )
    await message.answer("Сумма принята. Теперь введите **комментарий** или нажмите 'Без комментария'.", reply_markup=keyboard)


async def process_comment_entry(message: types.Message, state: FSMContext, bot: Bot):
    
    comment = message.text
    await state.update_data(comment=comment)
    
    # Отправляем новое сообщение, чтобы получить ID для редактирования статуса
    status_msg = await message.answer("⏳ **Записываю транзакцию...** Ожидайте.") 

    await finalize_transaction(status_msg, state, bot)


async def process_comment_skip(callback: types.CallbackQuery, state: FSMContext, bot: Bot):
    
    await safe_answer(callback) # <--- ИСПОЛЬЗУЕМ ОБЕРТКУ safe_answer
    
    data = await state.get_data()
    if not data.get('comment'):
        await state.update_data(comment="") 
        
    # Редактируем сообщение, чтобы показать статус загрузки
    await edit_or_send(
        bot,
        callback.message,
        text="⏳ **Записываю транзакцию...** Ожидайте.", 
        parse_mode="Markdown"
    )
    
    await finalize_transaction(callback.message, state, bot)