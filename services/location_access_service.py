from aiogram import Bot
from aiogram.enums import ChatMemberStatus

from services.location_service import LocationSummary, get_locations

_ALLOWED_STATUSES = {
    ChatMemberStatus.CREATOR,
    ChatMemberStatus.ADMINISTRATOR,
    ChatMemberStatus.MEMBER,
    ChatMemberStatus.RESTRICTED,
}


class LocationAccessService:
    def __init__(self, bot: Bot) -> None:
        self.bot = bot

    async def get_available_locations(
        self,
        user_id: int,
    ) -> list[LocationSummary]:
        available_locations = []

        for location in get_locations():
            chat_id = location["chat_id"]
            if chat_id is None:
                continue

            try:
                member = await self.bot.get_chat_member(
                    chat_id=int(chat_id),
                    user_id=user_id,
                )
            except Exception:
                continue

            if member.status in _ALLOWED_STATUSES:
                available_locations.append(location)

        return available_locations
