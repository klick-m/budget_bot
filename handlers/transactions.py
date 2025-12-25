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
from models.transaction import TransactionData, CheckData
from dataclasses import dataclass
from typing import Optional, Dict, Any
from utils.exceptions import SheetWriteError, CheckApiTimeout, CheckApiRecognitionError
from utils.service_wrappers import safe_answer, edit_or_send, clean_previous_kb
from utils.keyboards import get_history_keyboard, HistoryCallbackData
from sheets.client import get_latest_transactions
from services.repository import TransactionRepository
from services.text_parser import parse_transaction_text
from services.input_parser import InputParser
from services.transaction_service import TransactionService
from services.global_service_locator import get_transaction_service
from aiogram.filters import Command, CommandObject


# --- A. ФИЛЬТР И FSM ---
# ----------------------------------------------------------------------

class AllowedUsersFilter(BaseFilter):
    """Проверяет, является ли отправитель сообщения разрешенным пользователем."""
    async def __call__(self, message: types.Message) -> bool:
        if not ALLOWED_USER_IDS:
             return True # Если список разрешенных ID пуст, разрешаем всем
             
        return message.from_user.id in ALLOWED_USER_IDS

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

class Transaction(StatesGroup):
    choosing_type = State()
    choosing_category = State()
    choosing_category_after_check = State()
    confirming_check = State()  # Подтверждение чека после выбора категории вручно
    confirming_auto_check = State()  # Подтверждение автоматически распознанного чека
    entering_amount = State()
    entering_comment = State()
    editing_draft = State()  # Новое состояние для управления черновиком
    waiting_for_confirmation = State()  # Состояние ожидания подтверждения транзакции
    waiting_for_category_selection = State()  # Состояние ожидания выбора категории


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
            type=data.get('type', ''),
            category=data.get('category', ''),
            amount=data.get('amount', 0.0),
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

    # 2. Используем TransactionService для финализации транзакции
    service = get_transaction_service()
    if service is None:
        logger.error("TransactionService not initialized!")
        await edit_or_send(bot, message_to_edit, "❌ Критическая ошибка: TransactionService не инициализирован.", parse_mode="Markdown")
        await state.clear()
        return
    result = await service.finalize_transaction(transaction)
    
    if result['success']:
        await edit_or_send(bot, message_to_edit, result['summary'], parse_mode="Markdown")
    else:
        await edit_or_send(bot, message_to_edit, f"❌ **Ошибка записи в Google Sheets!** Ошибка: {result['error']}", parse_mode="Markdown")
    
    await state.clear()


# --- C. ХЕНДЛЕРЫ КОМАНД И ОСНОВНЫЕ ФУНКЦИИ ---
# ----------------------------------------------------------------------

async def command_start_handler(message: types.Message, state: FSMContext):
    # 1. Clean previous UI
    await clean_previous_kb(message.bot, state, message.chat.id)
    
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
    
    service = get_transaction_service()
    if service is None:
        logger.error("TransactionService not initialized!")
        await edit_or_send(
            message.bot,
            status_msg,
            text=f"❌ **Ошибка!** TransactionService не инициализирован.",
            parse_mode="Markdown"
        )
        return
    result = await service.finalize_transaction(test_data)
    
    if result['success']:
        await edit_or_send(
            message.bot,
            status_msg,
            text="✅ **Успех!** Тестовая запись успешно добавлена в Google Таблицу.",
            parse_mode="Markdown"
        )
    else:
        await edit_or_send(
            message.bot,
            status_msg,
            text=f"❌ **Ошибка!** Не удалось записать транзакцию: {result['error']}",
            parse_mode="Markdown"
        )


async def new_transaction_handler(message: types.Message, state: FSMContext):
    # 1. Clean previous UI
    await clean_previous_kb(message.bot, state, message.chat.id)
    
    await state.clear()
    
    # Создаем черновик транзакции (все поля будут пустыми/None)
    draft = TransactionDraft()
    await state.update_data(draft=draft.__dict__)
    await state.set_state(Transaction.editing_draft)
    
    # Отправляем сообщение с черновиком и inline-кнопками для редактирования
    await send_draft_message(message, state)

async def send_draft_message(message: types.Message, state: FSMContext):
    """Отправляет или редактирует сообщение с черновиком транзакции"""
    data = await state.get_data()
    draft_dict = data.get('draft', {})
    draft = TransactionDraft(**draft_dict)
    
    # Формируем текст сообщения с черновиком
    draft_text = format_draft_text(draft)
    
    # Создаем inline-кнопки для редактирования
    keyboard = create_draft_inline_keyboard(draft)
    
    await edit_or_send(message.bot, message, text=draft_text, reply_markup=keyboard, parse_mode="Markdown")

def format_draft_text(draft: TransactionDraft) -> str:
    """Форматирует текст черновика транзакции"""
    type_str = f"*Тип:* {draft.type}" if draft.type else "*Тип:* Не указан"
    category_str = f"*Категория:* {draft.category}" if draft.category else "*Категория:* Не указана"
    amount_str = f"*Сумма:* {draft.amount}" if draft.amount else "*Сумма:* Не указана"
    comment_str = f"*Комментарий:* {draft.comment}" if draft.comment else "*Комментарий:* Не указан"
    retailer_str = f"*Продавец:* {draft.retailer_name}" if draft.retailer_name else ""
    items_str = f"*Товары:* {draft.items_list}" if draft.items_list else ""
    payment_str = f"*Оплата:* {draft.payment_info}" if draft.payment_info else ""
    date_str = f"*Дата:* {draft.transaction_dt.strftime('%d.%m.%Y %H:%M')}" if draft.transaction_dt else ""
    
    draft_text = f"📝 *Черновик транзакции*\n\n{type_str}\n{category_str}\n{amount_str}\n{comment_str}"
    if retailer_str:
        draft_text += f"\n{retailer_str}"
    if items_str:
        draft_text += f"\n{items_str}"
    if payment_str:
        draft_text += f"\n{payment_str}"
    if date_str:
        draft_text += f"\n{date_str}"
    
    return draft_text

def create_draft_inline_keyboard(draft: TransactionDraft) -> types.InlineKeyboardMarkup:
    """Создает inline-клавиатуру для редактирования черновика"""
    keyboard_buttons = []
    
    # Кнопки для редактирования полей
    if not draft.type:
        keyboard_buttons.append([types.InlineKeyboardButton(text="✏️ Выбрать тип", callback_data="edit_type")])
    else:
        keyboard_buttons.append([types.InlineKeyboardButton(text="✏️ Изменить тип", callback_data="edit_type")])
    
    if not draft.category:
        keyboard_buttons.append([types.InlineKeyboardButton(text="🏷️ Выбрать категорию", callback_data="edit_category_draft")])
    else:
        keyboard_buttons.append([types.InlineKeyboardButton(text="🏷️ Изменить категорию", callback_data="edit_category_draft")])
    
    if not draft.amount:
        keyboard_buttons.append([types.InlineKeyboardButton(text="💰 Ввести сумму", callback_data="edit_amount")])
    else:
        keyboard_buttons.append([types.InlineKeyboardButton(text="💰 Изменить сумму", callback_data="edit_amount")])
    
    keyboard_buttons.append([types.InlineKeyboardButton(text="💬 Изменить комментарий", callback_data="edit_comment")])
    
    # Кнопка завершения
    if draft.type and draft.category and draft.amount:
        keyboard_buttons.append([types.InlineKeyboardButton(text="✅ Подтвердить и записать", callback_data="confirm_draft")])
    else:
        keyboard_buttons.append([types.InlineKeyboardButton(text="❌ Отменить", callback_data="cancel_draft")])
    
    return types.InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)


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
    
    # 0. Загружаем категории из Google Sheets с кэшированием, чтобы использовать актуальные ключевые слова
    # Загрузка происходит с кэшированием, поэтому не будет частых обращений к API
    service = get_transaction_service()
    if service is None:
        logger.error("TransactionService not initialized!")
        await edit_or_send(message.bot, status_msg, f"❌ Критическая ошибка: TransactionService не инициализирован.")
        return
    await service.load_categories()
    
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

    # 2. Обработка изображения чека через TransactionService
    try:
        parsed_data: CheckData = await service.create_transaction_from_check(image_bytes)
    except (CheckApiTimeout, CheckApiRecognitionError) as e:
        await edit_or_send(message.bot, status_msg, f"❌ Анализ чека не удался. {e}\nПопробуйте ввести вручную: /new_transaction")
        return
    except ValueError as e:
        await edit_or_send(message.bot, status_msg, f"❌ {e}. Введите вручную: /new_transaction")
        return

    # 3. Обработка данных чека через TransactionService
    try:
        transaction = await service.process_check_data(parsed_data, message.from_user.username or message.from_user.full_name)
    except Exception as e:
        await edit_or_send(message.bot, status_msg, f"❌ Ошибка обработки данных чека: {e}")
        return

    # Сохранение данных в FSM
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

    # Используем обработанную транзакцию
    predicted_category = transaction.category
    # Используем уверенность из обработки, но для этого нужно получить её из сервиса
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
    
    # Получаем уверенность из классификатора
    _, confidence = service.classifier.predict_category(temp_transaction)
    
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
    
    # 1. Clean previous UI
    await clean_previous_kb(bot, state, callback.message.chat.id)
    
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
    
    # 2. Send new message with keyboard
    sent_msg = await edit_or_send(
        bot,
        callback.message,
        text=f"Выбран тип: **{transaction_type}**. \nВыберите категорию:",
        parse_mode="Markdown",
        reply_markup=keyboard
    )
    
    # 3. Track new message ID
    if sent_msg:
        await state.update_data(last_kb_msg_id=sent_msg.message_id)


async def process_category_choice(callback: types.CallbackQuery, state: FSMContext, bot: Bot):
    
    await safe_answer(callback) # <--- ИСПОЛЬЗУЕМ ОБЕРТКУ safe_answer
    
    # 1. Clean previous UI
    await clean_previous_kb(bot, state, callback.message.chat.id)
    
    category = callback.data.split('_')[1]
    
    await state.update_data(category=category)
    await state.set_state(Transaction.entering_amount)
    
    # 2. Send new message with keyboard (if any)
    sent_msg = await edit_or_send(
        bot,
        callback.message,
        text=f"Категория: **{category}**. \nТеперь введите **сумму** (только число).",
        parse_mode="Markdown"
    )
    
    # 3. Track new message ID
    if sent_msg:
        await state.update_data(last_kb_msg_id=sent_msg.message_id)


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
    
    # Проверяем, используем ли мы новый флоу с черновиком
    data = await state.get_data()
    if 'draft' in data:
        # Это новый флоу, передаем в соответствующий обработчик
        await handle_amount_entry_draft(message, state, bot)
        return
    
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
    
    # Проверяем, используем ли мы новый флоу с черновиком
    data = await state.get_data()
    if 'draft' in data:
        # Это новый флоу, передаем в соответствующий обработчик
        await handle_comment_entry_draft(message, state, bot)
        return
    
    comment = message.text
    await state.update_data(comment=comment)
    
    # Проверяем, все ли обязательные поля заполнены
    data = await state.get_data()
    transaction_type = data.get('type')
    category = data.get('category')
    amount = data.get('amount')
    
    # Отправляем новое сообщение, чтобы получить ID для редактирования статуса
    status_msg = await message.answer("⏳ **Записываю транзакцию...** Ожидайте.")

    # Проверяем наличие всех обязательных полей перед записью
    if transaction_type and category and amount is not None and amount > 0:
        await finalize_transaction(status_msg, state, bot)
    else:
        # Создаем клавиатуру с кнопкой "Без комментария" для повторного ввода
        keyboard = types.InlineKeyboardMarkup(
            inline_keyboard=[
                [types.InlineKeyboardButton(text="Без комментария", callback_data="comment_none")]
            ]
        )
        await edit_or_send(bot, status_msg, "❌ Не все обязательные поля заполнены. Пожалуйста, продолжайте заполнять транзакцию.", reply_markup=keyboard, parse_mode="Markdown")
        await state.set_state(Transaction.entering_comment)  # Остаемся в текущем состоянии


async def process_comment_skip(callback: types.CallbackQuery, state: FSMContext, bot: Bot):
    
    await safe_answer(callback) # <--- ИСПОЛЬЗУЕМ ОБЕРТКУ safe_answer
    
    # Проверяем, используем ли мы новый флоу с черновиком
    data = await state.get_data()
    if 'draft' in data:
        # Это новый флоу, передаем в соответствующий обработчик
        await handle_comment_skip_draft(callback, state, bot)
        return
    
    if not data.get('comment'):
        await state.update_data(comment="")
    
    # Проверяем, находимся ли мы в состоянии подтверждения чека (нужно добавить ключевые слова)
    current_state = await state.get_state()
    
    if current_state == Transaction.confirming_check:
        # Это подтверждение после выбора категории для чека - добавляем ключевые слова
        new_category = data.get('category')
        retailer_name = data.get('retailer_name', 'Неизвестный Продавец')
        items_list_str = data.get('items_list', '')
        
        # Показываем статус о сохранении ключевых слов
        status_msg = await edit_or_send(
            bot,
            callback.message,
            text=f"⏳ Категория **{new_category}** подтверждена. Запоминаю ключевые слова для будущих чеков...",
            parse_mode="Markdown"
        )
        
        # Используем TransactionService для добавления ключевых слов
        service = get_transaction_service()
        if service is None:
            logger.error("TransactionService not initialized!")
            await edit_or_send(
                bot,
                status_msg,
                text=f"❌ Критическая ошибка: TransactionService не инициализирован.",
                parse_mode="Markdown"
            )
            return
        keywords_added = await service.add_keywords_for_transaction(new_category, retailer_name, items_list_str)
        
        if not keywords_added:
            logger.warning(f"Не удалось добавить ключевые слова для категории {new_category}")
        
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
        service.classifier.train([temp_transaction])
        
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
        
        # Используем TransactionService для обучения классификатора
        service = get_transaction_service()
        if service is None:
            logger.error("TransactionService not initialized!")
            await edit_or_send(
                bot,
                callback.message,
                text=f"❌ Критическая ошибка: TransactionService не инициализирован.",
                parse_mode="Markdown"
            )
            return
        service.classifier.train([temp_transaction])
        
        await edit_or_send(
            bot,
            callback.message,
            text="⏳ **Записываю транзакцию...** Ожидайте.",
            parse_mode="Markdown"
        )
        
        await finalize_transaction(callback.message, state, bot)
    else:
        # Обычное пропускание комментария - проверяем, все ли обязательные поля заполнены
        transaction_type = data.get('type')
        category = data.get('category')
        amount = data.get('amount')
        
        if transaction_type and category and amount is not None and amount > 0:
            await edit_or_send(
                bot,
                callback.message,
                text="⏳ **Записываю транзакцию...** Ожидайте.",
                parse_mode="Markdown"
            )
            
            await finalize_transaction(callback.message, state, bot)
        else:
            # Создаем клавиатуру с кнопкой "Без комментария" для повторного ввода
            keyboard = types.InlineKeyboardMarkup(
                inline_keyboard=[
                    [types.InlineKeyboardButton(text="Без комментария", callback_data="comment_none")]
                ]
            )
            await edit_or_send(bot, callback.message, "❌ Не все обязательные поля заполнены. Пожалуйста, продолжайте заполнять транзакцию.", reply_markup=keyboard, parse_mode="Markdown")
            await state.set_state(Transaction.entering_comment)  # Остаемся в текущем состоянии


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


# --- НОВЫЕ ХЕНДЛЕРЫ ДЛЯ РЕДАКТИРОВАНИЯ ЧЕРНОВИКА ---
# ----------------------------------------------------------------------

async def handle_edit_type(callback: types.CallbackQuery, state: FSMContext, bot: Bot):
    """Обработчик для редактирования типа транзакции"""
    await safe_answer(callback)
    
    keyboard = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [types.InlineKeyboardButton(text="💸 Расход", callback_data="type_Расход")],
            [types.InlineKeyboardButton(text="💰 Доход", callback_data="type_Доход")]
        ]
    )
    await edit_or_send(bot, callback.message, "Выберите тип операции:", reply_markup=keyboard)


async def handle_type_choice(callback: types.CallbackQuery, state: FSMContext, bot: Bot):
    """Обработчик выбора типа транзакции"""
    await safe_answer(callback)
    
    transaction_type = callback.data.split('_')[1]
    
    # Обновляем черновик
    data = await state.get_data()
    draft_dict = data.get('draft', {})
    draft = TransactionDraft(**draft_dict)
    draft.type = transaction_type
    await state.update_data(draft=draft.__dict__)
    
    # Возвращаемся к редактированию черновика
    await send_draft_message(callback.message, state)


async def handle_edit_category_draft(callback: types.CallbackQuery, state: FSMContext, bot: Bot):
    """Обработчик для редактирования категории транзакции"""
    await safe_answer(callback)
    
    data = await state.get_data()
    draft_dict = data.get('draft', {})
    draft = TransactionDraft(**draft_dict)
    
    transaction_type = draft.type or "Расход"  # По умолчанию "Расход" если тип не выбран
    category_list = CATEGORY_STORAGE.expense if transaction_type == "Расход" else CATEGORY_STORAGE.income
    
    if not category_list:
        await edit_or_send(
            bot,
            callback.message,
            text=f"❌ Категории для типа '{transaction_type}' не загружены. Проверьте лист 'Categories'!",
        )
        return

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


async def handle_category_choice_draft(callback: types.CallbackQuery, state: FSMContext, bot: Bot):
    """Обработчик выбора категории транзакции"""
    await safe_answer(callback)
    
    category = callback.data.split('_')[1]
    
    # Обновляем черновик
    data = await state.get_data()
    draft_dict = data.get('draft', {})
    draft = TransactionDraft(**draft_dict)
    draft.category = category
    await state.update_data(draft=draft.__dict__)
    
    # Возвращаемся к редактированию черновика
    await send_draft_message(callback.message, state)


async def handle_edit_amount(callback: types.CallbackQuery, state: FSMContext, bot: Bot):
    """Обработчик для редактирования суммы транзакции"""
    await safe_answer(callback)
    
    await state.set_state(Transaction.entering_amount)
    data = await state.get_data()
    draft_dict = data.get('draft', {})
    draft = TransactionDraft(**draft_dict)
    
    if draft.amount:
        await edit_or_send(
            bot,
            callback.message,
            text=f"Текущая сумма: **{draft.amount}**. Введите новую сумму (только число).",
            parse_mode="Markdown"
        )
    else:
        await edit_or_send(
            bot,
            callback.message,
            text="Введите сумму (только число).",
            parse_mode="Markdown"
        )


async def handle_amount_entry_draft(message: types.Message, state: FSMContext, bot: Bot):
    """Обработчик ввода суммы транзакции для черновика"""
    
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

    # Обновляем черновик
    data = await state.get_data()
    draft_dict = data.get('draft', {})
    draft = TransactionDraft(**draft_dict)
    draft.amount = amount
    await state.update_data(draft=draft.__dict__)
    
    # Возвращаемся к основному состоянию редактирования черновика
    await state.set_state(Transaction.editing_draft)
    await send_draft_message(message, state)


async def handle_edit_comment(callback: types.CallbackQuery, state: FSMContext, bot: Bot):
    """Обработчик для редактирования комментария транзакции"""
    await safe_answer(callback)
    
    await state.set_state(Transaction.entering_comment)
    data = await state.get_data()
    draft_dict = data.get('draft', {})
    draft = TransactionDraft(**draft_dict)
    
    if draft.comment:
        keyboard = types.InlineKeyboardMarkup(
            inline_keyboard=[
                [types.InlineKeyboardButton(text="Без комментария", callback_data="comment_none_draft")]
            ]
        )
        await edit_or_send(
            bot,
            callback.message,
            text=f"Текущий комментарий: **{draft.comment}**. Введите новый комментарий или нажмите 'Без комментария'.",
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
    else:
        keyboard = types.InlineKeyboardMarkup(
            inline_keyboard=[
                [types.InlineKeyboardButton(text="Без комментария", callback_data="comment_none_draft")]
            ]
        )
        await edit_or_send(
            bot,
            callback.message,
            text="Введите комментарий или нажмите 'Без комментария'.",
            reply_markup=keyboard
        )


async def handle_comment_entry_draft(message: types.Message, state: FSMContext, bot: Bot):
    """Обработчик ввода комментария транзакции для черновика"""
    
    comment = message.text

    # Обновляем черновик
    data = await state.get_data()
    draft_dict = data.get('draft', {})
    draft = TransactionDraft(**draft_dict)
    draft.comment = comment
    await state.update_data(draft=draft.__dict__)
    
    # Возвращаемся к основному состоянию редактирования черновика
    await state.set_state(Transaction.editing_draft)
    await send_draft_message(message, state)


async def handle_comment_skip_draft(callback: types.CallbackQuery, state: FSMContext, bot: Bot):
    """Обработчик пропуска комментария для черновика"""
    await safe_answer(callback)
    
    # Обновляем черновик
    data = await state.get_data()
    draft_dict = data.get('draft', {})
    draft = TransactionDraft(**draft_dict)
    draft.comment = ""
    await state.update_data(draft=draft.__dict__)
    
    # Возвращаемся к основному состоянию редактирования черновика
    await state.set_state(Transaction.editing_draft)
    await send_draft_message(callback.message, state)


async def handle_confirm_draft(callback: types.CallbackQuery, state: FSMContext, bot: Bot):
    """Обработчик подтверждения черновика"""
    await safe_answer(callback)
    
    try:
        # Получаем финальный черновик
        data = await state.get_data()
        draft_dict = data.get('draft', {})
        draft = TransactionDraft(**draft_dict)
        
        # Проверяем, все ли обязательные поля заполнены
        if not draft.type or not draft.category or draft.amount is None or draft.amount <= 0:
            await edit_or_send(bot, callback.message, "❌ Не все обязательные поля заполнены. Пожалуйста, продолжайте заполнять транзакцию.", parse_mode="Markdown")
            await state.set_state(Transaction.editing_draft)
            await send_draft_message(callback.message, state)
            return
        
        # Формируем TransactionData из черновика
        transaction = TransactionData(
            type=draft.type or '',
            category=draft.category or '',
            amount=draft.amount or 0.0,
            comment=draft.comment,
            username=callback.from_user.username or callback.from_user.full_name,
            retailer_name=draft.retailer_name or "",
            items_list=draft.items_list or "",
            payment_info=draft.payment_info or "",
            transaction_dt=draft.transaction_dt or datetime.now()
        )
        
        # Отправляем сообщение о записи транзакции
        status_msg = await edit_or_send(bot, callback.message, "⏳ **Записываю транзакцию...** Ожидайте.", parse_mode="Markdown")
        
        # Записываем транзакцию
        await finalize_transaction_draft(status_msg, state, bot, transaction)
    except Exception as e:
        logger.error(f"Ошибка при подтверждении черновика: {e}")
        await edit_or_send(bot, callback.message, f"❌ Произошла ошибка при обработке транзакции: {str(e)}", parse_mode="Markdown")
        await state.set_state(Transaction.editing_draft)
        await send_draft_message(callback.message, state)


async def handle_cancel_draft(callback: types.CallbackQuery, state: FSMContext, bot: Bot):
    """Обработчик отмены черновика"""
    await safe_answer(callback)
    
    await state.clear()
    await edit_or_send(
        bot,
        callback.message,
        text="❌ **Черновик отменен.** Выберите действие на клавиатуре ниже.",
        parse_mode="Markdown",
        reply_markup=get_main_keyboard()
    )


async def finalize_transaction_draft(message_to_edit: types.Message, state: FSMContext, bot: Bot, transaction: TransactionData):
    """Финализирует транзакцию из черновика: записывает в Sheets, отправляет финальное сообщение."""
    
    try:
        # Проверяем обязательные поля перед записью
        if not transaction.type or not transaction.category or transaction.amount <= 0:
            await edit_or_send(bot, message_to_edit, "❌ Не все обязательные поля заполнены. Пожалуйста, продолжайте заполнять транзакцию.", parse_mode="Markdown")
            await state.set_state(Transaction.editing_draft)
            await send_draft_message(message_to_edit, state)
            return
        
        # Используем TransactionService для финализации транзакции
        service = get_transaction_service()
        if service is None:
            logger.error("TransactionService not initialized!")
            await edit_or_send(bot, message_to_edit, f"❌ **Критическая ошибка:** TransactionService не инициализирован.", parse_mode="Markdown")
            await state.clear()
            return
        result = await service.finalize_transaction(transaction)
        
        if result['success']:
            await edit_or_send(bot, message_to_edit, result['summary'], parse_mode="Markdown")
        else:
            await edit_or_send(bot, message_to_edit, f"❌ **Ошибка записи в Google Sheets!** Ошибка: {result['error']}", parse_mode="Markdown")
    
    except Exception as e:
        logger.error(f"Критическая ошибка в finalize_transaction_draft: {e}")
        await edit_or_send(bot, message_to_edit, f"❌ **Критическая ошибка при обработке транзакции:** {e}", parse_mode="Markdown")
    
    finally:
        await state.clear()


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


# --- РЕГИСТРАЦИЯ ХЕНДЛЕРОВ ЧЕРНОВИКА ---
# ----------------------------------------------------------------------

def register_draft_handlers(dp: Dispatcher):
    """Регистрирует хендлеры для работы с черновиками транзакций"""
    # Обработчики inline-кнопок для черновика
    dp.callback_query.register(handle_edit_type, F.data == "edit_type", Transaction.editing_draft, AllowedUsersFilter())
    dp.callback_query.register(handle_type_choice, F.data.startswith("type_"), Transaction.editing_draft, AllowedUsersFilter())
    dp.callback_query.register(handle_edit_category_draft, F.data == "edit_category_draft", Transaction.editing_draft, AllowedUsersFilter())
    dp.callback_query.register(handle_category_choice_draft, F.data.startswith("cat_"), Transaction.editing_draft, AllowedUsersFilter())
    dp.callback_query.register(handle_edit_amount, F.data == "edit_amount", Transaction.editing_draft, AllowedUsersFilter())
    dp.callback_query.register(handle_edit_comment, F.data == "edit_comment", Transaction.editing_draft, AllowedUsersFilter())
    dp.callback_query.register(handle_confirm_draft, F.data == "confirm_draft", Transaction.editing_draft, AllowedUsersFilter())
    dp.callback_query.register(handle_cancel_draft, F.data == "cancel_draft", Transaction.editing_draft, AllowedUsersFilter())
    dp.callback_query.register(handle_comment_skip_draft, F.data == "comment_none_draft", Transaction.entering_comment, AllowedUsersFilter())
    
    # Обработчики ввода текста для черновика
    dp.message.register(handle_amount_entry_draft, Transaction.entering_amount, F.text, AllowedUsersFilter())
    dp.message.register(handle_comment_entry_draft, Transaction.entering_comment, F.text, AllowedUsersFilter())


async def parse_transaction_handler(message: types.Message, state: FSMContext):
    """Handle plain text messages to parse and save transactions."""
    print(f"DEBUG: Handler triggered for: {message.text}")
    text = message.text.strip()
    
    # Parse the transaction text
    parsed = parse_transaction_text(text)
    amount = parsed['amount']
    description = parsed['category']  # raw_category from parser becomes description
    
    # Validate amount
    if amount is None or amount <= 0:
        await message.answer("❌ Не удалось распознать сумму в тексте. Отправьте сообщение в формате 'сумма категория' (например, '300 кофе').")
        return
    
    # Initialize transaction service
    service = get_transaction_service()
    if service is None:
        logger.error("TransactionService not initialized!")
        await message.answer("❌ **Критическая ошибка:** TransactionService не инициализирован.")
        return
    
    # Predict category using the classifier from TransactionService
    # First try to find category by keyword using the keyword dictionary
    keyword_result = service.classifier.get_category_by_keyword(description)
    if keyword_result:
        category, confidence = keyword_result
        logger.info(f"Keyword matching result for '{description}': {category} with confidence {confidence}")
    else:
        # If keyword matching fails, try ML classification
        # Create a temporary transaction for classification
        temp_transaction = TransactionData(
            type='Расход',  # Default type
            category='',
            amount=amount,
            comment=description,
            username=message.from_user.username or message.from_user.full_name,
            retailer_name='',
            items_list='',
            payment_info='',
            transaction_dt=datetime.now()
        )
        
        predicted_category, confidence = service.classifier.predict_category(temp_transaction)
        logger.info(f"ML classification result for '{description}': {predicted_category} with confidence {confidence}")
        
        if confidence > 0.5:  # Use ML prediction if confidence is high enough
            category = predicted_category
        else:
            # If both methods fail, use the raw description and let the classifier validate it
            category = service.classifier.predict(description)  # This will return a valid category or "Другое"
    
    # Store transaction data in FSM state
    await state.update_data(
        amount=amount,
        category=category,
        description=description
    )
    
    # Create confirmation message
    confirmation_text = f"💰 Сумма: {amount}\n" \
                        f"📂 Категория: {category}\n" \
                        f"📝 Описание: {description}\n\n" \
                        f"Сохранить?"
    
    # Create inline keyboard with options
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [
            types.InlineKeyboardButton(text="✅ Сохранить", callback_data="save_tx"),
            types.InlineKeyboardButton(text="📂 Изменить категорию", callback_data="change_cat_tx")
        ],
        [
            types.InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_tx")
        ]
    ])
    
    # Send confirmation message
    await message.answer(confirmation_text, reply_markup=keyboard)
    
    # Set state to waiting for confirmation
    await state.set_state(Transaction.waiting_for_confirmation)


async def smart_input_handler(message: types.Message, state: FSMContext):
    """Handle plain text messages for smart input (without /add command)."""
    text = message.text.strip()
    
    # Initialize the input parser
    parser = InputParser()
    parsed_result = parser.parse_user_input(text)
    
    if not parsed_result:
        # If parsing fails, do nothing to avoid interfering with normal conversation
        return
    
    amount = parsed_result['amount']
    comment = parsed_result['comment']
    
    # Validate amount
    if amount is None or amount <= 0:
        await message.answer("❌ Не удалось распознать сумму в тексте. Отправьте сообщение в формате 'сумма категория' (например, '300 кофе').")
        return
    
    # Initialize transaction service
    service = get_transaction_service()
    if service is None:
        logger.error("TransactionService not initialized!")
        await message.answer("❌ **Критическая ошибка:** TransactionService не инициализирован.")
        return
    
    # If there's a comment, try to classify it to get category
    category = None
    if comment:
        # First try to find category by keyword using the keyword dictionary
        keyword_result = service.classifier.get_category_by_keyword(comment)
        if keyword_result:
            category, confidence = keyword_result
            logger.info(f"Keyword matching result for '{comment}': {category} with confidence {confidence}")
        else:
            # If keyword matching fails, try ML classification
            temp_transaction = TransactionData(
                type='Расход',  # Default type for smart input
                category='',
                amount=amount,
                comment=comment,
                username=message.from_user.username or message.from_user.full_name,
                retailer_name='',
                items_list='',
                payment_info='',
                transaction_dt=datetime.now()
            )
            
            predicted_category, confidence = service.classifier.predict_category(temp_transaction)
            logger.info(f"ML classification result for '{comment}': {predicted_category} with confidence {confidence}")
            
            # If classifier is confident, use predicted category
            if confidence > 0.5:
                category = predicted_category
            else:
                category = None  # Will need to ask user for category
    
    # If we have both amount and a confident category prediction, save directly
    if category:
        # Create transaction with predicted category
        transaction = TransactionData(
            type='Расход',
            category=category,
            amount=amount,
            comment=comment,
            username=message.from_user.username or message.from_user.full_name,
            retailer_name='',
            items_list='',
            payment_info='',
            transaction_dt=datetime.now()
        )
        
        # Finalize transaction directly
        result = await service.finalize_transaction(transaction)
        
        if result['success']:
            await message.answer(result['summary'])
        else:
            await message.answer(f"❌ **Ошибка записи в Google Sheets!** Ошибка: {result['error']}", parse_mode="Markdown")
    else:
        # If we only have amount or category prediction is not confident, ask for category using FSM
        await state.update_data(
            amount=amount,
            comment=comment
        )
        
        # Get available categories
        from config import CATEGORY_STORAGE
        category_list = CATEGORY_STORAGE.expense  # Assuming expense categories for this flow
        
        # Create ReplyKeyboard with available categories
        from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
        
        # Create buttons in rows of 2
        keyboard_buttons = []
        for i in range(0, len(category_list), 2):
            row = [KeyboardButton(text=cat) for cat in category_list[i:i+2]]
            keyboard_buttons.append(row)
        
        # Add a 'Skip' button to allow user to skip category selection
        keyboard_buttons.append([KeyboardButton(text="⏭️ Пропустить")])
        keyboard_buttons.append([KeyboardButton(text="❌ Отмена")])
        
        keyboard = ReplyKeyboardMarkup(
            keyboard=keyboard_buttons,
            resize_keyboard=True,
            one_time_keyboard=True
        )
        
        # Ask user to select a category
        if comment:
            await message.answer(f"Сумма: {amount}\nКомментарий: {comment}\n\nВыберите категорию:", reply_markup=keyboard)
        else:
            await message.answer(f"Сумма: {amount}\n\nВыберите категорию:", reply_markup=keyboard)
        
        # Set state to waiting for category selection
        await state.set_state(Transaction.waiting_for_category_selection)


def register_text_parser_handler(dp: Dispatcher):
    """Register the text parser handler."""
    # Register with a filter to exclude the category selection state
    dp.message.register(parse_transaction_handler, F.text, ~StateFilter(Transaction.waiting_for_category_selection), ~F.text.startswith('/'), AllowedUsersFilter())


def register_smart_input_handler(dp: Dispatcher):
    """Register the smart input handler."""
    # Register with a filter to exclude the category selection state and FSM states
    dp.message.register(smart_input_handler, F.text, ~StateFilter(Transaction.waiting_for_category_selection), ~F.text.startswith('/'), AllowedUsersFilter())


async def handle_save_tx(callback: types.CallbackQuery, state: FSMContext):
    """Handle saving transaction after confirmation."""
    await safe_answer(callback)
    
    # Get transaction data from state
    data = await state.get_data()
    amount = data.get('amount')
    category = data.get('category')
    description = data.get('description')
    user_id = callback.from_user.id
    
    # Initialize transaction service
    service = get_transaction_service()
    if service is None:
        logger.error("TransactionService not initialized!")
        await callback.message.edit_text("❌ **Критическая ошибка:** TransactionService не инициализирован.")
        return
    
    # Create transaction with data from state
    transaction = TransactionData(
        type='Расход',  # Default type for this flow
        category=category,
        amount=amount,
        comment=description,  # Using description as comment
        username=callback.from_user.username or callback.from_user.full_name,
        retailer_name='',
        items_list='',
        payment_info='',
        transaction_dt=datetime.now()
    )
    
    # Finalize transaction using service
    result = await service.finalize_transaction(transaction)
    
    if result['success']:
        await callback.message.edit_text(result['summary'])
    else:
        await callback.message.edit_text(f"❌ **Ошибка записи в Google Sheets!** Ошибка: {result['error']}", parse_mode="Markdown")
    
    # Clear state
    await state.clear()


async def handle_cancel_tx(callback: types.CallbackQuery, state: FSMContext):
    """Handle canceling transaction."""
    await safe_answer(callback)
    
    # Clear state
    await state.clear()
    
    # Edit message to confirm cancellation
    await callback.message.edit_text("❌ Отменено.")


async def handle_change_category(callback: types.CallbackQuery, state: FSMContext):
    """Handle changing category."""
    await safe_answer(callback)
    
    # Get transaction data from state to preserve the comment/description
    data = await state.get_data()
    original_description = data.get('description', '')
    
    # Get available categories
    from config import CATEGORY_STORAGE
    category_list = CATEGORY_STORAGE.expense  # Assuming expense categories for this flow
    
    # Create ReplyKeyboard with available categories
    from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
    
    # Create buttons in rows of 2
    keyboard_buttons = []
    for i in range(0, len(category_list), 2):
        row = [KeyboardButton(text=cat) for cat in category_list[i:i+2]]
        keyboard_buttons.append(row)
    
    # Add a 'Cancel' button
    keyboard_buttons.append([KeyboardButton(text="❌ Отмена")])
    
    keyboard = ReplyKeyboardMarkup(
        keyboard=keyboard_buttons,
        resize_keyboard=True,
        one_time_keyboard=True
    )
    
    # Ask user to select a new category, preserving the original description
    if original_description:
        await callback.message.answer(f"Текущий комментарий: '{original_description}'\n\nВыберите новую категорию:", reply_markup=keyboard)
    else:
        await callback.message.answer("Выберите новую категорию:", reply_markup=keyboard)
    await state.set_state(Transaction.waiting_for_category_selection)


# Add handler for category selection
async def handle_category_selection(message: types.Message, state: FSMContext):
    """Handle category selection from reply keyboard."""
    selected_category = message.text
    
    # Check if user wants to cancel
    if selected_category == "❌ Отмена":
        # Clear the state and send cancellation message
        await state.clear()
        await message.answer("❌ Выбор категории отменен.", reply_markup=get_main_keyboard())
        return
    
    # Check if user wants to skip category
    if selected_category == "⏭️ Пропустить":
        # Get data from state - check both 'comment' and 'description' fields
        data = await state.get_data()
        amount = data.get('amount')
        # Try to get comment from both possible fields
        comment = data.get('comment', '')
        if not comment:
            comment = data.get('description', '')
        
        # Initialize transaction service
        service = get_transaction_service()
        if service is None:
            logger.error("TransactionService not initialized!")
            await message.answer("❌ **Критическая ошибка:** TransactionService не инициализирован.")
            return
        
        # Create transaction with default category
        transaction = TransactionData(
            type='Расход',
            category='Прочее Расход',  # Default category when skipping
            amount=amount,
            comment=comment,
            username=message.from_user.username or message.from_user.full_name,
            retailer_name='',
            items_list='',
            payment_info='',
            transaction_dt=datetime.now()
        )
        
        # Finalize transaction
        result = await service.finalize_transaction(transaction)
        
        if result['success']:
            await message.answer(result['summary'])
        else:
            await message.answer(f"❌ **Ошибка записи в Google Sheets!** Ошибка: {result['error']}", parse_mode="Markdown")
        
        # Clear state
        await state.clear()
        return
    
    # Get available categories to validate selection
    from config import CATEGORY_STORAGE
    available_categories = CATEGORY_STORAGE.expense  # Assuming expense categories for this flow
    
    # Check if selected category is valid
    if selected_category not in available_categories:
        await message.answer("❌ Пожалуйста, выберите категорию из предложенных вариантов.")
        return
    
    # Get the original comment from state data - check both 'comment' and 'description' fields
    data = await state.get_data()
    # Try to get comment from both possible fields
    original_comment = data.get('comment', '')
    if not original_comment:
        original_comment = data.get('description', '')
    amount = data.get('amount')
    
    # Initialize transaction service
    service = get_transaction_service()
    if service is None:
        logger.error("TransactionService not initialized!")
        await message.answer("❌ **Критическая ошибка:** TransactionService не инициализирован.")
        return
    
    # Create transaction with selected category
    transaction = TransactionData(
        type='Расход',
        category=selected_category,
        amount=amount,
        comment=original_comment,
        username=message.from_user.username or message.from_user.full_name,
        retailer_name='',
        items_list='',
        payment_info='',
        transaction_dt=datetime.now()
    )
    
    # Finalize transaction
    result = await service.finalize_transaction(transaction)
    
    if result['success']:
        # Clean up the keyboard before sending the final message
        await clean_previous_kb(message.bot, state, message.chat.id)
        await message.answer(result['summary'])
    else:
        # Clean up the keyboard before sending the error message
        await clean_previous_kb(message.bot, state, message.chat.id)
        await message.answer(f"❌ **Ошибка записи в Google Sheets!** Ошибка: {result['error']}", parse_mode="Markdown")
    
    # Learn from this correction - associate the comment with the selected category
    if original_comment:
        service.classifier.learn_keyword(original_comment, selected_category)
        
        # Notify the user about the learning
        await message.answer(f"✅ Я также запомнил, что '{original_comment}' относится к категории '{selected_category}'.")
    
    # Clear state
    await state.clear()


# Function to send transaction summary (reusable)
async def send_transaction_summary(message: types.Message, state: FSMContext):
    """Send transaction summary and confirmation buttons."""
    # Get the transaction data to create confirmation message
    data = await state.get_data()
    amount = data.get('amount')
    description = data.get('description', '')
    category = data.get('category', 'Не указана')
    
    # Create confirmation message
    confirmation_text = f"💰 Сумма: {amount}\n" \
                        f"📂 Категория: {category}\n" \
                        f"📝 Описание: {description}\n\n" \
                        f"Сохранить?"
    
    # Create inline keyboard with options
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [
            types.InlineKeyboardButton(text="✅ Сохранить", callback_data="save_tx"),
            types.InlineKeyboardButton(text="📂 Изменить категорию", callback_data="change_cat_tx")
        ],
        [
            types.InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_tx")
        ]
    ])
    
    # Send confirmation message with inline keyboard (replacing the reply keyboard)
    await message.answer(confirmation_text, reply_markup=keyboard)
    
    # Set state back to waiting for confirmation
    await state.set_state(Transaction.waiting_for_confirmation)


# Register the new callback handlers
def register_confirmation_handlers(dp: Dispatcher):
    """Register confirmation handlers."""
    dp.callback_query.register(handle_save_tx, F.data == "save_tx", Transaction.waiting_for_confirmation, AllowedUsersFilter())
    dp.callback_query.register(handle_cancel_tx, F.data == "cancel_tx", Transaction.waiting_for_confirmation, AllowedUsersFilter())
    dp.callback_query.register(handle_change_category, F.data == "change_cat_tx", Transaction.waiting_for_confirmation, AllowedUsersFilter())
    # Register the new message handler for category selection
    dp.message.register(handle_category_selection, Transaction.waiting_for_category_selection, F.text, AllowedUsersFilter())
    