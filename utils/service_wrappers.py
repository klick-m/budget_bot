# utils/service_wrappers.py
from aiogram import Bot, types
from aiogram.exceptions import TelegramBadRequest
from config import logger

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

async def edit_or_send(bot: Bot, message: types.Message, text: str, **kwargs):
    """
    Пытается отредактировать сообщение, в случае неудачи (например, если сообщение слишком старое) 
    отправляет новое сообщение.
    """
    # 1. Сначала пытаемся отредактировать
    if message.message_id:
        try:
            return await bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=message.message_id,
                text=text,
                **kwargs
            )
        except TelegramBadRequest as e:
            # 2. Если редактирование не удалось из-за старости сообщения, отправляем новое
            logger.warning(f"Failed to edit message {message.message_id}: {e}. Sending new message.")
            pass 
        except AttributeError:
            # На всякий случай, если message_id не найден
            pass
    
    # 3. Отправляем новое сообщение, если редактирование не прошло
    return await bot.send_message(
        chat_id=message.chat.id,
        text=text,
        **kwargs
    )