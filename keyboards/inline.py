from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from services.location_service import (
    LocationSummary,
    get_location_projects,
    get_project_time_slots,
)


def get_locations_keyboard(locations: list[LocationSummary]) -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton(text=str(location["name"]), callback_data=f"location:{location['id']}")]
        for location in locations
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_location_projects_keyboard(location_id: str) -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton(text=project["name"], callback_data=f"project:{project['id']}")]
        for project in get_location_projects(location_id)
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_location_time_slots_keyboard(location_id: str, project_id: str) -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton(text=time_slot, callback_data=f"slot:{time_slot}")]
        for time_slot in get_project_time_slots(location_id, project_id)
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)
