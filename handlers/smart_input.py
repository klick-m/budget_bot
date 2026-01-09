# -*- coding: utf-8 -*-
# handlers/smart_input.py
import asyncio
import re
from datetime import datetime
from aiogram import Router, types
from aiogram.filters import BaseFilter
from aiogram.fsm.context import FSMContext
from aiogram import F
from typing import Optional

# Импорты из нашей структуры
from config import logger
from models.transaction import TransactionData
from services.input_parser import InputParser
from services.transaction_service import TransactionService
from utils.messages import MSG
from utils.exceptions import TransactionSaveError
from services.transaction_service import TransactionService
from utils.service_wrappers import safe_answer, edit_or_send
from utils.keyboards import get_main_keyboard
from utils.states import TransactionStates
from aiogram.filters import Command, StateFilter


# --- A. ФИЛЬТР И FSM ---
# ----------------------------------------------------------------------



# --- F. УМНЫЙ ВВОД ЧЕРЕЗ FSM ---
# ----------------------------------------------------------------------

async def process_smart_input(message: types.Message, state: FSMContext, transaction_service: TransactionService, current_user: Optional[dict] = None):
    """Обрабатывает умный ввод транзакции в формате 'кофе 300'."""
    await state.clear()
    
    user_input = message.text.strip()
    
    # Используем InputParser для разбора ввода
    parser = InputParser()
    try:
        parsed_data = parser.parse_user_input(user_input)
        if not parsed_data:
            await message.answer(MSG.error_parsing_no_amount)
            return
    except ValueError as e:
        await message.answer(MSG.error_parsing.format(error=e))
        return

    # Service injected
    service = transaction_service
    # Checks removed

    # Загружаем категории для актуальности
    await service.load_categories()

    # Создаем объект транзакции
    # Определяем тип транзакции на основе ключевых слов
    text_lower = user_input.lower()
    transaction_type = "Расход"
    if "доход" in text_lower or "зарплата" in text_lower or "подарок" in text_lower or "возврат" in text_lower:
        transaction_type = "Доход"
    
    # Получаем информацию о пользователе из middleware (передается напрямую)
    if not current_user:
        await message.answer("❌ Ошибка: невозможно получить информацию о пользователе.")
        return

    transaction_data = TransactionData(
        type=transaction_type,
        category="",  # Категория будет определена позже
        amount=parsed_data['amount'],
        comment=parsed_data['comment'],
        username=message.from_user.username or message.from_user.full_name,
        user_id=current_user['telegram_id'],  # Используем ID из middleware
        retailer_name="",
        items_list="",
        payment_info="",
        transaction_dt=datetime.now()
    )

    # Пытаемся уточнить категорию с помощью классификатора
    predicted_category, confidence = service.classifier.predict_category(transaction_data)
    
    # Если уверенность высока, используем предсказанную категорию
    if confidence > 0.0 and predicted_category:
        transaction_data.category = predicted_category
        logger.info(f"Категория уточнена: {predicted_category} (уверенность: {confidence:.2f})")
        confidence_text = f"{confidence:.0%}"
    else:
        # Если категория не определена, устанавливаем как "Прочее"
        transaction_data.category = "Прочее"
        confidence_text = "Низкая уверенность"
    
    # Сохраняем объект транзакции в FSM для последующего использования
    await state.update_data(transaction_data=transaction_data)

    # Показываем сводку и спрашиваем подтверждение
    summary = (f"📋 **Новая транзакция**\n\n"
               f"Тип: **{transaction_data.type}**\n"
               f"Категория: **{transaction_data.category}** (_{confidence_text}_)\n"
               f"Сумма: **{transaction_data.amount}** руб.\n"
               f"Комментарий: *{transaction_data.comment or 'Не указан'}*\n\n"
               f"{MSG.btn_confirm}?")

    keyboard = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [
                types.InlineKeyboardButton(text="✅ Подтвердить", callback_data="confirm_smart_transaction"),
                types.InlineKeyboardButton(text="❌ Отменить", callback_data="cancel_smart_transaction")
            ]
        ]
    )

    await message.answer(summary, reply_markup=keyboard, parse_mode="Markdown")
    await state.set_state(TransactionStates.waiting_for_confirmation)


async def confirm_smart_transaction(callback: types.CallbackQuery, state: FSMContext, transaction_service: TransactionService):
    """Подтверждает и записывает транзакцию из умного ввода."""
    
    await safe_answer(callback)
    
    try:
        # Получаем данные транзакции из FSM
        fsm_data = await state.get_data()
        transaction_data: TransactionData = fsm_data.get('transaction_data')
        
        if not transaction_data:
            await edit_or_send(
                callback.bot,
                callback.message,
                "❌ **Ошибка!** Данные транзакции не найдены.",
                parse_mode="Markdown"
            )
            return

        # Service injected
        service = transaction_service
        # Checks removed

        # Сохраняем транзакцию
        try:
            result = await service.finalize_transaction(transaction_data)
            await edit_or_send(
                callback.bot,
                callback.message,
                MSG.transaction_saved.format(
                    amount=transaction_data.amount,
                    category=transaction_data.category,
                    comment=transaction_data.comment or 'Не указан'
                ),
                parse_mode="Markdown",
                reply_markup=get_main_keyboard()
            )
            # Очищаем состояние
            await state.clear()
        except TransactionSaveError as e:
            await edit_or_send(
                callback.bot,
                callback.message,
                f"{MSG.transaction_save_error.format(error=e)}",
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Ошибка при сохранении транзакции: {e}")
            await edit_or_send(
                callback.bot,
                callback.message,
                f"{MSG.transaction_save_error.format(error=e)}",
                parse_mode="Markdown"
            )
    except Exception as e:
        logger.error(f"Неожиданная ошибка в confirm_smart_transaction: {e}")
        try:
            await edit_or_send(
                callback.bot,
                callback.message,
                f"{MSG.unexpected_error.format(error=e)}",
                parse_mode="Markdown"
            )
        except Exception:
            # Если даже edit_or_send не сработал, просто логируем
            logger.error(f"Не удалось отправить сообщение об ошибке: {e}")


async def cancel_smart_transaction(callback: types.CallbackQuery, state: FSMContext):
    """Отменяет ввод транзакции из умного ввода."""
    
    await safe_answer(callback)
    
    await state.clear()
    
    await edit_or_send(
        callback.bot,
        callback.message,
        MSG.transaction_cancelled,
        parse_mode="Markdown",
        reply_markup=get_main_keyboard()
    )


# --- РЕГИСТРАЦИЯ ХЕНДЛЕРОВ ---
# ----------------------------------------------------------------------

def register_smart_input_handlers(dp: Router):
    """Регистрирует хендлеры для умного ввода транзакций"""
    # Список текстов кнопок, которые нужно игнорировать в умном вводе
    main_buttons = ["💸 Добавить транзакцию", "📜 История транзакций", "🧪 Проверить Sheets"]
    
    # FSM для умного ввода: только если текст не команда, не кнопка и нет активного состояния
    dp.message.register(
        process_smart_input,
        F.text,
        ~F.text.startswith("/"),
        ~F.text.in_(main_buttons),
        StateFilter(None)
    )
    
    # Callback-хендлеры для подтверждения
    dp.callback_query.register(confirm_smart_transaction, F.data == "confirm_smart_transaction", TransactionStates.waiting_for_confirmation)
    dp.callback_query.register(cancel_smart_transaction, F.data == "cancel_smart_transaction", TransactionStates.waiting_for_confirmation)