# -*- coding: utf-8 -*-
# handlers/manual.py
import asyncio
import re
from datetime import datetime
from aiogram import Router, types
from aiogram.filters import BaseFilter
from aiogram import Bot
from aiogram.types import BotCommand, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram import F

# Импорты из нашей структуры
from config import CATEGORY_STORAGE, logger, SHEET_WRITE_TIMEOUT
from models.transaction import TransactionData
from dataclasses import dataclass
from typing import Optional, Dict, Any
from utils.exceptions import SheetWriteError, TransactionSaveError
from utils.service_wrappers import safe_answer, edit_or_send, clean_previous_kb
from utils.keyboards import get_main_keyboard
from sheets.client import get_latest_transactions
from services.repository import TransactionRepository
from services.input_parser import InputParser
from services.transaction_service import TransactionService
from utils.messages import MSG

from aiogram.filters import Command, or_f


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


# --- B. ОБРАБОТКА FSM (Ручной ввод) ---
# ----------------------------------------------------------------------

async def start_manual_transaction(message: types.Message, state: FSMContext, transaction_service: TransactionService):
    """Начинает процесс ручного ввода транзакции."""
    await state.clear()
    
    # Проверяем, есть ли доступ к сервису
    # Service injected
    service = transaction_service
    # Checks removed
    
    # Загружаем категории для актуальности
    await service.load_categories()
    
    # Уточняем тип транзакции
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text=MSG.btn_income),
                KeyboardButton(text=MSG.btn_expense)
            ],
            [
                KeyboardButton(text=MSG.btn_cancel)
            ]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    
    await message.answer(
        MSG.choose_type,
        reply_markup=keyboard,
        parse_mode="Markdown"
    )
    await state.set_state(TransactionStates.choosing_type)


async def process_type_selection(message: types.Message, state: FSMContext):
    """Обрабатывает выбор типа транзакции."""
    user_input = message.text.strip().lower()
    
    if user_input in [MSG.btn_cancel.lower(), "отмена", "cancel"]:
        await state.clear()
        await message.answer(MSG.transaction_cancelled, reply_markup=get_main_keyboard())
        return

    transaction_type = None
    if "доход" in user_input or "💰" in user_input:
        transaction_type = "Доход"
    elif "расход" in user_input or "🛒" in user_input:
        transaction_type = "Расход"
    
    if not transaction_type:
        await message.answer("❌ Пожалуйста, выберите тип транзакции с помощью клавиатуры.")
        return

    # Сохраняем тип в FSM
    await state.update_data(transaction_type=transaction_type)
    
    # Показываем клавиатуру с категориями
    categories = CATEGORY_STORAGE.income if transaction_type == "Доход" else CATEGORY_STORAGE.expense
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=cat) for cat in categories[i:i + 2]]
            for i in range(0, len(categories), 2)
        ] + [
            [KeyboardButton(text=MSG.btn_cancel)]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    
    await message.answer(
        MSG.choose_category.format(type=transaction_type),
        reply_markup=keyboard,
        parse_mode="Markdown"
    )
    await state.set_state(TransactionStates.choosing_category)


async def process_category_selection(message: types.Message, state: FSMContext):
    """Обрабатывает выбор категории."""
    user_input_raw = message.text.strip()
    user_input = user_input_raw.lower()
    
    if user_input in [MSG.btn_cancel.lower(), "отмена", "cancel"]:
        await state.clear()
        await message.answer(MSG.transaction_cancelled, reply_markup=get_main_keyboard())
        return

    # Получаем тип транзакции из FSM
    data = await state.get_data()
    transaction_type = data.get('transaction_type')
    
    # Проверяем, что выбранная категория соответствует типу
    valid_categories = CATEGORY_STORAGE.income if transaction_type == "Доход" else CATEGORY_STORAGE.expense
    if user_input_raw not in valid_categories:
        await message.answer(f"❌ Пожалуйста, выберите категорию из списка для типа **{transaction_type}**.")
        return

    # Сохраняем категорию в FSM
    await state.update_data(category=user_input_raw)
    
    # Запрашиваем сумму
    await message.answer(
        MSG.enter_amount.format(category=user_input_raw),
        reply_markup=ReplyKeyboardRemove(),
        parse_mode="Markdown"
    )
    await state.set_state(TransactionStates.entering_amount)


async def process_amount_input(message: types.Message, state: FSMContext):
    """Обрабатывает ввод суммы."""
    user_input_raw = message.text.strip()
    user_input = user_input_raw.lower()
    
    if user_input in ["❌ отмена", "отмена", "cancel"]:
        await state.clear()
        await message.answer("❌ **Ввод транзакции отменен.**", reply_markup=get_main_keyboard())
        return

    try:
        amount = float(user_input_raw.replace(',', '.'))
        if amount <= 0:
            raise ValueError("Сумма должна быть положительной")
    except ValueError:
        await message.answer("❌ Пожалуйста, введите корректную сумму (например, 100.50 или 100).")
        return

    # Сохраняем сумму в FSM
    await state.update_data(amount=amount)
    
    # Запрашиваем комментарий
    await message.answer(
        MSG.enter_comment.format(amount=amount),
        parse_mode="Markdown"
    )
    await state.set_state(TransactionStates.entering_comment)


async def process_comment_input(message: types.Message, state: FSMContext, current_user: Optional[dict] = None):
    """Обрабатывает ввод комментария."""
    user_input_raw = message.text.strip()
    user_input = user_input_raw.lower()
    
    if user_input in ["❌ отмена", "отмена", "cancel"]:
        await state.clear()
        await message.answer("❌ **Ввод транзакции отменен.**", reply_markup=get_main_keyboard())
        return

    comment = user_input_raw
    if user_input.startswith('/skip'):
        comment = ""

    # Сохраняем комментарий в FSM
    await state.update_data(comment=comment)
    
    # Получаем все данные для подтверждения
    data = await state.get_data()
    
    # Получаем информацию о пользователе из middleware (передается напрямую)
    if not current_user:
        await message.answer("❌ Ошибка: невозможно получить информацию о пользователе.")
        return

    transaction_data = TransactionData(
        type=data['transaction_type'],
        category=data['category'],
        amount=data['amount'],
        comment=comment,
        username=message.from_user.username or message.from_user.full_name,
        user_id=current_user.telegram_id,  # Используем ID из middleware
        retailer_name="",
        items_list="",
        payment_info="",
        transaction_dt=datetime.now()
    )
    
    # Сохраняем объект транзакции в FSM для последующего использования
    await state.update_data(transaction_data=transaction_data)
    
    # Показываем сводку и спрашиваем подтверждение
    summary = (f"📋 **Новая транзакция**\n\n"
               f"Тип: **{transaction_data.type}**\n"
               f"Категория: **{transaction_data.category}**\n"
               f"Сумма: **{transaction_data.amount}** руб.\n"
               f"Комментарий: *{transaction_data.comment or 'Не указан'}*\n\n"
               f"✅ Подтвердить и записать?")
    
    keyboard = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [
                types.InlineKeyboardButton(text="✅ Подтвердить", callback_data="confirm_manual_transaction"),
                types.InlineKeyboardButton(text="❌ Отменить", callback_data="cancel_manual_transaction")
            ]
        ]
    )
    
    await message.answer(summary, reply_markup=keyboard, parse_mode="Markdown")
    await state.set_state(TransactionStates.waiting_for_confirmation)


# --- C. ОБРАБОТКА FSM (Подтверждение) ---
# ----------------------------------------------------------------------

async def confirm_manual_transaction(callback: types.CallbackQuery, state: FSMContext, transaction_service: TransactionService):
    """Подтверждает и записывает транзакцию."""
    
    await safe_answer(callback)
    
    try:
        # Получаем данные транзакции из FSM
        data = await state.get_data()
        transaction_data: TransactionData = data.get('transaction_data')
        
        if not transaction_data:
            await edit_or_send(
                callback.bot,
                callback.message,
                "❌ **Ошибка!** Данные транзакции не найдены.",
                parse_mode="Markdown"
            )
            return

        # Получаем сервис для сохранения
        # Service injected
        service = transaction_service
        # Checks removed

        # Сохраняем транзакцию
        try:
            await service.finalize_transaction(transaction_data)
            await edit_or_send(
                callback.bot,
                callback.message,
                f"✅ **Транзакция сохранена!**\n\n"
                f"Сумма: **{transaction_data.amount}** руб.\n"
                f"Категория: **{transaction_data.category}**\n"
                f"Комментарий: *{transaction_data.comment or 'Не указан'}*",
                parse_mode="Markdown",
                reply_markup=get_main_keyboard()
            )
            # Очищаем состояние
            await state.clear()
        except TransactionSaveError as e:
            await edit_or_send(
                callback.bot,
                callback.message,
                f"❌ **Ошибка при сохранении:** {e}",
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Ошибка при сохранении транзакции: {e}")
            await edit_or_send(
                callback.bot,
                callback.message,
                f"❌ **Ошибка при сохранении транзакции:** {e}",
                parse_mode="Markdown"
            )
    except Exception as e:
        logger.error(f"Неожиданная ошибка в confirm_manual_transaction: {e}")
        try:
            await edit_or_send(
                callback.bot,
                callback.message,
                f"❌ **Критическая ошибка:** {e}",
                parse_mode="Markdown"
            )
        except Exception:
            # Если даже edit_or_send не сработал, просто логируем
            logger.error(f"Не удалось отправить сообщение об ошибке: {e}")


async def cancel_manual_transaction(callback: types.CallbackQuery, state: FSMContext):
    """Отменяет ввод транзакции."""
    
    await safe_answer(callback)
    
    await state.clear()
    
    await edit_or_send(
        callback.bot,
        callback.message,
        "❌ **Ввод транзакции отменен.**",
        parse_mode="Markdown",
        reply_markup=get_main_keyboard()
    )


# --- РЕГИСТРАЦИЯ ХЕНДЛЕРОВ ---
# ----------------------------------------------------------------------

def register_manual_handlers(dp: Router):
    """Регистрирует хендлеры для ручного ввода транзакций"""
    # Команда для начала ручного ввода
    dp.message.register(start_manual_transaction, or_f(Command("new_transaction"), F.text == "💸 Добавить транзакцию"))
    
    # FSM для ручного ввода
    dp.message.register(process_type_selection, TransactionStates.choosing_type)
    dp.message.register(process_category_selection, TransactionStates.choosing_category)
    dp.message.register(process_amount_input, TransactionStates.entering_amount)
    dp.message.register(process_comment_input, TransactionStates.entering_comment)
    
    # Callback-хендлеры для подтверждения
    dp.callback_query.register(confirm_manual_transaction, F.data == "confirm_manual_transaction", TransactionStates.waiting_for_confirmation)
    dp.callback_query.register(cancel_manual_transaction, F.data == "cancel_manual_transaction", TransactionStates.waiting_for_confirmation)


def register_draft_handlers(dp: Router):
    """Регистрирует хендлеры для работы с черновиками транзакций"""
    # FSM для работы с черновиками
    dp.callback_query.register(process_edit_type, F.data == "edit_type", TransactionStates.editing_draft)
    dp.callback_query.register(process_edit_category_draft, F.data == "edit_category_draft", TransactionStates.editing_draft)
    dp.callback_query.register(process_edit_amount, F.data == "edit_amount", TransactionStates.editing_draft)
    dp.callback_query.register(process_edit_comment, F.data == "edit_comment", TransactionStates.editing_draft)
    dp.callback_query.register(confirm_draft, F.data == "confirm_draft", TransactionStates.editing_draft)
    dp.callback_query.register(cancel_draft, F.data == "cancel_draft", TransactionStates.editing_draft)


async def process_edit_type(callback: types.CallbackQuery, state: FSMContext):
    """Обработка изменения типа транзакции в черновике"""
    from utils.service_wrappers import safe_answer, edit_or_send
    from utils.keyboards import get_transaction_type_keyboard
    
    await safe_answer(callback)
    
    # Показываем клавиатуру для выбора типа
    keyboard = get_transaction_type_keyboard()
    await edit_or_send(
        callback.bot,
        callback.message,
        "Выберите тип транзакции:",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )


async def process_edit_category_draft(callback: types.CallbackQuery, state: FSMContext):
    """Обработка изменения категории в черновике"""
    from utils.service_wrappers import safe_answer, edit_or_send
    from utils.keyboards import get_categories_keyboard
    
    await safe_answer(callback)
    
    # Получаем текущий тип транзакции из состояния
    data = await state.get_data()
    transaction_type = data.get('transaction_type', 'Расход')
    
    # Показываем клавиатуру для выбора категории
    keyboard = get_categories_keyboard(transaction_type)
    await edit_or_send(
        callback.bot,
        callback.message,
        "Выберите категорию:",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )


async def process_edit_amount(callback: types.CallbackQuery, state: FSMContext):
    """Обработка изменения суммы в черновике"""
    from utils.service_wrappers import safe_answer, edit_or_send
    
    await safe_answer(callback)
    
    await edit_or_send(
        callback.bot,
        callback.message,
        "Введите сумму транзакции:",
        parse_mode="Markdown"
    )


async def process_edit_comment(callback: types.CallbackQuery, state: FSMContext):
    """Обработка изменения комментария в черновике"""
    from utils.service_wrappers import safe_answer, edit_or_send
    
    await safe_answer(callback)
    
    await edit_or_send(
        callback.bot,
        callback.message,
        "Введите комментарий к транзакции:",
        parse_mode="Markdown"
    )


async def confirm_draft(callback: types.CallbackQuery, state: FSMContext, transaction_service: TransactionService, current_user: Optional[dict] = None):
    """Подтверждение и запись черновика транзакции"""
    from utils.service_wrappers import safe_answer, edit_or_send
    # from services.global_service_locator import get_transaction_service # Removed
    from models.transaction import TransactionData
    from datetime import datetime
    
    await safe_answer(callback)
    
    try:
        # Получаем данные черновика из состояния
        data = await state.get_data()
        
        # Проверяем, что все необходимые поля заполнены
        if not (data.get('transaction_type') and data.get('category') and data.get('amount')):
            await edit_or_send(
                callback.bot,
                callback.message,
                "❌ Не все обязательные поля заполнены! Необходимо указать тип, категорию и сумму.",
                parse_mode="Markdown"
            )
            return
         
        # Создаем объект транзакции
        # Получаем информацию о пользователе из middleware (передается напрямую)
        if not current_user:
            await edit_or_send(
                callback.bot,
                callback.message,
                "❌ Ошибка: невозможно получить информацию о пользователе.",
                parse_mode="Markdown"
            )
            return

        transaction_data = TransactionData(
            type=data['transaction_type'],
            category=data['category'],
            amount=data['amount'],
            comment=data.get('comment', ''),
            username=callback.from_user.username or callback.from_user.full_name,
            user_id=current_user.telegram_id,  # Используем ID из middleware
            retailer_name=data.get('retailer_name', ''),
            items_list=data.get('items_list', ''),
            payment_info=data.get('payment_info', ''),
            transaction_dt=datetime.now()
        )
        
        # Получаем сервис для сохранения
        # Service injected
        service = transaction_service
        # Checks removed
        
        # Сохраняем транзакцию
        try:
            await service.finalize_transaction(transaction_data)
            await edit_or_send(
                callback.bot,
                callback.message,
                f"✅ **Транзакция сохранена!**\n\n"
                f"Сумма: **{transaction_data.amount}** руб.\n"
                f"Категория: **{transaction_data.category}**\n"
                f"Комментарий: *{transaction_data.comment or 'Не указан'}*",
                parse_mode="Markdown",
                reply_markup=get_main_keyboard()
            )
            # Очищаем состояние
            await state.clear()
        except TransactionSaveError as e:
            await edit_or_send(
                callback.bot,
                callback.message,
                f"❌ **Ошибка при сохранении:** {e}",
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Ошибка при сохранении транзакции: {e}")
            await edit_or_send(
                callback.bot,
                callback.message,
                f"❌ **Ошибка при сохранении транзакции:** {e}",
                parse_mode="Markdown"
            )
    except Exception as e:
        logger.error(f"Неожиданная ошибка в confirm_draft: {e}")
        try:
            await edit_or_send(
                callback.bot,
                callback.message,
                f"❌ **Критическая ошибка:** {e}",
                parse_mode="Markdown"
            )
        except Exception:
            # Если даже edit_or_send не сработал, просто логируем
            logger.error(f"Не удалось отправить сообщение об ошибке в confirm_draft: {e}")


async def cancel_draft(callback: types.CallbackQuery, state: FSMContext):
    """Отмена черновика транзакции"""
    from utils.service_wrappers import safe_answer, edit_or_send
    
    await safe_answer(callback)
    
    await state.clear()
    
    await edit_or_send(
        callback.bot,
        callback.message,
        "❌ **Черновик отменен.**",
        parse_mode="Markdown",
        reply_markup=get_main_keyboard()
    )