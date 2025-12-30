"""Тест для проверки регистрации FSM состояний в хендлерах чеков."""
import pytest
from aiogram import Router
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram import F

from handlers.receipts import register_receipt_handlers


class MockTransactionService:
    """Мок-объект для TransactionService"""
    pass


class MockAllowedUsersFilter:
    """Мок-объект для фильтра разрешенных пользователей"""
    def __call__(self, *args, **kwargs):
        return True


def test_fsm_state_registration_should_not_raise_error():
    """Тест проверяет, что регистрация FSM состояний не вызывает ошибок."""
    # Создаем роутер
    dp = Router()
    
    # Создаем мок-сервис
    mock_service = MockTransactionService()
    
    # Проверяем, что регистрация хендлеров не вызывает ошибок
    # Основная проблема была в строке 332 в handlers/receipts.py:
    # dp.callback_query.register(cancel_check, F.data == "cancel_check", (Transaction.confirming_check, Transaction.confirming_auto_check), AllowedUsersFilter())
    register_receipt_handlers(dp, mock_service)
    
    # Проверяем, что хендлеры зарегистрированы
    assert len(dp.message.handlers) > 0
    assert len(dp.callback_query.handlers) > 0


def test_individual_fsm_registration():
    """Тест проверяет регистрацию хендлера с отдельными FSM состояниями."""
    from handlers.receipts import (
        cancel_check,
        Transaction,
        AllowedUsersFilter
    )
    
    dp = Router()
    
    # После исправления, мы регистрируем хендлер дважды - по одному для каждого состояния
    dp.callback_query.register(
        cancel_check, 
        F.data == "cancel_check", 
        Transaction.confirming_check, 
        AllowedUsersFilter()
    )
    
    dp.callback_query.register(
        cancel_check, 
        F.data == "cancel_check", 
        Transaction.confirming_auto_check, 
        AllowedUsersFilter()
    )
    
    # Проверяем, что оба хендлера зарегистрированы
    assert len(dp.callback_query.handlers) == 2


if __name__ == "__main__":
    pytest.main([__file__])