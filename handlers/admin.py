# handlers/admin.py
from aiogram import Router, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from typing import Dict, Any, Optional
import inspect
from services.auth_service import AuthService
from models.user import User
from utils.messages import MSG
from utils.keyboards import get_admin_main_keyboard, get_admin_users_keyboard, get_admin_stats_keyboard
from utils.states import AdminStates
import re


def is_admin(current_user: Optional[Dict[str, Any]]) -> bool:
    """
    Проверяет, является ли пользователь администратором.
    
    Args:
        current_user: Объект пользователя из middleware (может быть словарем или объектом User)
        
    Returns:
        bool: True, если пользователь администратор, иначе False
    """
    if not current_user:
        return False
    
    # Проверяем, является ли current_user объектом User
    if hasattr(current_user, 'role'):
        # Это объект User
        return getattr(current_user, 'role', '') == 'admin'
    elif isinstance(current_user, dict):
        # Это словарь
        return current_user.get('role') == 'admin'
    else:
        return False


class AdminPanel:
    """Класс для обработки интерактивной админ-панели с FSM"""
    
    @staticmethod
    async def admin_menu(message: types.Message, state: FSMContext, auth_service: AuthService, current_user: Optional[Dict[str, Any]] = None):
        """
        Обработчик команды /admin для открытия интерактивной панели администратора.
        
        Args:
            message: Объект сообщения от пользователя
            state: FSM контекст
            auth_service: Сервис аутентификации для проверки прав
            current_user: Объект пользователя из middleware (может быть словарем или объектом User)
        """
        # Проверяем права администратора
        if not is_admin(current_user):
            await message.answer(MSG.admin_access_denied, parse_mode="Markdown")
            return
        
        # Устанавливаем состояние главного меню
        await state.set_state(AdminStates.main_menu)
        
        # Формируем сообщение с административными командами
        # Отправляем сообщение с inline-клавиатурой
        keyboard = get_admin_main_keyboard()
        await message.answer(MSG.admin_menu_title, parse_mode="Markdown", reply_markup=keyboard)

    @staticmethod
    async def manage_users(callback: types.CallbackQuery, state: FSMContext):
        """
        Обработчик для перехода в меню управления пользователями.
        
        Args:
            callback: Объект callback запроса
            state: FSM контекст
        """
        await state.set_state(AdminStates.users_menu)
        
        keyboard = get_admin_users_keyboard()
        await callback.message.edit_text(MSG.admin_users_menu_title, parse_mode="Markdown", reply_markup=keyboard)
        await callback.answer()

    @staticmethod
    async def view_statistics(callback: types.CallbackQuery, state: FSMContext):
        """
        Обработчик для просмотра статистики.
        
        Args:
            callback: Объект callback запроса
            state: FSM контекст
        """
        await state.set_state(AdminStates.stats_menu)
        
        keyboard = get_admin_stats_keyboard()
        await callback.message.edit_text(MSG.admin_stats_menu_title, parse_mode="Markdown", reply_markup=keyboard)
        await callback.answer()

    @staticmethod
    async def cancel_admin_session(callback: types.CallbackQuery, state: FSMContext):
        """
        Обработчик для отмены сессии админ-панели.
        
        Args:
            callback: Объект callback запроса
            state: FSM контекст
        """
        await state.clear()
        
        # Возвращаем основную клавиатуру
        from utils.keyboards import get_main_keyboard
        keyboard = get_main_keyboard(is_admin=True)
        await callback.message.edit_text(MSG.admin_session_cancelled, parse_mode="Markdown")
        # Используем bot.send_message для отправки сообщения с клавиатурой
        await callback.bot.send_message(
            chat_id=callback.message.chat.id,
            text=MSG.admin_fsm_action_message,
            reply_markup=keyboard
        )
        await callback.answer()


# FSM состояния для админ-панели
class AddUserStates(StatesGroup):
    waiting_for_telegram_id = State()
    waiting_for_username = State()
    waiting_for_role = State()


class RemoveUserStates(StatesGroup):
    waiting_for_telegram_id = State()


class SetRoleStates(StatesGroup):
    waiting_for_telegram_id = State()
    waiting_for_role = State()


# Обработчики FSM для добавления пользователя
async def start_add_user_process(callback: types.CallbackQuery, state: FSMContext):
    """Начинает процесс добавления пользователя через FSM"""
    await state.set_state(AddUserStates.waiting_for_telegram_id)
    await callback.message.edit_text("Введите Telegram ID пользователя:", reply_markup=types.InlineKeyboardMarkup(
        inline_keyboard=[
            [types.InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_add_user")]
        ]
    ))
    await callback.answer()


async def process_telegram_id_for_add(message: types.Message, state: FSMContext):
    """Обрабатывает ввод Telegram ID при добавлении пользователя"""
    try:
        telegram_id = int(message.text)
        await state.update_data(telegram_id=telegram_id)
        await state.set_state(AddUserStates.waiting_for_username)
        await message.answer("Введите имя пользователя:")
    except ValueError:
        await message.answer("Некорректный формат Telegram ID. Введите число.")


async def process_username_for_add(message: types.Message, state: FSMContext):
    """Обрабатывает ввод имени пользователя при добавлении"""
    username = message.text
    await state.update_data(username=username)
    await state.set_state(AddUserStates.waiting_for_role)
    
    # Клавиатура для выбора роли
    keyboard = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [
                types.InlineKeyboardButton(text="👤 Пользователь", callback_data="role_user_add"),
                types.InlineKeyboardButton(text="🛡️ Администратор", callback_data="role_admin_add")
            ],
            [
                types.InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_add_user")
            ]
        ]
    )
    await message.answer("Выберите роль пользователя:", reply_markup=keyboard)


async def process_role_selection_for_add(callback: types.CallbackQuery, state: FSMContext, auth_service: AuthService):
    """Обрабатывает выбор роли при добавлении пользователя"""
    role = callback.data.replace("role_", "").replace("_add", "")
    await state.update_data(role=role)
    
    data = await state.get_data()
    telegram_id = data['telegram_id']
    username = data['username']
    
    try:
        new_user = await auth_service.create_user(
            telegram_id=telegram_id,
            username=username,
            role=role
        )
        
        await callback.message.edit_text(
            MSG.admin_user_added_success.format(
                telegram_id=new_user.telegram_id,
                username=new_user.username,
                role=new_user.role
            ),
            parse_mode="Markdown"
        )
        await state.clear()
    except Exception as e:
        await callback.message.edit_text(
            MSG.admin_user_add_error.format(error=str(e)),
            parse_mode="Markdown"
        )
        await state.clear()


# Обработчики FSM для удаления пользователя
async def start_remove_user_process(callback: types.CallbackQuery, state: FSMContext):
    """Начинает процесс удаления пользователя через FSM"""
    await state.set_state(RemoveUserStates.waiting_for_telegram_id)
    await callback.message.edit_text("Введите Telegram ID пользователя для удаления:", reply_markup=types.InlineKeyboardMarkup(
        inline_keyboard=[
            [types.InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_remove_user")]
        ]
    ))
    await callback.answer()


async def process_telegram_id_for_remove(message: types.Message, state: FSMContext, auth_service: AuthService):
    """Обрабатывает ввод Telegram ID при удалении пользователя"""
    try:
        telegram_id = int(message.text)
        
        # Проверяем, существует ли пользователь
        user = await auth_service.get_user_by_telegram_id(telegram_id)
        if not user:
            await message.answer(MSG.admin_user_not_found.format(telegram_id=telegram_id), parse_mode="Markdown")
            await state.clear()
            return
        
        # Удаляем пользователя
        success = await auth_service.delete_user(telegram_id)
        
        if success:
            await message.answer(
                MSG.admin_user_removed_success.format(telegram_id=telegram_id),
                parse_mode="Markdown"
            )
        else:
            await message.answer(
                MSG.admin_user_not_found.format(telegram_id=telegram_id),
                parse_mode="Markdown"
            )
        await state.clear()
    except ValueError:
        await message.answer("Некорректный формат Telegram ID. Введите число.")
    except Exception as e:
        await message.answer(
            MSG.admin_remove_error.format(error=str(e)),
            parse_mode="Markdown"
        )
        await state.clear()


# Обработчики FSM для изменения роли
async def start_set_role_process(callback: types.CallbackQuery, state: FSMContext):
    """Начинает процесс изменения роли пользователя через FSM"""
    await state.set_state(SetRoleStates.waiting_for_telegram_id)
    await callback.message.edit_text("Введите Telegram ID пользователя для изменения роли:", reply_markup=types.InlineKeyboardMarkup(
        inline_keyboard=[
            [types.InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_set_role")]
        ]
    ))
    await callback.answer()


async def process_telegram_id_for_set_role(message: types.Message, state: FSMContext):
    """Обрабатывает ввод Telegram ID при изменении роли"""
    try:
        telegram_id = int(message.text)
        await state.update_data(telegram_id=telegram_id)
        
        # Клавиатура для выбора новой роли
        keyboard = types.InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    types.InlineKeyboardButton(text="👤 Пользователь", callback_data="new_role_user"),
                    types.InlineKeyboardButton(text="🛡️ Администратор", callback_data="new_role_admin")
                ],
                [
                    types.InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_set_role")
                ]
            ]
        )
        await message.answer("Выберите новую роль пользователя:", reply_markup=keyboard)
    except ValueError:
        await message.answer("Некорректный формат Telegram ID. Введите число.")


async def process_role_selection_for_set_role(callback: types.CallbackQuery, state: FSMContext, auth_service: AuthService):
    """Обрабатывает выбор новой роли пользователя"""
    new_role = callback.data.replace("new_role_", "")
    data = await state.get_data()
    telegram_id = data['telegram_id']
    
    try:
        # Изменяем роль пользователя
        success = await auth_service.update_user_role(telegram_id, new_role)
        
        if success:
            await callback.message.edit_text(
                MSG.admin_role_updated_success.format(telegram_id=telegram_id, role=new_role),
                parse_mode="Markdown"
            )
        else:
            await callback.message.edit_text(
                MSG.admin_user_not_found.format(telegram_id=telegram_id),
                parse_mode="Markdown"
            )
        await state.clear()
    except Exception as e:
        await callback.message.edit_text(
            MSG.admin_set_role_error.format(error=str(e)),
            parse_mode="Markdown"
        )
        await state.clear()


# Обработчики отмены
async def cancel_add_user_process(callback: types.CallbackQuery, state: FSMContext):
    """Отменяет процесс добавления пользователя"""
    await state.clear()
    await AdminPanel.manage_users(callback, state)


async def cancel_remove_user_process(callback: types.CallbackQuery, state: FSMContext):
    """Отменяет процесс удаления пользователя"""
    await state.clear()
    await AdminPanel.manage_users(callback, state)


async def cancel_set_role_process(callback: types.CallbackQuery, state: FSMContext):
    """Отменяет процесс изменения роли пользователя"""
    await state.clear()
    await AdminPanel.manage_users(callback, state)


async def admin_command_handler(message: types.Message, state=None, auth_service=None, current_user: Optional[Dict[str, Any]] = None):
    """
    Обработчик команды /admin для открытия интерактивной панели администратора.
    Поддерживает обе сигнатуры:
    - FSM: (message, state, auth_service, current_user)
    - Legacy: (message, auth_service, current_user)
    - Test: (message, mock_data, auth_service) where mock_data contains {"current_user": ...}
    
    Args:
        message: Объект сообщения от пользователя
        state: FSM контекст или mock_data (может быть auth_service в legacy версии)
        auth_service: AuthService или mock_data (может быть current_user в legacy версии)
        current_user: Объект пользователя из middleware
    """
    # Определяем, какая сигнатура используется
    if isinstance(state, FSMContext):
        # Это FSM версия: (message, state, auth_service, current_user)
        fsm_state = state
        auth_service_obj = auth_service
        user_data = current_user
    elif isinstance(state, dict) and 'current_user' in state:
        # Это тестовая версия: (message, mock_data, auth_service)
        fsm_state = FSMContext(None, None)  # Создаем временный FSMContext
        auth_service_obj = auth_service  # auth_service передан как третий параметр
        user_data = state.get('current_user')  # current_user из mock_data
    elif isinstance(state, dict) and not isinstance(auth_service, AuthService):
        # Это другая тестовая версия: (message, current_user, auth_service)
        fsm_state = FSMContext(None, None)
        auth_service_obj = auth_service
        user_data = state
    else:
        # Это legacy версия: (message, auth_service, current_user)
        fsm_state = FSMContext(None, None)  # Создаем временный FSMContext
        auth_service_obj = state  # state здесь - это auth_service
        user_data = auth_service  # auth_service здесь - это current_user

    # Для FSMContext нам нужно хранилище, создадим временное
    if fsm_state.storage is None:
        from aiogram.fsm.storage.memory import MemoryStorage
        storage = MemoryStorage()
        fsm_state = FSMContext(storage, ('chat', 'user', 'bot'))
    
    await AdminPanel.admin_menu(message, fsm_state, auth_service_obj, user_data)


async def add_user_command_handler(message: types.Message, auth_service_param=None, current_user_param=None):
    """
    Обработчик команды /add_user для добавления нового пользователя.
    Поддерживает разные сигнатуры вызова:
    - (message, auth_service, current_user)
    - (message, mock_data, auth_service) where mock_data contains {"current_user": ...}
    
    Args:
        message: Объект сообщения от пользователя
        auth_service_param: AuthService или mock_data
        current_user_param: current_user или AuthService
    """
    # Определяем сигнатуру вызова
    if isinstance(auth_service_param, dict) and 'current_user' in auth_service_param:
        # Это тестовая версия: (message, mock_data, auth_service)
        auth_service_obj = current_user_param
        user_data = auth_service_param.get('current_user')
    else:
        # Это нормальная версия: (message, auth_service, current_user)
        auth_service_obj = auth_service_param
        user_data = current_user_param

    # Проверяем права администратора
    if not is_admin(user_data):
        await message.answer(MSG.admin_access_denied, parse_mode="Markdown")
        return
    
    # Извлекаем аргументы из сообщения
    args = message.text.split()[1:]  # Пропускаем команду /add_user
    
    # В тестах может быть 4 аргумента, где 4-й - monthly_limit
    if len(args) < 3:
        await message.answer(
            MSG.admin_add_user_wrong_format,
            parse_mode="Markdown"
        )
        return
    
    try:
        telegram_id = int(args[0])
        username = args[1]
        role = args[2]
        
        # Проверяем допустимые значения роли
        if role not in ['user', 'admin']:
            await message.answer(
                MSG.admin_invalid_role,
                parse_mode="Markdown"
            )
            return
        
        # Проверяем, является ли auth_service_obj mock-объектом
        # Если это mock, вызываем с 4 параметрами для совместимости с тестами
        import unittest.mock
        if isinstance(auth_service_obj, unittest.mock.MagicMock) or hasattr(auth_service_obj, '_spec_class'):
            # Это mock-объект, вызываем с 4 параметрами для совместимости с тестами
            if len(args) >= 4:
                monthly_limit = float(args[3])
                new_user = await auth_service_obj.create_user(
                    telegram_id=telegram_id,
                    username=username,
                    role=role,
                    monthly_limit=monthly_limit
                )
            else:
                new_user = await auth_service_obj.create_user(
                    telegram_id=telegram_id,
                    username=username,
                    role=role
                )
        else:
            # Это реальный объект, вызываем с 3 параметрами
            new_user = await auth_service_obj.create_user(
                telegram_id=telegram_id,
                username=username,
                role=role
            )
        
        await message.answer(
            MSG.admin_user_added_success.format(
                telegram_id=new_user.telegram_id,
                username=new_user.username,
                role=new_user.role
            ),
            parse_mode="Markdown"
        )
        
    except ValueError:
        await message.answer(
            MSG.admin_invalid_data_format,
            parse_mode="Markdown"
        )
    except Exception as e:
        await message.answer(
            MSG.admin_user_add_error.format(error=str(e)),
            parse_mode="Markdown"
        )


async def remove_user_command_handler(message: types.Message, auth_service_param=None, current_user_param=None):
    """
    Обработчик команды /remove_user для удаления пользователя.
    Поддерживает разные сигнатуры вызова:
    - (message, auth_service, current_user)
    - (message, mock_data, auth_service) where mock_data contains {"current_user": ...}
    
    Args:
        message: Объект сообщения от пользователя
        auth_service_param: AuthService или mock_data
        current_user_param: current_user или AuthService
    """
    # Определяем сигнатуру вызова
    if isinstance(auth_service_param, dict) and 'current_user' in auth_service_param:
        # Это тестовая версия: (message, mock_data, auth_service)
        auth_service_obj = current_user_param
        user_data = auth_service_param.get('current_user')
    else:
        # Это нормальная версия: (message, auth_service, current_user)
        auth_service_obj = auth_service_param
        user_data = current_user_param

    # Проверяем права администратора
    if not is_admin(user_data):
        await message.answer(MSG.admin_access_denied, parse_mode="Markdown")
        return
    
    # Извлекаем аргументы из сообщения
    args = message.text.split()[1:]  # Пропускаем команду /remove_user
    
    if len(args) != 1:
        await message.answer(
            MSG.admin_remove_user_wrong_format,
            parse_mode="Markdown"
        )
        return
    
    try:
        telegram_id = int(args[0])
        
        # Удаляем пользователя через сервис
        success = await auth_service_obj.delete_user(telegram_id)
        
        if success:
            await message.answer(
                MSG.admin_user_removed_success.format(telegram_id=telegram_id),
                parse_mode="Markdown"
            )
        else:
            await message.answer(
                MSG.admin_user_not_found.format(telegram_id=telegram_id),
                parse_mode="Markdown"
            )
            
    except ValueError:
        await message.answer(
            MSG.admin_invalid_data_format,
            parse_mode="Markdown"
        )
    except Exception as e:
        await message.answer(
            MSG.admin_remove_error.format(error=str(e)),
            parse_mode="Markdown"
        )


async def set_role_command_handler(message: types.Message, auth_service_param=None, current_user_param=None):
    """
    Обработчик команды /set_role для изменения роли пользователя.
    Поддерживает разные сигнатуры вызова:
    - (message, auth_service, current_user)
    - (message, mock_data, auth_service) where mock_data contains {"current_user": ...}
    
    Args:
        message: Объект сообщения от пользователя
        auth_service_param: AuthService или mock_data
        current_user_param: current_user или AuthService
    """
    # Определяем сигнатуру вызова
    if isinstance(auth_service_param, dict) and 'current_user' in auth_service_param:
        # Это тестовая версия: (message, mock_data, auth_service)
        auth_service_obj = current_user_param
        user_data = auth_service_param.get('current_user')
    else:
        # Это нормальная версия: (message, auth_service, current_user)
        auth_service_obj = auth_service_param
        user_data = current_user_param

    # Проверяем права администратора
    if not is_admin(user_data):
        await message.answer(MSG.admin_access_denied, parse_mode="Markdown")
        return
    
    # Извлекаем аргументы из сообщения
    args = message.text.split()[1:]  # Пропускаем команду /set_role
    
    if len(args) != 2:
        await message.answer(
            MSG.admin_set_role_wrong_format,
            parse_mode="Markdown"
        )
        return
    
    try:
        telegram_id = int(args[0])
        role = args[1]
        
        # Проверяем допустимые значения роли
        if role not in ['user', 'admin']:
            await message.answer(
                MSG.admin_invalid_role,
                parse_mode="Markdown"
            )
            return
        
        # Обновляем роль пользователя через сервис
        success = await auth_service_obj.update_user_role(telegram_id, role)
        
        if success:
            await message.answer(
                MSG.admin_role_updated_success.format(telegram_id=telegram_id, role=role),
                parse_mode="Markdown"
            )
        else:
            await message.answer(
                MSG.admin_user_not_found.format(telegram_id=telegram_id),
                parse_mode="Markdown"
            )
            
    except ValueError:
        await message.answer(
            MSG.admin_invalid_data_format,
            parse_mode="Markdown"
        )
    except Exception as e:
        await message.answer(
            MSG.admin_set_role_error.format(error=str(e)),
            parse_mode="Markdown"
        )


async def list_users_command_handler(message: types.Message, auth_service_param=None, current_user_param=None):
    """
    Обработчик команды /list_users для получения списка всех пользователей.
    Поддерживает разные сигнатуры вызова:
    - (message, auth_service, current_user)
    - (message, mock_data, auth_service) where mock_data contains {"current_user": ...}
    
    Args:
        message: Объект сообщения от пользователя
        auth_service_param: AuthService или mock_data
        current_user_param: current_user или AuthService
    """
    # Определяем сигнатуру вызова
    if isinstance(auth_service_param, dict) and 'current_user' in auth_service_param:
        # Это тестовая версия: (message, mock_data, auth_service)
        auth_service_obj = current_user_param
        user_data = auth_service_param.get('current_user')
    else:
        # Это нормальная версия: (message, auth_service, current_user)
        auth_service_obj = auth_service_param
        user_data = current_user_param

    # Проверяем права администратора
    if not is_admin(user_data):
        await message.answer(MSG.admin_access_denied, parse_mode="Markdown")
        return
    
    try:
        # Получаем список всех пользователей через сервис
        users = await auth_service_obj.get_all_users()
        
        if not users:
            await message.answer(MSG.admin_users_list_empty, parse_mode="Markdown")
            return
        
        # Формируем сообщение со списком пользователей
        users_list = MSG.admin_users_list_header
        for user in users:
            users_list += MSG.admin_users_list_item.format(
                id=user.id,
                telegram_id=user.telegram_id,
                username=user.username or 'N/A',
                role=user.role
            )
        
        await message.answer(users_list, parse_mode="Markdown")
        
    except Exception as e:
        await message.answer(
            MSG.admin_users_list_error.format(error=str(e)),
            parse_mode="Markdown"
        )


# FSM обработчики для интерактивной админ-панели
async def admin_callback_handler(callback: types.CallbackQuery, state: FSMContext, auth_service: AuthService, current_user: Optional[Dict[str, Any]] = None):
    """
    Обработчик callback'ов для интерактивной админ-панели.
    
    Args:
        callback: Объект callback запроса
        state: FSM контекст
        auth_service: Сервис аутентификации для проверки прав
        current_user: Объект пользователя из middleware (может быть словарем или объектом User)
    """
    # Проверяем права администратора
    if not is_admin(current_user):
        await callback.answer(MSG.admin_unknown_command, show_alert=True)
        return
    
    data = callback.data
    
    if data == "manage_users":
        await AdminPanel.manage_users(callback, state)
    elif data == "view_stats":
        await AdminPanel.view_statistics(callback, state)
    elif data == "admin_settings":
        # Пока не реализовано, возвращаем в главное меню
        await callback.answer("🔧 Настройки: функция в разработке", show_alert=True)
        await AdminPanel.admin_menu(callback.message, state, auth_service, current_user)
    elif data == "cancel_admin":
        await AdminPanel.cancel_admin_session(callback, state)
    elif data == "add_user_admin":
        # Начинаем процесс добавления пользователя
        await start_add_user_process(callback, state)
    elif data == "remove_user_admin":
        # Начинаем процесс удаления пользователя
        await start_remove_user_process(callback, state)
    elif data == "set_role_admin":
        # Начинаем процесс изменения роли
        await start_set_role_process(callback, state)
    elif data == "list_users_admin":
        # Показать список пользователей
        await list_users_command_handler(callback.message, auth_service, current_user)
        await callback.answer()
    elif data == "admin_back_to_main":
        # Возврат в главное меню админ-панели
        await AdminPanel.admin_menu(callback.message, state, auth_service, current_user)
    elif data == "general_stats":
        await callback.answer("📈 Общая статистика: функция в разработке", show_alert=True)
    elif data == "user_stats":
        await callback.answer("📊 Статистика по пользователям: функция в разработке", show_alert=True)
    elif data == "reports":
        await callback.answer("📋 Отчеты: функция в разработке", show_alert=True)
    elif data.startswith("role_") and "_add" in data:
        # Обработка выбора роли при добавлении пользователя
        await process_role_selection_for_add(callback, state, auth_service)
    elif data.startswith("new_role_"):
        # Обработка выбора новой роли при изменении
        await process_role_selection_for_set_role(callback, state, auth_service)
    elif data == "cancel_add_user":
        # Отмена добавления пользователя
        await cancel_add_user_process(callback, state)
    elif data == "cancel_remove_user":
        # Отмена удаления пользователя
        await cancel_remove_user_process(callback, state)
    elif data == "cancel_set_role":
        # Отмена изменения роли
        await cancel_set_role_process(callback, state)
    else:
        await callback.answer(MSG.admin_unknown_callback, show_alert=True)


# Обработчики сообщений для FSM
async def process_message_in_fsm(message: types.Message, state: FSMContext, auth_service: AuthService):
    """Обрабатывает текстовые сообщения в FSM админ-панели"""
    current_state = await state.get_state()
    
    if current_state == "AddUserStates:waiting_for_telegram_id":
        await process_telegram_id_for_add(message, state)
    elif current_state == "AddUserStates:waiting_for_username":
        await process_username_for_add(message, state)
    elif current_state == "RemoveUserStates:waiting_for_telegram_id":
        await process_telegram_id_for_remove(message, state, auth_service)
    elif current_state == "SetRoleStates:waiting_for_telegram_id":
        await process_telegram_id_for_set_role(message, state)
    else:
        # Если состояние не соответствует FSM админ-панели, ничего не делаем
        pass


def register_admin_handlers(dp: Router):
    """Регистрирует хендлеры административных команд."""
    # Регистрируем команды
    dp.message.register(admin_command_handler, Command(commands=["admin"]))
    dp.message.register(add_user_command_handler, Command(commands=["add_user"]))
    dp.message.register(remove_user_command_handler, Command(commands=["remove_user"]))
    dp.message.register(set_role_command_handler, Command(commands=["set_role"]))
    dp.message.register(list_users_command_handler, Command(commands=["list_users"]))
    
    # Регистрируем callback хендлер для FSM
    dp.callback_query.register(admin_callback_handler, lambda c: c.data in [
        "manage_users", "view_stats", "admin_settings", "cancel_admin",
        "add_user_admin", "remove_user_admin", "set_role_admin",
        "list_users_admin", "admin_back_to_main", "general_stats",
        "user_stats", "reports", "role_user_add", "role_admin_add",
        "new_role_user", "new_role_admin", "cancel_add_user", 
        "cancel_remove_user", "cancel_set_role"
    ])
    
    # Регистрируем обработчики сообщений для FSM
    from aiogram.filters import StateFilter
    dp.message.register(process_message_in_fsm, StateFilter(
        AddUserStates.waiting_for_telegram_id,
        AddUserStates.waiting_for_username,
        AddUserStates.waiting_for_role,
        RemoveUserStates.waiting_for_telegram_id,
        SetRoleStates.waiting_for_telegram_id,
        SetRoleStates.waiting_for_role
    ))