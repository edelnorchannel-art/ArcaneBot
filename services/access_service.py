from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware, Bot
from aiogram.enums import ChatMemberStatus
from aiogram.types import CallbackQuery, Message, TelegramObject

from config import CORPORATE_CHAT_ID

ACCESS_DENIED_MESSAGE = "У вас нет доступа к использованию бота."

_ALLOWED_STATUSES = {
    ChatMemberStatus.CREATOR,
    ChatMemberStatus.ADMINISTRATOR,
    ChatMemberStatus.MEMBER,
    ChatMemberStatus.RESTRICTED,
}


async def is_user_allowed(bot: Bot, user_id: int) -> bool:
    if not CORPORATE_CHAT_ID:
        return False

    try:
        member = await bot.get_chat_member(
            chat_id=int(CORPORATE_CHAT_ID),
            user_id=user_id,
        )
        return member.status in _ALLOWED_STATUSES
    except Exception:
        return False


class AccessMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        bot: Bot = data["bot"]
        user = getattr(event, "from_user", None)

        if user is None or await is_user_allowed(bot, user.id):
            return await handler(event, data)

        if isinstance(event, Message):
            await event.answer(ACCESS_DENIED_MESSAGE)
        elif isinstance(event, CallbackQuery):
            if event.message:
                await event.message.answer(ACCESS_DENIED_MESSAGE)
            await event.answer()

        return None
