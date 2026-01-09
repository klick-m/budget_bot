# handlers/admin.py
from aiogram import Router, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from typing import Dict, Any, Optional
from services.auth_service import AuthService
from utils.messages import MSG
from utils.keyboards import get_admin_main_keyboard, get_admin_users_keyboard, get_admin_stats_keyboard
from utils.states import AdminStates
import re


def is_admin(current_user: Dict[str, Any]) -> bool:
    """
    Проверяет, является ли пользователь администратором.
    
    Args:
        current_user: Словарь с информацией о пользователе из middleware
        
    Returns:
        bool: True, если пользователь администратор, иначе False
    """
    if not current_user or not isinstance(current_user, dict):
        return False
    return current_user.get('role', 'user') == 'admin'


class AdminPanel:
    """Класс для обработки интерактивной админ-панели с FSM"""
    
    @staticmethod
    async def admin_menu(message: types.Message, state: FSMContext, auth_service: AuthService, current_user: Optional[dict] = None):
        """
        Обработчик команды /admin для открытия интерактивной панели администратора.
        
        Args:
            message: Объект сообщения от пользователя
            state: FSM контекст
            auth_service: Сервис аутентификации для проверки прав
            current_user: Словарь с информацией о пользователе из middleware
        """
        # Проверяем права администратора
        if not is_admin(current_user):
            await message.answer("❌ *Доступ запрещен.*\nТолько администраторы могут использовать эту команду.", parse_mode="Markdown")
            return
        
        # Устанавливаем состояние главного меню
        await state.set_state(AdminStates.main_menu)
        
        # Формируем сообщение с административными командами
        admin_menu = """
🛡 *Панель администратора*

Выберите действие:
        """
        
        # Отправляем сообщение с inline-клавиатурой
        keyboard = get_admin_main_keyboard()
        await message.answer(admin_menu, parse_mode="Markdown", reply_markup=keyboard)

    @staticmethod
    async def manage_users(callback: types.CallbackQuery, state: FSMContext):
        """
        Обработчик для перехода в меню управления пользователями.
        
        Args:
            callback: Объект callback запроса
            state: FSM контекст
        """
        await state.set_state(AdminStates.users_menu)
        
        users_menu = """
👥 *Управление пользователями*

Выберите действие:
        """
        
        keyboard = get_admin_users_keyboard()
        await callback.message.edit_text(users_menu, parse_mode="Markdown", reply_markup=keyboard)
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
        
        stats_menu = """
📊 *Статистика и отчеты*

Выберите тип статистики:
        """
        
        keyboard = get_admin_stats_keyboard()
        await callback.message.edit_text(stats_menu, parse_mode="Markdown", reply_markup=keyboard)
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
        
        cancel_message = """
✅ *Сессия админ-панели завершена*

Вы вышли из режима администрирования.
        """
        
        # Возвращаем основную клавиатуру
        from utils.keyboards import get_main_keyboard
        keyboard = get_main_keyboard(is_admin=True)
        await callback.message.edit_text(cancel_message, parse_mode="Markdown")
        # Используем bot.send_message для отправки сообщения с клавиатурой
        await callback.bot.send_message(
            chat_id=callback.message.chat.id,
            text="👆 Выберите действие:",
            reply_markup=keyboard
        )
        await callback.answer()


async def admin_command_handler(message: types.Message, auth_service: AuthService, current_user: Optional[dict] = None):
    """
    Обработчик команды /admin для открытия панели администратора.
    
    Args:
        message: Объект сообщения от пользователя
        auth_service: Сервис аутентификации для работы с пользователями
        current_user: Словарь с информацией о пользователе из middleware
    """
    # Проверяем права администратора
    if not is_admin(current_user):
        await message.answer("❌ *Доступ запрещен.*\nТолько администраторы могут использовать эту команду.", parse_mode="Markdown")
        return
    
    # Формируем сообщение с административными командами
    admin_menu = """
🛡 *Панель администратора*

Доступные команды:
• `/add_user <telegram_id> <username> <role> <limit>` - Добавить пользователя
• `/remove_user <telegram_id>` - Удалить пользователя
• `/set_role <telegram_id> <role>` - Изменить роль пользователя
• `/list_users` - Список всех пользователей

Примеры:
• `/add_user 123456789 username user 5000.0`
• `/set_role 123456789 admin`
• `/remove_user 123456789`
    """
    
    await message.answer(admin_menu, parse_mode="Markdown")
    
    # Отправляем сообщение с основной клавиатурой, чтобы пользователь мог вернуться к обычному режиму
    from utils.keyboards import get_main_keyboard
    keyboard = get_main_keyboard(is_admin=True)
    await message.answer("👆 Выберите действие:", reply_markup=keyboard)


async def add_user_command_handler(message: types.Message, auth_service: AuthService, current_user: Optional[dict] = None):
    """
    Обработчик команды /add_user для добавления нового пользователя.
    
    Args:
        message: Объект сообщения от пользователя
        auth_service: Сервис аутентификации для работы с пользователями
        current_user: Словарь с информацией о пользователе из middleware
    """
    # Проверяем права администратора
    if not is_admin(current_user):
        await message.answer("❌ *Доступ запрещен.*\nТолько администраторы могут добавлять пользователей.", parse_mode="Markdown")
        return
    
    # Извлекаем аргументы из сообщения
    args = message.text.split()[1:]  # Пропускаем команду /add_user
    
    if len(args) != 4:
        await message.answer(
            "❌ *Неправильный формат команды.*\n"
            "Использование: `/add_user <telegram_id> <username> <role> <limit>`\n"
            "Пример: `/add_user 123456789 username user 5000.0`",
            parse_mode="Markdown"
        )
        return
    
    try:
        telegram_id = int(args[0])
        username = args[1]
        role = args[2]
        monthly_limit = float(args[3])
        
        # Проверяем допустимые значения роли
        if role not in ['user', 'admin']:
            await message.answer(
                "❌ *Недопустимая роль.*\n"
                "Роль должна быть 'user' или 'admin'.",
                parse_mode="Markdown"
            )
            return
        
        # Создаем пользователя через сервис
        new_user = await auth_service.create_user(
            telegram_id=telegram_id,
            username=username,
            role=role,
            monthly_limit=monthly_limit
        )
        
        await message.answer(
            f"✅ *Пользователь успешно добавлен:*\n"
            f"Telegram ID: `{new_user.telegram_id}`\n"
            f"Username: `{new_user.username}`\n"
            f"Роль: `{new_user.role}`\n"
            f"Лимит: `{new_user.monthly_limit}`",
            parse_mode="Markdown"
        )
        
    except ValueError:
        await message.answer(
            "❌ *Неправильный формат данных.*\n"
            "Telegram ID должен быть числом, лимит - числом с плавающей точкой.",
            parse_mode="Markdown"
        )
    except Exception as e:
        await message.answer(
            f"❌ *Ошибка при добавлении пользователя:* {str(e)}",
            parse_mode="Markdown"
        )


async def remove_user_command_handler(message: types.Message, auth_service: AuthService, current_user: Optional[dict] = None):
    """
    Обработчик команды /remove_user для удаления пользователя.
    
    Args:
        message: Объект сообщения от пользователя
        auth_service: Сервис аутентификации для работы с пользователями
        current_user: Словарь с информацией о пользователе из middleware
    """
    # Проверяем права администратора
    if not is_admin(current_user):
        await message.answer("❌ *Доступ запрещен.*\nТолько администраторы могут удалять пользователей.", parse_mode="Markdown")
        return
    
    # Извлекаем аргументы из сообщения
    args = message.text.split()[1:]  # Пропускаем команду /remove_user
    
    if len(args) != 1:
        await message.answer(
            "❌ *Неправильный формат команды.*\n"
            "Использование: `/remove_user <telegram_id>`\n"
            "Пример: `/remove_user 123456789`",
            parse_mode="Markdown"
        )
        return
    
    try:
        telegram_id = int(args[0])
        
        # Удаляем пользователя через сервис
        success = await auth_service.delete_user(telegram_id)
        
        if success:
            await message.answer(
                f"✅ *Пользователь с Telegram ID `{telegram_id}` успешно удален.*",
                parse_mode="Markdown"
            )
        else:
            await message.answer(
                f"❌ *Пользователь с Telegram ID `{telegram_id}` не найден.*",
                parse_mode="Markdown"
            )
            
    except ValueError:
        await message.answer(
            "❌ *Неправильный формат данных.*\n"
            "Telegram ID должен быть числом.",
            parse_mode="Markdown"
        )
    except Exception as e:
        await message.answer(
            f"❌ *Ошибка при удалении пользователя:* {str(e)}",
            parse_mode="Markdown"
        )


async def set_role_command_handler(message: types.Message, auth_service: AuthService, current_user: Optional[dict] = None):
    """
    Обработчик команды /set_role для изменения роли пользователя.
    
    Args:
        message: Объект сообщения от пользователя
        auth_service: Сервис аутентификации для работы с пользователями
        current_user: Словарь с информацией о пользователе из middleware
    """
    # Проверяем права администратора
    if not is_admin(current_user):
        await message.answer("❌ *Доступ запрещен.*\nТолько администраторы могут изменять роли пользователей.", parse_mode="Markdown")
        return
    
    # Извлекаем аргументы из сообщения
    args = message.text.split()[1:]  # Пропускаем команду /set_role
    
    if len(args) != 2:
        await message.answer(
            "❌ *Неправильный формат команды.*\n"
            "Использование: `/set_role <telegram_id> <role>`\n"
            "Пример: `/set_role 123456789 admin`",
            parse_mode="Markdown"
        )
        return
    
    try:
        telegram_id = int(args[0])
        role = args[1]
        
        # Проверяем допустимые значения роли
        if role not in ['user', 'admin']:
            await message.answer(
                "❌ *Недопустимая роль.*\n"
                "Роль должна быть 'user' или 'admin'.",
                parse_mode="Markdown"
            )
            return
        
        # Обновляем роль пользователя через сервис
        success = await auth_service.update_user_role(telegram_id, role)
        
        if success:
            await message.answer(
                f"✅ *Роль пользователя с Telegram ID `{telegram_id}` успешно обновлена на `{role}`.*",
                parse_mode="Markdown"
            )
        else:
            await message.answer(
                f"❌ *Пользователь с Telegram ID `{telegram_id}` не найден.*",
                parse_mode="Markdown"
            )
            
    except ValueError:
        await message.answer(
            "❌ *Неправильный формат данных.*\n"
            "Telegram ID должен быть числом.",
            parse_mode="Markdown"
        )
    except Exception as e:
        await message.answer(
            f"❌ *Ошибка при изменении роли пользователя:* {str(e)}",
            parse_mode="Markdown"
        )


async def list_users_command_handler(message: types.Message, auth_service: AuthService, current_user: Optional[dict] = None):
    """
    Обработчик команды /list_users для получения списка всех пользователей.
    
    Args:
        message: Объект сообщения от пользователя
        auth_service: Сервис аутентификации для работы с пользователями
        current_user: Словарь с информацией о пользователе из middleware
    """
    # Проверяем права администратора
    if not is_admin(current_user):
        await message.answer("❌ *Доступ запрещен.*\nТолько администраторы могут просматривать список пользователей.", parse_mode="Markdown")
        return
    
    try:
        # Получаем список всех пользователей через сервис
        users = await auth_service.get_all_users()
        
        if not users:
            await message.answer("📋 *Список пользователей пуст.*", parse_mode="Markdown")
            return
        
        # Формируем сообщение со списком пользователей
        users_list = "👥 *Список всех пользователей:*\n\n"
        for user in users:
            users_list += (
                f"🔹 ID: `{user.id}`\n"
                f"   Telegram ID: `{user.telegram_id}`\n"
                f"   Username: `{user.username or 'N/A'}`\n"
                f"   Роль: `{user.role}`\n"
                f"   Лимит: `{user.monthly_limit}`\n\n"
            )
        
        await message.answer(users_list, parse_mode="Markdown")
        
    except Exception as e:
        await message.answer(
            f"❌ *Ошибка при получении списка пользователей:* {str(e)}",
            parse_mode="Markdown"
        )


# FSM обработчики для интерактивной админ-панели
async def admin_callback_handler(callback: types.CallbackQuery, state: FSMContext, auth_service: AuthService, current_user: Optional[dict] = None):
    """
    Обработчик callback'ов для интерактивной админ-панели.
    
    Args:
        callback: Объект callback запроса
        state: FSM контекст
        auth_service: Сервис аутентификации для проверки прав
        current_user: Словарь с информацией о пользователе из middleware
    """
    # Проверяем права администратора
    if not is_admin(current_user):
        await callback.answer("❌ Доступ запрещен. Только администраторы могут использовать эту функцию.", show_alert=True)
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
        # Переход к добавлению пользователя
        await callback.answer("➕ Добавление пользователя: используйте команду /add_user", show_alert=True)
    elif data == "remove_user_admin":
        # Переход к удалению пользователя
        await callback.answer("🗑️ Удаление пользователя: используйте команду /remove_user", show_alert=True)
    elif data == "set_role_admin":
        # Переход к изменению роли
        await callback.answer("✏️ Изменение роли: используйте команду /set_role", show_alert=True)
    elif data == "list_users_admin":
        # Показать список пользователей
        await callback.answer("📋 Список пользователей: используйте команду /list_users", show_alert=True)
    elif data == "admin_back_to_main":
        # Возврат в главное меню админ-панели
        await AdminPanel.admin_menu(callback.message, state, auth_service, current_user)
    elif data == "general_stats":
        await callback.answer("📈 Общая статистика: функция в разработке", show_alert=True)
    elif data == "user_stats":
        await callback.answer("📊 Статистика по пользователям: функция в разработке", show_alert=True)
    elif data == "reports":
        await callback.answer("📋 Отчеты: функция в разработке", show_alert=True)
    else:
        await callback.answer("Неизвестная команда", show_alert=True)


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
        "user_stats", "reports"
    ])