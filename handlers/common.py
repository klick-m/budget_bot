# -*- coding: utf-8 -*-
# handlers/common.py
import asyncio
import re
from datetime import datetime
from aiogram import Router, types
from aiogram.filters import BaseFilter
from aiogram import Bot
from aiogram.types import BotCommand, ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram import F

# Импорт из нашей структуры
from config import ALLOWED_USER_IDS, CATEGORY_STORAGE, logger
from models.transaction import TransactionData, CheckData
from dataclasses import dataclass
from typing import Optional, Dict, Any
from utils.exceptions import SheetWriteError, TransactionSaveError
from utils.service_wrappers import safe_answer, edit_or_send, clean_previous_kb
from utils.keyboards import get_main_keyboard, get_history_keyboard, HistoryCallbackData
from sheets.client import get_latest_transactions
from services.repository import TransactionRepository
from services.transaction_service import TransactionService
from services.transaction_service import TransactionService
from utils.messages import MSG
from aiogram.filters import Command, or_f


# --- A. ФИЛЬТР И FSM ---
# ----------------------------------------------------------------------

class AllowedUsersFilter(BaseFilter):
    """Проверяет, является ли отправитель сообщения разрешенным пользователем."""
    async def __call__(self, message: types.Message) -> bool:
        if not ALLOWED_USER_IDS:
             return True # Если список разрешенных ID пуст, разрешаем всем
             
        return message.from_user.id in ALLOWED_USER_IDS


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


async def test_sheets_handler(message: types.Message, transaction_service: TransactionService):
    status_msg = await message.answer(MSG.test_transaction_start)

    test_data = TransactionData(
        type='ТЕСТ',
        category='Связь',
        amount=1.00,
        comment='Проверка связи с ботом',
        username=message.from_user.username or message.from_user.full_name,
        user_id=message.from_user.id,
        transaction_dt=datetime.now()
    )
    
    # service = get_transaction_service() -> transaction_service injected
    service = transaction_service
    # if service is None check removed as DI ensures it

    # if service is None check removed as DI ensures it
 
    try:
        result = await service.finalize_transaction(test_data)
        await edit_or_send(
            message.bot,
            status_msg,
            text=MSG.test_transaction_success,
            parse_mode="Markdown"
        )
    except TransactionSaveError as e:
        await edit_or_send(
            message.bot,
            status_msg,
            text=f"{MSG.transaction_save_error.format(error=e)}",
            parse_mode="Markdown"
        )
    except Exception as e:
        await edit_or_send(
            message.bot,
            status_msg,
            text=f"{MSG.transaction_save_error.format(error=e)}",
            parse_mode="Markdown"
        )


# --- КОМАНДА /undo ---
# ----------------------------------------------------------------------


async def undo_command_handler(message: types.Message):
    """Обработчик команды /undo для удаления последних транзакций."""
    # Получаем последние 3 транзакции
    user_id = str(message.from_user.id)
    transactions = await get_latest_transactions(user_id=user_id, limit=3, offset=0)
    
    if not transactions:
        await message.answer("📋 У вас пока нет транзакций для отмены.")
        return

    # Формируем сообщение с транзакциями
    undo_text = "🗑 *Выберите транзакцию для удаления:*\n\n"
    for i, transaction in enumerate(transactions, 1):
        # Обрезаем комментарий до 20 символов, если он длиннее
        comment = transaction['comment'] if transaction['comment'] else 'Нет'
        if len(comment) > 20:
            comment = comment[:20] + "..."
        undo_text += (
            f"{i}. *{transaction['date']} {transaction['time']}*\n"
            f"   Тип: {transaction['type']}\n"
            f"   Категория: {transaction['category']}\n"
            f"   Сумма: {transaction['amount']} руб.\n"
            f"   Комментарий: {comment}\n\n"
        )
    
    # Создаем inline-клавиатуру с кнопками удаления
    keyboard = create_undo_keyboard(transactions)

    await message.answer(undo_text, reply_markup=keyboard, parse_mode="Markdown")


def create_undo_keyboard(transactions: list) -> types.InlineKeyboardMarkup:
    """Создает inline-клавиатуру с кнопками для удаления транзакций."""
    keyboard = []
    
    # Создаем кнопки для каждой транзакции
    for i, transaction in enumerate(transactions, 1):
        # Создаем уникальный идентификатор на основе даты, времени и суммы
        transaction_id = f"{transaction['date']}_{transaction['time']}_{transaction['amount']}"
        button = types.InlineKeyboardButton(
            text=f"🗑 Удалить {i}",
            callback_data=f"undo_{transaction_id}"
        )
        # Добавляем кнопки в ряды по 2
        if i % 2 == 1:
            keyboard.append([button])
        else:
            keyboard[-1].append(button)
    
    # Добавляем кнопку "Закрыть"
    close_button = [types.InlineKeyboardButton(text="❌ Закрыть", callback_data="close_undo")]
    keyboard.append(close_button)
    
    return types.InlineKeyboardMarkup(inline_keyboard=keyboard)


async def undo_callback_handler(callback: types.CallbackQuery, transaction_service: TransactionService):
    """Обработчик нажатия кнопок удаления транзакций."""
    await safe_answer(callback)  # Безопасно отвечаем на callback
    
    try:
        # Проверяем, что callback_data начинается с "undo_"
        if not callback.data.startswith("undo_"):
            return
        
        # Извлекаем информацию о транзакции из callback_data
        transaction_info = callback.data[5:]  # Убираем "undo_" из начала
        if not transaction_info:
            await callback.message.answer(MSG.undo_invalid_format)
            return
        
        # Разбиваем информацию о транзакции
        parts = transaction_info.split("_")
        if len(parts) < 3:
            await callback.message.answer(MSG.undo_invalid_format)
            return
        
        transaction_date = parts[0]
        transaction_time = parts[1]
        transaction_amount = parts[2]
        
        # Получаем TransactionService через DI
        service = transaction_service
        # Check removed

        # Удаляем транзакцию через сервис
        result = await service.delete_transaction_by_details(
            user_id=str(callback.from_user.id),
            date=transaction_date,
            time=transaction_time,
            amount=float(transaction_amount)
        )
        
        if result['success']:
            await edit_or_send(
                callback.bot,
                callback.message,
                MSG.undo_success.format(date=transaction_date, time=transaction_time, amount=transaction_amount),
                parse_mode="Markdown"
            )
        else:
            await edit_or_send(
                callback.bot,
                callback.message,
                text=f"{MSG.undo_error.format(error=result['error'])}",
                parse_mode="Markdown"
            )
            
    except Exception as e:
        logger.error(f"Ошибка при удалении транзакции: {e}")
        try:
            await edit_or_send(
                callback.bot,
                callback.message,
                f"❌ Ошибка при удалении транзакции: {str(e)}",
                parse_mode="Markdown"
            )
        except Exception:
            # Если даже edit_or_send не сработал, просто логируем
            logger.error(f"Не удалось отправить сообщение об ошибке: {e}")


async def close_undo_handler(callback: types.CallbackQuery):
    """Обработчик кнопки закрытия меню отмены транзакций."""
    await safe_answer(callback) # Безопасно отвечаем на callback
    
    # Удаляем сообщение с меню отмены
    try:
        await callback.message.delete()
    except Exception:
        # Если не удалось удалить сообщение, редактируем его, чтобы убрать клавиатуру
        try:
            await edit_or_send(
                callback.bot,
                callback.message,
                "🗑 Меню отмены транзакций закрыто.",
                parse_mode="Markdown"
            )
        except Exception:
            # Если edit_or_send тоже не сработал, просто логируем
            logger.error("Не удалось удалить или отредактировать сообщение в close_undo_handler")


# --- КОМАНДА ИСТОРИИ ТРАНЗАКЦИЙ ---
# ----------------------------------------------------------------------

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
        try:
            await edit_or_send(
                callback.bot,
                callback.message,
                "📋 У вас пока нет транзакций в истории.",
                parse_mode="Markdown"
            )
        except Exception:
            logger.error("Не удалось отправить сообщение об отсутствии транзакций")
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
        try:
            await edit_or_send(callback.bot, callback.message, history_text, reply_markup=keyboard, parse_mode="Markdown")
        except Exception:
            logger.error("Не удалось обновить сообщение с историей транзакций")
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
        try:
            await edit_or_send(
                callback.bot,
                callback.message,
                "📜 *История транзакций закрыта.*",
                parse_mode="Markdown"
            )
        except Exception:
            # Если edit_or_send тоже не сработал, просто логируем
            logger.error("Не удалось удалить или отредактировать сообщение в close_history_handler")


# --- РЕГИСТРАЦИЯ ХЕНДЛЕРОВ ---
# ----------------------------------------------------------------------

def register_common_handlers(dp: Router):
    """Регистрирует общые хендлеры"""
    # Регистрируем команды
    dp.message.register(command_start_handler, Command(commands=["start"]), AllowedUsersFilter())
    dp.message.register(test_sheets_handler, or_f(Command(commands=["test_sheets"]), F.text == "🧪 Проверить Sheets"), AllowedUsersFilter())
    dp.message.register(undo_command_handler, Command(commands=["undo"]), AllowedUsersFilter())
    dp.message.register(history_command_handler, or_f(Command(commands=["history"]), F.text == "📜 История транзакций"), AllowedUsersFilter())
    
    # Регистрируем обработчики callback'ов для undo
    dp.callback_query.register(undo_callback_handler, F.data.startswith("undo_"), AllowedUsersFilter())
    dp.callback_query.register(close_undo_handler, F.data == "close_undo", AllowedUsersFilter())
    
    # Регистрируем обработчики callback'ов для истории
    dp.callback_query.register(history_callback_handler, HistoryCallbackData.filter(), AllowedUsersFilter())
    dp.callback_query.register(close_history_handler, F.data == "close_history", AllowedUsersFilter())