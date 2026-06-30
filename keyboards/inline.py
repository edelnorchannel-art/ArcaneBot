from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from projects import get_projects, get_time_slots


def get_projects_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton(text=project["name"], callback_data=f"project:{project['id']}")]
        for project in get_projects()
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_time_slots_keyboard(project_id: str) -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton(text=time_slot, callback_data=f"slot:{time_slot}")]
        for time_slot in get_time_slots(project_id)
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)
