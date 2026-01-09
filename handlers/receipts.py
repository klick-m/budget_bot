# -*- coding: utf-8 -*-
# handlers/receipts.py
import asyncio
import re
from datetime import datetime
from aiogram import Router, types
from aiogram.filters import BaseFilter
from aiogram import Bot
from aiogram.types import BotCommand, ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram import F

# Импорты из нашей структуры
from config import CATEGORY_STORAGE, logger, SHEET_WRITE_TIMEOUT
from models.transaction import TransactionData, CheckData
from dataclasses import dataclass
from typing import Optional, Dict, Any
from utils.exceptions import SheetWriteError, CheckApiTimeout, CheckApiRecognitionError, TransactionSaveError
from utils.service_wrappers import safe_answer, edit_or_send, clean_previous_kb
from utils.keyboards import get_main_keyboard
from sheets.client import get_latest_transactions
from services.repository import TransactionRepository
from services.input_parser import InputParser
from services.transaction_service import TransactionService
from utils.messages import MSG
from aiogram.filters import Command
import aiohttp


# --- A. ФИЛЬТР И FSM ---
# ----------------------------------------------------------------------



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


from utils.states import TransactionStates


# --- D. ХЕНДЛЕР ЧЕКОВ (СЛОЖНЫЙ) ---
# ----------------------------------------------------------------------

async def handle_photo(message: types.Message, state: FSMContext, data: dict, transaction_service: TransactionService):
    await state.clear()
    
    try:
        # Определяем файл для скачивания
        if message.photo:
            # Проверяем размер фото (ограничим максимальный размер файла в 5 МБ)
            if message.photo[-1].file_size and message.photo[-1].file_size > 5 * 1024 * 1024:
                await message.answer(MSG.error_file_too_big)
                return
            file_object = message.photo[-1]
        elif message.document and message.document.mime_type and message.document.mime_type.startswith('image'):
            # Проверяем размер документа
            if message.document.file_size and message.document.file_size > 5 * 1024 * 1024:
                await message.answer(MSG.error_file_too_big)
                return
            file_object = message.document
        else:
            return

        status_msg = await message.answer(MSG.receipt_sending_to_api)
        
        # 0. Загружаем категории из Google Sheets с кэшированием, чтобы использовать актуальные ключевые слова
        # Загрузка происходит с кэшированием, поэтому не будет частых обращений к API
        # Service injected
        service = transaction_service
        # Checks removed
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
            await edit_or_send(message.bot, status_msg, f"❌ {MSG.receipt_processing_failed} {e}\nПопробуйте ввести вручную: /new_transaction")
            return
        except ValueError as e:
            await edit_or_send(message.bot, status_msg, f"❌ {e}. Введите вручную: /new_transaction")
            return

        # Получаем информацию о пользователе из middleware
        current_user = data.get('current_user')
        if not current_user:
            await edit_or_send(message.bot, status_msg, "❌ Ошибка: невозможно получить информацию о пользователе.")
            return

        # 3. Обработка данных чека через TransactionService
        try:
            transaction = await service.process_check_data(parsed_data, message.from_user.username or message.from_user.full_name, current_user['telegram_id'])  # Используем ID из middleware
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
            user_id=current_user['telegram_id'],  # Используем ID из middleware
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
            await state.set_state(TransactionStates.choosing_category_after_check)
            
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
            
            await state.set_state(TransactionStates.confirming_auto_check)

            keyboard = types.InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        types.InlineKeyboardButton(text="✅ Подтвердить", callback_data="confirm_auto_check"),
                        types.InlineKeyboardButton(text="✏️ Изм. Категорию", callback_data="change_category")
                    ],
                    [
                        types.InlineKeyboardButton(text="✂️ Разделить чек", callback_data="split_check"),
                        types.InlineKeyboardButton(text="❌ Отменить", callback_data="cancel_check")
                    ]
                ]
            )
            
            summary = (f"🧾 **Чек успешно распознан**\n\n"
                       f"Сумма: **{parsed_data.amount}** руб.\n"
                       f"{check_date_preview}"
                       f"Продавец: *{parsed_data.retailer_name}*\n"
                       f"Категория: **{predicted_category}** (_{confidence:.0%}_)\n\n"
                       f"{items_preview}")
            
            await edit_or_send(message.bot, status_msg, summary, reply_markup=keyboard, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Неожиданная ошибка в handle_photo: {e}")
        try:
            await message.answer(f"❌ **Критическая ошибка при обработке чека:** {e}")
        except Exception:
            # Если даже ответить не получилось, просто логируем
            logger.error(f"Не удалось отправить сообщение об ошибке в handle_photo: {e}")


# --- E. ХЕНДЛЕРЫ FSM (Ввод данных) ---
# ----------------------------------------------------------------------

async def process_category_choice_after_check(callback: types.CallbackQuery, state: FSMContext, bot: Bot):
    
    await safe_answer(callback) # <--- ИСПОЛЬЗУЕМ ОБЕРТКУ safe_answer
    
    try:
        new_category = callback.data.split('_')[1]
        data = await state.get_data()
        
        # Сохраняем новую категорию и переходим в состояние подтверждения
        await state.update_data(category=new_category)
        await state.set_state(TransactionStates.confirming_check)
        
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
        
        # Кнопки для подтверждения
        keyboard = types.InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    types.InlineKeyboardButton(text="✅ Подтвердить", callback_data="confirm_check"),
                    types.InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_check")
                ],
                [
                    types.InlineKeyboardButton(text="✂️ Разделить чек", callback_data="split_check")
                ]
            ]
        )
        
        await edit_or_send(
            bot,
            callback.message,
            summary,
            parse_mode="Markdown",
            reply_markup=keyboard
        )
    except Exception as e:
        logger.error(f"Ошибка в process_category_choice_after_check: {e}")
        try:
            await edit_or_send(
                bot,
                callback.message,
                f"❌ **Ошибка при выборе категории:** {e}",
                parse_mode="Markdown"
            )
        except Exception:
            logger.error(f"Не удалось отправить сообщение об ошибке в process_category_choice_after_check: {e}")


async def process_edit_category(callback: types.CallbackQuery, state: FSMContext, bot: Bot):
    """Переводит пользователя в режим выбора категории для авто-распознанного чека."""
    
    await safe_answer(callback)
    
    try:
        data = await state.get_data()
        transaction_type = data.get('type', 'Расход')
        category_list = CATEGORY_STORAGE.expense if transaction_type == "Расход" else CATEGORY_STORAGE.income
        
        # Переходим в состояние выбора категории
        await state.set_state(TransactionStates.choosing_category_after_check)
        
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
    except Exception as e:
        logger.error(f"Ошибка в process_edit_category: {e}")
        try:
            await edit_or_send(
                bot,
                callback.message,
                f"❌ **Ошибка при редактировании категории:** {e}",
                parse_mode="Markdown"
            )
        except Exception:
            logger.error(f"Не удалось отправить сообщение об ошибке в process_edit_category: {e}")


async def process_cancel_check(callback: types.CallbackQuery, state: FSMContext, bot: Bot):
    """Отменяет обработку чека."""
    await safe_answer(callback)
    
    # Сбрасываем состояние
    await state.clear()
    
    try:
        await edit_or_send(bot, callback.message, f"❌ {MSG.transaction_cancelled}", reply_markup=get_main_keyboard())
    except Exception as e:
         # Игнорируем ошибки при редактировании сообщения
         logger.error(f"Не удалось отправить сообщение об отмене чека: {e}")


async def process_confirm_check(callback: types.CallbackQuery, state: FSMContext, bot: Bot, data: dict, transaction_service: TransactionService):
    """Подтверждает и записывает транзакцию из чека после выбора категории вручную."""
    await safe_answer(callback)
    
    try:
        data = await state.get_data()
        
        # Получаем информацию о пользователе из middleware
        current_user = data.get('current_user')
        if not current_user:
            await edit_or_send(
                bot,
                callback.message,
                "❌ Ошибка: невозможно получить информацию о пользователе.",
                parse_mode="Markdown"
            )
            return

        # Создаем объект транзакции
        transaction_data = TransactionData(
            type=data.get('type', 'Расход'),
            category=data['category'],
            amount=data['amount'],
            comment=data.get('comment', '').replace('|', '\n• '),
            username=callback.from_user.username or callback.from_user.full_name,
            user_id=current_user['telegram_id'],  # Используем ID из middleware
            retailer_name=data.get('retailer_name', ''),
            items_list=data.get('items_list', ''),
            payment_info=data.get('payment_info', ''),
            transaction_dt=data.get('transaction_dt') or datetime.now()
        )
        
        service = transaction_service
        try:
            result = await service.finalize_transaction(transaction_data)
            
            await edit_or_send(
                bot,
                callback.message,
                f"✅ **Чек успешно записан!**\n\n"
                f"Сумма: **{transaction_data.amount}** руб.\n"
                f"Категория: **{transaction_data.category}**\n"
                f"Комментарий: *{transaction_data.comment or 'Нет'}*",
                parse_mode="Markdown",
                reply_markup=get_main_keyboard()
            )
            # Если была выбрана категория вручную, обучаем классификатор
            if data.get('retailer_name') or data.get('items_list'):
                await service.add_keywords_for_transaction(
                    transaction_data.category,
                    data.get('retailer_name', ''),
                    data.get('items_list', '')
                )
            await state.clear()
        except TransactionSaveError as e:
            await edit_or_send(
                bot,
                callback.message,
                f"❌ **Ошибка записи:** {e}",
                parse_mode="Markdown"
            )
            
    except Exception as e:
        logger.error(f"Ошибка в process_confirm_check: {e}")
        await edit_or_send(bot, callback.message, f"❌ **Ошибка:** {e}")


async def process_confirm_auto_check(callback: types.CallbackQuery, state: FSMContext, bot: Bot, data: dict, transaction_service: TransactionService):
    """Подтверждает и записывает автоматически распознанный чек."""
    await safe_answer(callback)
    
    try:
        data = await state.get_data()
        
        # Получаем информацию о пользователе из middleware
        current_user = data.get('current_user')
        if not current_user:
            await edit_or_send(
                bot,
                callback.message,
                "❌ Ошибка: невозможно получить информацию о пользователе.",
                parse_mode="Markdown"
            )
            return

        # Создаем объект транзакции
        transaction_data = TransactionData(
            type=data.get('type', 'Расход'),
            category=data['category'],
            amount=data['amount'],
            comment=data.get('comment', '').replace('|', '\n• '),
            username=callback.from_user.username or callback.from_user.full_name,
            user_id=current_user['telegram_id'],  # Используем ID из middleware
            retailer_name=data.get('retailer_name', ''),
            items_list=data.get('items_list', ''),
            payment_info=data.get('payment_info', ''),
            transaction_dt=data.get('transaction_dt') or datetime.now()
        )
        
        service = transaction_service
        try:
            result = await service.finalize_transaction(transaction_data)
            
            await edit_or_send(
                bot,
                callback.message,
                f"✅ **Чек успешно записан!**\n\n"
                f"Сумма: **{transaction_data.amount}** руб.\n"
                f"Категория: **{transaction_data.category}**\n"
                f"Продавец: *{transaction_data.retailer_name}*",
                parse_mode="Markdown",
                reply_markup=get_main_keyboard()
            )
            await state.clear()
        except TransactionSaveError as e:
            await edit_or_send(
                bot,
                callback.message,
                f"❌ **Ошибка записи:** {e}",
                parse_mode="Markdown"
            )
            
    except Exception as e:
        logger.error(f"Ошибка в process_confirm_auto_check: {e}")
        await edit_or_send(bot, callback.message, f"❌ **Ошибка:** {e}")


# --- E. ЛОГИКА РАЗДЕЛЕНИЯ ЧЕКА (SPLIT) ---
# ----------------------------------------------------------------------

async def start_splitting_check(callback: types.CallbackQuery, state: FSMContext):
    """Начинает процесс разделения чека."""
    await safe_answer(callback)
    
    data = await state.get_data()
    # CheckData хранится в "плоском" виде в FSM
    if not data or 'items' not in data:
        await edit_or_send(callback.bot, callback.message, "❌ Ошибка: данные чека отсутствуют.")
        return

    # Восстанавливаем объекты CheckItem из словарей, если они там есть
    items_raw = data.get('items', [])
    if not items_raw:
        await edit_or_send(callback.bot, callback.message, "❌ Ошибка: в чеке нет списка товаров для разделения.")
        return

    # Если items_raw - это список словарей, преобразуем обратно в объекты (для удобства типизации, хоть и не обязательно)
    # Но в FSM мы будем хранить индексы.
    
    # Инициализируем сессию разделения
    split_session = {
        'original_items': items_raw, # Список всех товаров (dict)
        'remaining_indices': list(range(len(items_raw))), # Индексы доступных товаров
        'current_selection': [], # Индексы, выбранные для текущей группы
        'completed_groups': [] # Список сформированных транзакций (dict: sum, items, category)
    }
    
    await state.update_data(split_session=split_session)
    await state.set_state(TransactionStates.splitting_items)
    
    await show_splitting_ui(callback, state)


async def show_splitting_ui(callback: types.CallbackQuery, state: FSMContext):
    """Отображает интерфейс выбора товаров."""
    from utils.split_keyboards import get_items_keyboard
    from models.transaction import CheckItem
    
    data = await state.get_data()
    session = data.get('split_session')
    items_raw = session['original_items']
    remaining_indices = session['remaining_indices']
    current_selection = set(session['current_selection'])
    
    # Формируем список оставшихся товаров для отображения
    # Нам нужно отобразить только те, что в remaining_indices
    # Но callback должен знать реальный индекс в original_items
    
    # Чтобы не усложнять, покажем ВСЕ товары, но те что уже распределены (не в remaining), будут скрыты или помечены
    # Проще: показываем только remaining items.
    
    display_items = []
    # Картируем локальный индекс списка display_items на реальный индекс original_items
    display_map = {} 
    
    for real_idx in remaining_indices:
        item_dict = items_raw[real_idx]
        item = CheckItem(**item_dict) 
        display_items.append(item)
        display_map[len(display_items)-1] = real_idx
        
    await state.update_data(display_map=display_map)
    
    # Выбранные индексы для отображения (локальные)
    local_selected = set()
    for local_idx, real_idx in display_map.items():
        if real_idx in current_selection:
            local_selected.add(local_idx)

    keyboard = get_items_keyboard(display_items, local_selected)
    
    total_left = sum(items_raw[i]['sum'] for i in remaining_indices)
    current_sum = sum(items_raw[i]['sum'] for i in session['current_selection'])
    
    text = (f"✂️ **Разделение чека**\n"
            f"Всего осталось: **{total_left:.2f}** руб.\n"
            f"Выбрано сейчас: **{current_sum:.2f}** руб.\n\n"
            f"👇 Отметьте товары для **Группы {len(session['completed_groups']) + 1}**:")
            
    await edit_or_send(callback.bot, callback.message, text, reply_markup=keyboard, parse_mode="Markdown")


async def toggle_split_item(callback: types.CallbackQuery, state: FSMContext):
    """Переключает выбор товара."""
    # Получаем локальный индекс из callback data: toggle_item_0
    try:
        local_idx = int(callback.data.split('_')[-1])
    except ValueError:
        return

    data = await state.get_data()
    display_map = data.get('display_map', {})
    # display_map ключи - строки, так как из JSON
    real_idx = display_map.get(str(local_idx))
    
    if real_idx is None:
        if isinstance(display_map, dict): # попробуем int ключи
             real_idx = display_map.get(local_idx)
    
    if real_idx is None:
        await safe_answer(callback, "Ошибка индекса")
        return

    session = data.get('split_session')
    current_selection = set(session['current_selection'])
    
    if real_idx in current_selection:
        current_selection.remove(real_idx)
    else:
        current_selection.add(real_idx)
        
    session['current_selection'] = list(current_selection)
    await state.update_data(split_session=session)
    
    # Обновляем UI без ответа (просто перерисовка)
    await show_splitting_ui(callback, state)
    await safe_answer(callback)


async def confirm_split_group_items(callback: types.CallbackQuery, state: FSMContext):
    """Переход к выбору категории для группы."""
    await safe_answer(callback)
    data = await state.get_data()
    session = data.get('split_session')
    
    if not session['current_selection']:
        await safe_answer(callback, "Выберите хотя бы один товар!", show_alert=True)
        return

    # Переходим к выбору категории
    from utils.split_keyboards import get_categories_inline_keyboard
    keyboard = get_categories_inline_keyboard(CATEGORY_STORAGE.expense)
    
    current_sum = sum(session['original_items'][i]['sum'] for i in session['current_selection'])
    
    text = (f"📂 **Группа {len(session['completed_groups']) + 1}** сформирована.\n"
            f"Сумма: **{current_sum:.2f}** руб.\n"
            f"Выберите категорию:")
            
    await edit_or_send(callback.bot, callback.message, text, reply_markup=keyboard, parse_mode="Markdown")
    await state.set_state(TransactionStates.splitting_choose_category)


async def process_split_category_choice(callback: types.CallbackQuery, state: FSMContext, transaction_service: TransactionService):
    """Обрабатывает выбор категории для группы сплита."""
    await safe_answer(callback)
    category = callback.data.split('_', 1)[1]
    
    data = await state.get_data()
    session = data.get('split_session')
    
    # 1. Сохраняем группу
    selected_indices = session['current_selection']
    original_items = session['original_items']
    
    group_items = [original_items[i] for i in selected_indices]
    group_sum = sum(item['sum'] for item in group_items)
    group_items_str = " | ".join([item['name'] for item in group_items])
    
    session['completed_groups'].append({
        'category': category,
        'amount': group_sum,
        'items': group_items,
        'items_str': group_items_str
    })
    
    # 2. Удаляем выбранные из оставшихся
    session['remaining_indices'] = [i for i in session['remaining_indices'] if i not in selected_indices]
    session['current_selection'] = [] # Очищаем выбор
    
    await state.update_data(split_session=session)
    
    # 3. Проверяем, осталось ли что-то
    if not session['remaining_indices']:
        # ВСЕ РАСПРЕДЕЛЕНО - ФИНАЛИЗАЦИЯ
        await finalize_split_transactions(callback, state, transaction_service)
    else:
        # ЕЩЕ ЕСТЬ ТОВАРЫ - ПРОДОЛЖАЕМ
        await state.set_state(TransactionStates.splitting_items)
        await show_splitting_ui(callback, state)


async def finalize_split_transactions(callback: types.CallbackQuery, state: FSMContext, data: dict, transaction_service: TransactionService):
    """Сохраняет все транзакции из сплита."""
    data = await state.get_data()
    session = data.get('split_session')
    
    check_data_raw = data
    from models.transaction import CheckData
    # Восстанавливаем общие данные чека
    # Используем model_validate или просто создаем, но нужно учесть, что некоторые поля могут быть лишними
    # Проще взять из словаря поля
    
    # check_base = CheckData(**check_data_raw) # Может упасть из-за лишних полей в FSM
    # Создадим "базовый" объект руками для надежности
    
    class SimpleCheckBase:
        def __init__(self, d):
            self.retailer_name = d.get('retailer_name', '')
            self.payment_info = d.get('payment_info', '')
            self.transaction_datetime = d.get('transaction_dt') or datetime.now()
            
    check_base = SimpleCheckBase(check_data_raw) 
    
    count = 0
    errors = []
    
    for group in session['completed_groups']:
        try:
            # Получаем информацию о пользователе из middleware
            current_user = data.get('current_user')
            if not current_user:
                await edit_or_send(
                    callback.bot,
                    callback.message,
                    "❌ Ошибка: невозможно получить информацию о пользователе.",
                    parse_mode="Markdown"
                )
                return

            # Создаем транзакцию
            transaction = TransactionData(
                type="Расход", # В чеках обычно расход
                category=group['category'],
                amount=group['amount'],
                comment=group['items_str'][:100], # Ограничим длину комментария
                username=callback.from_user.username or callback.from_user.full_name,
                user_id=current_user['telegram_id'],  # Используем ID из middleware
                retailer_name=check_base.retailer_name,
                items_list=group['items_str'],
                payment_info=check_base.payment_info,
                transaction_dt=check_base.transaction_datetime
            )
            
            await transaction_service.finalize_transaction(transaction)
            count += 1
        except Exception as e:
            errors.append(f"{group['category']}: {e}")

    # Итог
    if not errors:
        await edit_or_send(callback.bot, callback.message, 
                           f"✅ **Чек успешно разделен!**\nСохранено {count} транзакций.", 
                           parse_mode="Markdown", reply_markup=get_main_keyboard())
    else:
        error_msg = "\n".join(errors)
        await edit_or_send(callback.bot, callback.message, 
                           f"⚠️ **Частично сохранено ({count})**\nОшибки:\n{error_msg}", 
                           parse_mode="Markdown", reply_markup=get_main_keyboard())
    
    await state.clear()


# --- РЕГИСТРАЦИЯ ХЕНДЛЕРОВ ---
# ----------------------------------------------------------------------

def register_receipt_handlers(dp: Router):
    """Регистрирует хендлеры для работы с чеками"""
    # ... (старые хендлеры)
    
    # Хендлер на фото/документ
    dp.message.register(handle_photo, F.photo | F.document)
    
    # Callback для подтверждения чека
    dp.callback_query.register(process_confirm_check, F.data == "confirm_check", TransactionStates.confirming_check)
    dp.callback_query.register(process_cancel_check, F.data == "cancel_check")
    
    # Callback для авто-чека
    dp.callback_query.register(process_confirm_auto_check, F.data == "confirm_auto_check", TransactionStates.confirming_auto_check)
    dp.callback_query.register(process_edit_category, F.data == "change_category", TransactionStates.confirming_auto_check)
    dp.callback_query.register(process_category_choice_after_check, F.data.startswith("checkcat_"), TransactionStates.choosing_category_after_check)
    
    # NEW: Split handlers
    dp.callback_query.register(start_splitting_check, F.data == "split_check")
    dp.callback_query.register(toggle_split_item, F.data.startswith("toggle_item_"), TransactionStates.splitting_items)
    dp.callback_query.register(confirm_split_group_items, F.data == "split_next_step", TransactionStates.splitting_items)
    dp.callback_query.register(process_split_category_choice, F.data.startswith("splitcat_"), TransactionStates.splitting_choose_category)
    dp.callback_query.register(process_confirm_auto_check, F.data == "comment_none", TransactionStates.confirming_auto_check)