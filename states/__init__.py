from aiogram.fsm.state import State, StatesGroup


class UploadPhotosState(StatesGroup):
    choosing_project = State()
    choosing_slot = State()
    waiting_photos = State()
