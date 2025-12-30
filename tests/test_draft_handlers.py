import pytest
from aiogram import Router
from aiogram.fsm.state import State, StatesGroup
from handlers.manual import register_draft_handlers


class TestStatesGroup(StatesGroup):
    editing_draft = State()


def test_register_draft_handlers_exists():
    """Тест: функция register_draft_handlers существует"""
    assert callable(register_draft_handlers)


def test_register_draft_handlers_registers_handlers():
    """Тест: функция register_draft_handlers регистрирует хендлеры в роутере"""
    router = Router()
    
    # Проверяем количество хендлеров до регистрации
    initial_message_handlers_count = len(router.message.handlers)
    initial_callback_handlers_count = len(router.callback_query.handlers)
    
    # Регистрируем хендлеры
    register_draft_handlers(router)
    
    # Проверяем, что количество хендлеров увеличилось
    final_message_handlers_count = len(router.message.handlers)
    final_callback_handlers_count = len(router.callback_query.handlers)
    
    # Должны быть зарегистрированы как минимум 2 callback хендлера (edit_type, edit_category_draft)
    assert final_callback_handlers_count > initial_callback_handlers_count, \
        "Callback handlers were not registered"
    
    # Проверяем, что количество message хендлеров не изменилось (draft handlers - это callback хендлеры)
    assert final_message_handlers_count == initial_message_handlers_count, \
        "Message handlers count changed, but draft handlers should only register callback handlers"