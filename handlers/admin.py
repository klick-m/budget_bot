# handlers/admin.py
from aiogram import Router, types
from aiogram.filters import Command
from typing import Dict, Any
from services.auth_service import AuthService
from utils.messages import MSG
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


async def admin_command_handler(message: types.Message, data: dict, auth_service: AuthService):
    """
    Обработчик команды /admin для открытия панели администратора.
    
    Args:
        message: Объект сообщения от пользователя
        data: Данные контекста (включая информацию о пользователе)
        auth_service: Сервис аутентификации для работы с пользователями
    """
    # Получаем информацию о пользователе из middleware
    current_user = data.get('current_user')
    
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


async def add_user_command_handler(message: types.Message, data: dict, auth_service: AuthService):
    """
    Обработчик команды /add_user для добавления нового пользователя.
    
    Args:
        message: Объект сообщения от пользователя
        data: Данные контекста (включая информацию о пользователе)
        auth_service: Сервис аутентификации для работы с пользователями
    """
    # Получаем информацию о пользователе из middleware
    current_user = data.get('current_user')
    
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


async def remove_user_command_handler(message: types.Message, data: dict, auth_service: AuthService):
    """
    Обработчик команды /remove_user для удаления пользователя.
    
    Args:
        message: Объект сообщения от пользователя
        data: Данные контекста (включая информацию о пользователе)
        auth_service: Сервис аутентификации для работы с пользователями
    """
    # Получаем информацию о пользователе из middleware
    current_user = data.get('current_user')
    
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


async def set_role_command_handler(message: types.Message, data: dict, auth_service: AuthService):
    """
    Обработчик команды /set_role для изменения роли пользователя.
    
    Args:
        message: Объект сообщения от пользователя
        data: Данные контекста (включая информацию о пользователе)
        auth_service: Сервис аутентификации для работы с пользователями
    """
    # Получаем информацию о пользователе из middleware
    current_user = data.get('current_user')
    
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


async def list_users_command_handler(message: types.Message, data: dict, auth_service: AuthService):
    """
    Обработчик команды /list_users для получения списка всех пользователей.
    
    Args:
        message: Объект сообщения от пользователя
        data: Данные контекста (включая информацию о пользователе)
        auth_service: Сервис аутентификации для работы с пользователями
    """
    # Получаем информацию о пользователе из middleware
    current_user = data.get('current_user')
    
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


def register_admin_handlers(dp: Router):
    """Регистрирует хендлеры административных команд."""
    # Регистрируем команды
    dp.message.register(admin_command_handler, Command(commands=["admin"]))
    dp.message.register(add_user_command_handler, Command(commands=["add_user"]))
    dp.message.register(remove_user_command_handler, Command(commands=["remove_user"]))
    dp.message.register(set_role_command_handler, Command(commands=["set_role"]))
    dp.message.register(list_users_command_handler, Command(commands=["list_users"]))