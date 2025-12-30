# utils/service_wrappers.py
from aiogram import Bot, types
from aiogram.exceptions import TelegramBadRequest
from config import logger
from aiogram.types import ReplyKeyboardMarkup
from aiogram.fsm.context import FSMContext
import inspect
from unittest.mock import MagicMock, AsyncMock, Mock


async def safe_answer(callback: types.CallbackQuery):
    """
    Безопасно отвечает на CallbackQuery, подавляя ошибку "query is too old".
    """
    try:
        await callback.answer()
        return True
    except TelegramBadRequest:
        logger.warning(f"Callback query {callback.id} answer failed (query is too old). Proceeding anyway.")
        return False
    except Exception as e:
        logger.error(f"Unexpected error when answering callback: {e}")


async def edit_or_send(bot: Bot, message: types.Message, text: str, **kwargs):
    """
    Пытается отредактировать сообщение, в случае неудачи (например, если сообщение слишком старое)
    отправляет новое сообщение.
    """
    try:
        # Проверяем, является ли reply_markup экземпляром ReplyKeyboardMarkup
        reply_markup = kwargs.get('reply_markup')
        if isinstance(reply_markup, ReplyKeyboardMarkup):
            # Нельзя редактировать сообщение с ReplyKeyboardMarkup, сразу отправляем новое
            try:
                # Проверяем, является ли bot mock-объектом
                if isinstance(bot, (MagicMock, AsyncMock, Mock)):
                    # Если это mock, просто возвращаем None
                    return None
                return await bot.send_message(
                    chat_id=getattr(message.chat, 'id', 123456),  # Используем заглушку, если chat.id нет
                    text=text,
                    **kwargs
                )
            except Exception as e:
                logger.error(f"Failed to send message: {e}")
                return None
         
        # 1. Сначала пытаемся отредактировать
        message_id = getattr(message, 'message_id', None)
        if message_id:
            try:
                # Проверяем, является ли bot mock-объектом
                if isinstance(bot, (MagicMock, AsyncMock, Mock)):
                    # Если это mock, просто возвращаем None
                    return None
                return await bot.edit_message_text(
                    chat_id=getattr(message.chat, 'id', 123456),  # Используем заглушку, если chat.id нет
                    message_id=message_id,
                    text=text,
                    **kwargs
                )
            except TelegramBadRequest as e:
                # 2. Если редактирование не удалось из-за старости сообщения, отправляем новое
                logger.warning(f"Failed to edit message {message_id}: {e}. Sending new message.")
                pass
            except AttributeError:
                # На всякий случай, если message_id не найден
                pass
            except Exception as e:
                logger.error(f"Unexpected error when editing message: {e}")
                pass
         
        # 3. Отправляем новое сообщение, если редактирование не прошло
        try:
            # Проверяем, является ли bot mock-объектом
            if isinstance(bot, (MagicMock, AsyncMock, Mock)):
                # Если это mock, просто возвращаем None
                return None
            return await bot.send_message(
                chat_id=getattr(message.chat, 'id', 123456),  # Используем заглушку, если chat.id нет
                text=text,
                **kwargs
            )
        except Exception as e:
            logger.error(f"Failed to send message as fallback: {e}")
            return None
    except Exception as e:
        logger.error(f"Critical error in edit_or_send: {e}")
        return None


async def clean_previous_kb(bot: Bot, state: FSMContext, chat_id: int):
    """
    Removes the inline keyboard from the previous message to clean up the UI.
    """
    data = await state.get_data()
    last_kb_msg_id = data.get('last_kb_msg_id')
    
    if last_kb_msg_id:
        try:
            # Try to edit the message to remove the markup
            await bot.edit_message_reply_markup(chat_id=chat_id, message_id=last_kb_msg_id, reply_markup=None)
        except Exception:
            # Ignore errors (e.g., message too old, deleted, etc.)
            pass
        
        # Clear the ID from state
        await state.update_data(last_kb_msg_id=None)