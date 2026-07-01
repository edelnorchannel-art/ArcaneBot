from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware, Bot
from aiogram.types import CallbackQuery, Message, TelegramObject

from services.location_access_service import LocationAccessService

ACCESS_DENIED_MESSAGE = "У вас нет доступа к использованию бота."


async def is_user_allowed(bot: Bot, user_id: int) -> bool:
    access_service = LocationAccessService(bot)
    available_locations = await access_service.get_available_locations(user_id)
    return bool(available_locations)


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
