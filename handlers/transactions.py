# -*- coding: utf-8 -*-
# handlers/transactions.py
import asyncio
import re
import aiohttp
from datetime import datetime
from aiogram import Dispatcher, Bot, types
from aiogram.filters import BaseFilter, StateFilter
from aiogram.types import BotCommand, ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram import F

# Импорт из нашей структуры
from config import ALLOWED_USER_IDS, CATEGORY_STORAGE, logger, SHEET_WRITE_TIMEOUT
from sheets.client import write_transaction, add_keywords_to_sheet, load_categories_from_sheet
from models.transaction import TransactionData, CheckData
from utils.exceptions import SheetWriteError, CheckApiTimeout, CheckApiRecognitionError
from utils.service_wrappers import safe_answer, edit_or_send
from utils.receipt_logic import parse_check_from_api, extract_learnable_keywords
from utils.category_classifier import classifier
from utils.keyboards import get_history_keyboard, HistoryCallbackData
from sheets.client import get_latest_transactions
from aiogram.filters import Command, CommandObject


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
    confirming_check = State()  # Подтверждение чека после выбора категории вручную
    confirming_auto_check = State()  # Подтверждение автоматически распознанного чека
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
        # Обучаем классификатор на новой транзакции перед записью
        transactions_for_training = [transaction]
        
        # Пытаемся получить историю транзакций для обучения
        # (в реальном приложении здесь нужно будет получить исторические данные из Google Sheets)
        # Пока используем только текущую транзакцию, но в будущем можно расширить
        
        # Обновляем модель классификатора
        classifier.train(transactions_for_training)
        
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
    # Создаем Reply-клавиатуру с командами
    keyboard = types.ReplyKeyboardMarkup(
        keyboard=[
            [types.KeyboardButton(text="💸 Добавить транзакцию")],
            [types.KeyboardButton(text="📜 История транзакций")],
            [types.KeyboardButton(text="🧪 Проверить Sheets")]
        ],
        resize_keyboard=True,
        one_time_keyboard=False
    )
    
    await message.answer(
        f"Привет, **{message.from_user.full_name}**! 👋\n"
        "Выберите действие на клавиатуре ниже, или просто отправьте фото чека с QR-кодом для быстрого добавления.",
        parse_mode="Markdown",
        reply_markup=keyboard
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
    if message.photo:
        # Проверяем размер фото (ограничим максимальный размер файла в 5 МБ)
        if message.photo[-1].file_size and message.photo[-1].file_size > 5 * 1024 * 1024:
            await message.answer("❌ Размер изображения слишком большой. Пожалуйста, отправьте фото меньше 5 МБ.")
            return
        file_object = message.photo[-1]
    elif message.document and message.document.mime_type and message.document.mime_type.startswith('image'):
        # Проверяем размер документа
        if message.document.file_size and message.document.file_size > 5 * 1024 * 1024:
            await message.answer("❌ Размер изображения слишком большой. Пожалуйста, отправьте фото меньше 5 МБ.")
            return
        file_object = message.document
    else:
        return

    status_msg = await message.answer("⏳ **Чек получен.** Отправка изображения в API Proverkacheka.com...")
    
    # 0. Перезагружаем категории из Google Sheets чтобы использовать актуальные ключевые слова
    await load_categories_from_sheet()
    
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

    # Создаем TransactionData из полученных данных для использования в классификаторе
    temp_transaction = TransactionData(
        type=parsed_data.type,
        category=parsed_data.category,
        amount=parsed_data.amount,
        comment=parsed_data.comment,
        username=message.from_user.username or message.from_user.full_name,
        retailer_name=parsed_data.retailer_name,
        items_list=parsed_data.items_list,
        payment_info=parsed_data.payment_info,
        transaction_dt=parsed_data.transaction_datetime
    )
    
    # Применяем улучшенную классификацию
    predicted_category, confidence = classifier.predict_category(temp_transaction)
    
    # Вместо предложения новой категории, используем только существующие категории
    if parsed_data.category == fallback_category or confidence < 0.5:
        
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
        # Обновляем категорию на основе предсказания улучшенного классификатора
        if confidence > 0.7:  # Если уверенность высока, используем предсказание
            parsed_data.category = predicted_category
        
        await state.set_state(Transaction.confirming_auto_check)

        keyboard = types.InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    types.InlineKeyboardButton(text="✅ Подтвердить и Записать", callback_data="comment_none"),
                    types.InlineKeyboardButton(text="❌ Отменить", callback_data="cancel_check")
                ],
                [
                    types.InlineKeyboardButton(text="✏️ Изменить категорию", callback_data="edit_category")
                ]
            ]
        )
        
        default_comment_preview = parsed_data.comment.replace('|', '\n• ')
        
        summary = (f"🔍 **Чек распознан и категоризирован!**\n\n"
                   f"Тип: **{parsed_data.type}**\n"
                   f"Категория: **{parsed_data.category}** (Авто, уверенность: {confidence:.2f})\n"
                   f"Сумма: **{parsed_data.amount}** руб.\n"
                   f"{check_date_preview}"
                   f"Продавец: *{parsed_data.retailer_name}*\n"
                   f"Оплата: *{parsed_data.payment_info}*\n\n"
                   f"**Позиции в чеке:**\n• {default_comment_preview}\n\n"
                   f"Нажмите **Подтвердить**, чтобы записать, или **Отменить**.")
                   
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
    
    # Сохраняем новую категорию и переходим в состояние подтверждения
    await state.update_data(category=new_category)
    await state.set_state(Transaction.confirming_check)
    
    # Показываем сводку и кнопки подтверждения/отмены БЕЗ добавления ключевых слов
    default_comment_preview = data['comment'].replace('|', '\n• ')
    transaction_dt_str = data.get('transaction_dt').strftime('%d.%m.%Y %H:%M') if data.get('transaction_dt') else 'сейчас'
    
    summary = (f"🔍 **Чек распознан и категоризирован!**\n\n"
               f"Тип: **{data.get('type', 'Расход')}**\n"
               f"Категория: **{new_category}** (вручную выбрана)\n"
               f"Сумма: **{data['amount']}** руб.\n"
               f"Дата: **{transaction_dt_str}**\n"
               f"Продавец: *{data.get('retailer_name', 'Неизвестный')}*\n\n"
               f"**Позиции в чеке:**\n• {default_comment_preview}\n\n"
               f"✅ Готово к записи?")
    
    keyboard = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [
                types.InlineKeyboardButton(text="✅ Подтвердить и Записать", callback_data="confirm_and_record"),
                types.InlineKeyboardButton(text="❌ Отменить", callback_data="cancel_check")
            ]
        ]
    )
    
    await edit_or_send(bot, callback.message, summary, reply_markup=keyboard, parse_mode="Markdown")


async def process_edit_category(callback: types.CallbackQuery, state: FSMContext, bot: Bot):
    """Переводит пользователя в режим выбора категории для авто-распознанного чека."""
    
    await safe_answer(callback)
    
    data = await state.get_data()
    transaction_type = data.get('type', 'Расход')
    category_list = CATEGORY_STORAGE.expense if transaction_type == "Расход" else CATEGORY_STORAGE.income
    
    # Переходим в состояние выбора категории
    await state.set_state(Transaction.choosing_category_after_check)
    
    buttons = [
        types.InlineKeyboardButton(text=cat, callback_data=f"checkcat_{cat}")
        for cat in category_list
    ]
    keyboard = types.InlineKeyboardMarkup(
        inline_keyboard=[buttons[i:i + 2] for i in range(0, len(buttons), 2)]
    )
    
    await edit_or_send(
        bot,
        callback.message,
        text=f"Выберите правильную категорию для этого чека:",
        parse_mode="Markdown",
        reply_markup=keyboard
    )


async def process_amount_entry(message: types.Message, state: FSMContext, bot: Bot):
    
    try:
        amount = round(float(message.text.replace(',', '.')), 2)
        if amount <= 0:
            raise ValueError("Сумма должна быть положительной")
        if amount > 100000:  # Ограничение максимальной суммы
            await message.answer("❌ Сумма слишком велика. Пожалуйста, введите сумму до 100000.")
            return
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
    
    # Проверяем, находимся ли мы в состоянии подтверждения чека (нужно добавить ключевые слова)
    current_state = await state.get_state()
    
    if current_state == Transaction.confirming_check:
        # Это подтверждение после выбора категории для чека - добавляем ключевые слова
        new_category = data.get('category')
        retailer_name = data.get('retailer_name', 'Неизвестный Продавец')
        items_list_str = data.get('items_list', '')
        keywords_to_learn = extract_learnable_keywords(retailer_name, items_list_str)
        
        # Показываем статус о сохранении ключевых слов
        status_msg = await edit_or_send(
            bot,
            callback.message,
            text=f"⏳ Категория **{new_category}** подтверждена. Запоминаю {len(keywords_to_learn)} ключевых слов для будущих чеков...",
            parse_mode="Markdown"
        )
        
        # Записываем ключевые слова в Google Sheets
        await add_keywords_to_sheet(new_category, keywords_to_learn)
        
        # Обучаем классификатор на новой транзакции
        temp_transaction = TransactionData(
            type=data.get('type', 'Расход'),
            category=new_category,
            amount=data.get('amount'),
            comment=data.get('comment', ''),
            username=callback.from_user.username or callback.from_user.full_name,
            retailer_name=retailer_name,
            items_list=items_list_str,
            payment_info=data.get('payment_info', ''),
            transaction_dt=data.get('transaction_dt', datetime.now())
        )
        
        # Обновляем модель классификатора
        classifier.train([temp_transaction])
        
        # Теперь записываем саму транзакцию
        await edit_or_send(
            bot,
            status_msg,
            text="⏳ **Записываю транзакцию...** Ожидайте.",
            parse_mode="Markdown"
        )
        
        await finalize_transaction(status_msg, state, bot)
        
    elif current_state == Transaction.confirming_auto_check:
        # Это подтверждение автоматически распознанного чека - обучаем классификатор
        temp_transaction = TransactionData(
            type=data.get('type', 'Расход'),
            category=data.get('category'),
            amount=data.get('amount'),
            comment=data.get('comment', ''),
            username=callback.from_user.username or callback.from_user.full_name,
            retailer_name=data.get('retailer_name', ''),
            items_list=data.get('items_list', ''),
            payment_info=data.get('payment_info', ''),
            transaction_dt=data.get('transaction_dt', datetime.now())
        )
        
        # Обновляем модель классификатора
        classifier.train([temp_transaction])
        
        await edit_or_send(
            bot,
            callback.message,
            text="⏳ **Записываю транзакцию...** Ожидайте.",
            parse_mode="Markdown"
        )
        
        await finalize_transaction(callback.message, state, bot)
    else:
        # Обычное пропускание комментария
        await edit_or_send(
            bot,
            callback.message,
            text="⏳ **Записываю транзакцию...** Ожидайте.",
            parse_mode="Markdown"
        )
        
        await finalize_transaction(callback.message, state, bot)


async def cancel_check(callback: types.CallbackQuery, state: FSMContext, bot: Bot):
    """Отменяет ввод чека и возвращает на начало."""
    
    await safe_answer(callback)
    
    await state.clear()
    
    # Редактируем текущее сообщение
    await edit_or_send(
        bot,
        callback.message,
        text="❌ **Чек отменен.** Выберите действие на клавиатуре ниже.",
        parse_mode="Markdown"
    )


async def history_command_handler(message: types.Message):
    """Обработчик команды /history для просмотра последних транзакций."""
    # Получаем последние 5 транзакций с нулевым смещением
    user_id = message.from_user.username or str(message.from_user.id)
    transactions = await get_latest_transactions(user_id=user_id, limit=5, offset=0)
    
    if not transactions:
        await message.answer("📋 У вас пока нет транзакций в истории.")
        return

    # Формируем сообщение с транзакциями
    history_text = "📜 *История ваших последних транзакций:*\n\n"
    for i, transaction in enumerate(transactions, 1):
        # Обрезаем комментарий до 20 символов, если он длиннее
        comment = transaction['comment'] if transaction['comment'] else 'Нет'
        if len(comment) > 20:
            comment = comment[:20] + "..."
        history_text += (
            f"{i}. *{transaction['date']} {transaction['time']}*\n"
            f"   Тип: {transaction['type']}\n"
            f"   Категория: {transaction['category']}\n"
            f"   Сумма: {transaction['amount']} руб.\n"
            f"   Комментарий: {comment}\n\n"
        )
    
    # Проверяем, есть ли следующие транзакции для пагинации
    # Получаем 6-ю транзакцию, чтобы проверить, есть ли следующая страница
    next_transactions = await get_latest_transactions(user_id=user_id, limit=1, offset=5)
    has_next = len(next_transactions) > 0

    # Создаем клавиатуру с пагинацией
    keyboard = get_history_keyboard(offset=0, has_next=has_next)

    await message.answer(history_text, reply_markup=keyboard, parse_mode="Markdown")


async def history_callback_handler(callback: types.CallbackQuery, callback_data: HistoryCallbackData):
    """Обработчик кнопок пагинации истории транзакций."""
    await safe_answer(callback)  # Безопасно отвечаем на callback
    
    offset = callback_data.offset
    direction = callback_data.direction
    
    # Получаем транзакции с новым смещением
    user_id = callback.from_user.username or str(callback.from_user.id)
    transactions = await get_latest_transactions(user_id=user_id, limit=5, offset=offset)
    
    if not transactions:
        await callback.message.edit_text("📋 У вас пока нет транзакций в истории.")
        return

    # Формируем сообщение с транзакциями
    history_text = "📜 *История ваших транзакций:*\n\n"
    for i, transaction in enumerate(transactions, 1):
        # Обрезаем комментарий до 20 символов, если он длиннее
        comment = transaction['comment'] if transaction['comment'] else 'Нет'
        if len(comment) > 20:
            comment = comment[:20] + "..."
        history_text += (
            f"{i}. *{transaction['date']} {transaction['time']}*\n"
            f"   Тип: {transaction['type']}\n"
            f"   Категория: {transaction['category']}\n"
            f"   Сумма: {transaction['amount']} руб.\n"
            f"   Комментарий: {comment}\n\n"
        )
    
    # Проверяем, есть ли следующие транзакции для пагинации
    # Получаем транзакцию после текущей страницы, чтобы проверить, есть ли следующая страница
    next_transactions = await get_latest_transactions(user_id=user_id, limit=1, offset=offset + 5)
    has_next = len(next_transactions) > 0

    # Проверяем, есть ли предыдущие транзакции для пагинации
    has_prev = offset > 0

    # Создаем клавиатуру с пагинацией
    keyboard = get_history_keyboard(offset=offset, has_next=has_next)

    # Проверяем, изменилось ли содержимое сообщения или клавиатура
    # Если нет, то не пытаемся редактировать сообщение, чтобы избежать ошибки "message is not modified"
    current_text = callback.message.text or ""
    current_reply_markup = callback.message.reply_markup
    
    # Преобразуем клавиатуру в строку для сравнения
    current_markup_str = str(current_reply_markup) if current_reply_markup else ""
    new_markup_str = str(keyboard)
    
    if current_text != history_text or current_markup_str != new_markup_str:
        # Обновляем сообщение с новыми транзакциями и клавиатурой
        await edit_or_send(callback.bot, callback.message, history_text, reply_markup=keyboard, parse_mode="Markdown")
    else:
        # Если контент не изменился, просто отвечаем на callback, чтобы убрать "часики" в интерфейсе
        await safe_answer(callback)
    
    
async def close_history_handler(callback: types.CallbackQuery):
    """Обработчик кнопки закрытия истории транзакций."""
    await safe_answer(callback) # Безопасно отвечаем на callback
    
    # Удаляем сообщение с историей транзакций
    try:
        await callback.message.delete()
    except Exception:
        # Если не удалось удалить сообщение, редактируем его, чтобы убрать клавиатуру
        await edit_or_send(callback.bot, callback.message, "📜 *История транзакций закрыта.*", parse_mode="Markdown")