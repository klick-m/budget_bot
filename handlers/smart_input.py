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
from config import logger, CATEGORY_STORAGE
from models.transaction import TransactionData
from services.input_parser import InputParser
from services.transaction_service import TransactionService
from utils.messages import MSG
from utils.exceptions import TransactionSaveError
from services.transaction_service import TransactionService
from utils.service_wrappers import safe_answer, edit_or_send
from utils.keyboards import get_main_keyboard, get_categories_keyboard
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
        user_id=current_user.telegram_id,  # Используем ID из middleware
        retailer_name="",
        items_list="",
        payment_info="",
        transaction_dt=datetime.now()
    )

    # Пытаемся уточнить категорию с помощью классификатора
    # Но если тип транзакции "Доход", то используем одну из стандартных категорий дохода
    if transaction_type == "Доход":
        # Если это доход, используем первую доступную категорию дохода или "Доход" по умолчанию
        income_categories = CATEGORY_STORAGE.income
        if income_categories:
            # Пытаемся определить наиболее подходящую категорию дохода на основе ключевых слов
            matched_category = None
            text_lower = user_input.lower()
            
            # Проверяем наличие ключевых слов в тексте для определения категории дохода
            for cat in income_categories:
                if cat.lower() in text_lower:
                    matched_category = cat
                    break
            
            # Если не нашли подходящую категорию по ключевым словам, используем первую
            if matched_category:
                transaction_data.category = matched_category
                confidence_text = "Категория дохода определена"
            else:
                # Используем первую доступную категорию дохода
                transaction_data.category = income_categories[0]
                confidence_text = "Категория дохода по умолчанию"
        else:
            # Если категории дохода не определены, используем "Доход"
            transaction_data.category = "Доход"
            confidence_text = "Категория дохода"
    else:
        # Для расходов используем обычную логику классификатора
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
    comment_display = getattr(transaction_data, 'comment', '') or 'Не указан'
    summary = MSG.smart_input_transaction_summary.format(transaction_data=transaction_data, confidence_text=confidence_text, btn_confirm=MSG.btn_confirm, comment_display=comment_display)

    keyboard = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [
                types.InlineKeyboardButton(text="✅ Подтвердить", callback_data="confirm_smart_transaction"),
                types.InlineKeyboardButton(text="❌ Отменить", callback_data="cancel_smart_transaction")
            ],
            [
                types.InlineKeyboardButton(text="🏷️ Изменить категорию", callback_data="edit_category_smart_transaction")
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
                    comment=getattr(transaction_data, 'comment', '') or 'Не указан'
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


async def edit_category_smart_transaction(callback: types.CallbackQuery, state: FSMContext):
    """Позволяет изменить категорию во время подтверждения транзакции из умного ввода."""
    
    await safe_answer(callback)
    
    # Получаем текущий тип транзакции из FSM
    data = await state.get_data()
    transaction_data = data.get('transaction_data')
    
    if not transaction_data:
        await edit_or_send(
            callback.bot,
            callback.message,
            "❌ **Ошибка!** Данные транзакции не найдены.",
            parse_mode="Markdown"
        )
        return
    
    transaction_type = transaction_data.type
    
    # Проверяем, что тип транзакции не None
    if not transaction_type:
        await edit_or_send(
            callback.bot,
            callback.message,
            "❌ **Ошибка!** Не удалось определить тип транзакции.",
            parse_mode="Markdown"
        )
        return
    
    # Создаем клавиатуру с категориями
    keyboard = get_categories_keyboard(transaction_type)
    
    await edit_or_send(
        callback.bot,
        callback.message,
        MSG.select_category_prompt,
        reply_markup=keyboard,
        parse_mode="Markdown"
    )
    
    # Переходим в состояние ожидания выбора категории
    await state.set_state(TransactionStates.waiting_for_category_selection)


async def process_category_selection_smart_input(message: types.Message, state: FSMContext):
    """Обрабатывает выбор новой категории во время умного ввода транзакции."""
    
    user_input_raw = message.text.strip()
    user_input = user_input_raw.lower()
    
    if user_input in [MSG.btn_cancel.lower(), "отмена", "cancel"]:
        await state.clear()
        await message.answer(MSG.transaction_cancelled, reply_markup=get_main_keyboard())
        return

    # Получаем тип транзакции из FSM
    data = await state.get_data()
    transaction_data = data.get('transaction_data')
    
    if not transaction_data:
        await message.answer("❌ **Ошибка!** Данные транзакции не найдены.")
        return

    transaction_type = transaction_data.type
    
    # Проверяем, что тип транзакции не None
    if not transaction_type:
        await message.answer("❌ **Ошибка!** Не удалось определить тип транзакции.")
        return
    
    # Проверяем, что выбранная категория соответствует типу
    from config import CATEGORY_STORAGE
    valid_categories = CATEGORY_STORAGE.income if transaction_type == "Доход" else CATEGORY_STORAGE.expense
    if user_input_raw not in valid_categories:
        await message.answer(MSG.please_select_category_for_type.format(transaction_type=transaction_type))
        return

    # Обновляем категорию в данных FSM
    transaction_data.category = user_input_raw
    await state.update_data(transaction_data=transaction_data)
    
    # Возвращаемся к подтверждению транзакции с обновленной информацией
    comment_display = getattr(transaction_data, 'comment', '') or 'Не указан'
    summary = MSG.smart_input_transaction_summary.format(transaction_data=transaction_data, confidence_text="Изменена вручную", btn_confirm=MSG.btn_confirm, comment_display=comment_display)
    
    keyboard = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [
                types.InlineKeyboardButton(text="✅ Подтвердить", callback_data="confirm_smart_transaction"),
                types.InlineKeyboardButton(text="❌ Отменить", callback_data="cancel_smart_transaction")
            ],
            [
                types.InlineKeyboardButton(text="🏷️ Изменить категорию", callback_data="edit_category_smart_transaction")
            ]
        ]
    )
    
    await message.answer(summary, reply_markup=keyboard, parse_mode="Markdown")
    await state.set_state(TransactionStates.waiting_for_confirmation)


async def process_category_selection_smart_input_callback(callback: types.CallbackQuery, state: FSMContext):
    """Обрабатывает выбор новой категории через callback (когда пользователь нажимает на кнопку с категорией) для умного ввода."""
    
    await safe_answer(callback)
    
    # Извлекаем название категории из callback.data
    category = callback.data.replace("cat_", "")
    
    # Получаем тип транзакции из FSM
    data = await state.get_data()
    transaction_data = data.get('transaction_data')
    
    if not transaction_data:
        await edit_or_send(
            callback.bot,
            callback.message,
            "❌ **Ошибка!** Данные транзакции не найдены.",
            parse_mode="Markdown"
        )
        return

    transaction_type = transaction_data.type
    
    # Проверяем, что тип транзакции не None
    if not transaction_type:
        await edit_or_send(
            callback.bot,
            callback.message,
            "❌ **Ошибка!** Не удалось определить тип транзакции.",
            parse_mode="Markdown"
        )
        return
    
    # Проверяем, что выбранная категория соответствует типу
    from config import CATEGORY_STORAGE
    valid_categories = CATEGORY_STORAGE.income if transaction_type == "Доход" else CATEGORY_STORAGE.expense
    if category not in valid_categories:
        await edit_or_send(
            callback.bot,
            callback.message,
            MSG.please_select_category_for_type.format(transaction_type=transaction_type),
            parse_mode="Markdown"
        )
        return

    # Обновляем категорию в данных FSM
    transaction_data.category = category
    await state.update_data(transaction_data=transaction_data)
    
    # Возвращаемся к подтверждению транзакции с обновленной информацией
    comment_display = getattr(transaction_data, 'comment', '') or 'Не указан'
    summary = MSG.smart_input_transaction_summary.format(transaction_data=transaction_data, confidence_text="Изменена вручную", btn_confirm=MSG.btn_confirm, comment_display=comment_display)
    
    keyboard = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [
                types.InlineKeyboardButton(text="✅ Подтвердить", callback_data="confirm_smart_transaction"),
                types.InlineKeyboardButton(text="❌ Отменить", callback_data="cancel_smart_transaction")
            ],
            [
                types.InlineKeyboardButton(text="🏷️ Изменить категорию", callback_data="edit_category_smart_transaction")
            ]
        ]
    )
    
    await edit_or_send(
        callback.bot,
        callback.message,
        summary,
        reply_markup=keyboard,
        parse_mode="Markdown"
    )
    await state.set_state(TransactionStates.waiting_for_confirmation)


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
    # Добавляем обработчик для изменения категории
    dp.callback_query.register(edit_category_smart_transaction, F.data == "edit_category_smart_transaction", TransactionStates.waiting_for_confirmation)
    # Добавляем обработчик для выбора категории через callback
    dp.callback_query.register(process_category_selection_smart_input_callback, F.data.startswith("cat_"), TransactionStates.waiting_for_category_selection)
    
    # Регистрируем обработчик для изменения категории в состоянии ожидания выбора категории
    dp.message.register(process_category_selection_smart_input, TransactionStates.waiting_for_category_selection)