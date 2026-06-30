import asyncio
import logging
import re
import tempfile
from datetime import date
from pathlib import Path

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove

from keyboards.inline import get_projects_keyboard, get_time_slots_keyboard
from keyboards.reply import get_main_keyboard
from projects import get_projects
from services.webdav_service import WebDAVService
from states import UploadPhotosState

router = Router()
logger = logging.getLogger(__name__)

_media_groups: dict[tuple[int, int, str], dict] = {}
_media_group_tasks: dict[tuple[int, int, str], asyncio.Task[None]] = {}

WEBDAV_ERROR_MESSAGE = (
    "Не удалось загрузить фотографии в хранилище. Попробуйте позже."
)
DOWNLOAD_ERROR_MESSAGE = (
    "Не удалось скачать файл из Telegram. Попробуйте отправить фотографии снова."
)


class UploadError(Exception):
    def __init__(self, user_message: str) -> None:
        self.user_message = user_message
        super().__init__(user_message)


def _is_image(message: Message) -> bool:
    return bool(
        message.photo
        or (
            message.document
            and message.document.mime_type
            and message.document.mime_type.startswith("image/")
        )
    )


def _get_project_name(project_id: str) -> str:
    for project in get_projects():
        if project["id"] == project_id:
            return project["name"]

    return project_id


def _get_message_file(message: Message):
    if message.photo:
        return message.photo[-1], ".jpg"

    if message.document:
        file_name = message.document.file_name or f"{message.document.file_unique_id}.jpg"
        return message.document, Path(file_name).suffix or ".jpg"

    return None, ".jpg"


def _sanitize_remote_path_part(value: str) -> str:
    safe_value = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "-", value)
    return safe_value.strip(" .") or "unknown"


def _build_success_message(
    project_name: str,
    upload_date: str,
    time_slot: str,
    count: int,
) -> str:
    return (
        "Фотографии успешно загружены.\n\n"
        f"Проект: {project_name}\n"
        f"Дата: {upload_date}\n"
        f"Слот: {time_slot}\n"
        f"Количество: {count}"
    )


async def _upload_messages(
    messages: list[Message],
    data: dict,
    bot: Bot,
) -> tuple[str, str, str, int]:
    project_id = data["project"]
    time_slot = data["time"]
    project_name = _get_project_name(project_id)
    upload_date = date.today().strftime("%d-%m-%Y")
    remote_folder = "/".join(
        [
            _sanitize_remote_path_part("Фото"),
            _sanitize_remote_path_part(upload_date),
            _sanitize_remote_path_part(project_name),
            _sanitize_remote_path_part(time_slot),
        ]
    )
    uploaded_count = 0

    try:
        webdav_service = WebDAVService()
        await asyncio.to_thread(webdav_service.create_folders, remote_folder)
    except Exception as exc:
        raise UploadError(WEBDAV_ERROR_MESSAGE) from exc

    with tempfile.TemporaryDirectory() as temp_dir:
        for index, message in enumerate(messages, start=1):
            telegram_file, suffix = _get_message_file(message)
            if telegram_file is None:
                continue

            local_path = Path(temp_dir) / f"{index}{suffix}"
            try:
                await bot.download(telegram_file, destination=local_path)
            except Exception as exc:
                raise UploadError(DOWNLOAD_ERROR_MESSAGE) from exc

            remote_path = f"{remote_folder}/{local_path.name}"
            try:
                await asyncio.to_thread(
                    webdav_service.upload_file,
                    local_path,
                    remote_path,
                    True,
                )
            except Exception as exc:
                raise UploadError(WEBDAV_ERROR_MESSAGE) from exc
            uploaded_count += 1

    return project_name, upload_date, time_slot, uploaded_count


async def _send_upload_error(message: Message, error: UploadError) -> None:
    logger.exception("Photo upload failed")
    await message.answer(error.user_message)


async def _send_media_group_result(
    key: tuple[int, int, str],
    bot: Bot,
    state: FSMContext,
) -> None:
    await asyncio.sleep(1)
    media_group = _media_groups.pop(key, {})
    _media_group_tasks.pop(key, None)

    messages = media_group.get("messages", [])
    if messages:
        try:
            project_name, upload_date, time_slot, uploaded_count = await _upload_messages(
                messages,
                media_group["data"],
                bot,
            )
        except UploadError as error:
            await _send_upload_error(messages[-1], error)
            return

        await state.clear()
        await messages[-1].answer(
            _build_success_message(project_name, upload_date, time_slot, uploaded_count),
            reply_markup=get_main_keyboard(),
        )


@router.message(F.text == "Загрузить фотографии")
async def upload_photos(message: Message, state: FSMContext) -> None:
    await state.set_state(UploadPhotosState.choosing_project)
    await message.answer(
        "Выберите проект:",
        reply_markup=ReplyKeyboardRemove(),
    )
    await message.answer(
        "Список проектов:",
        reply_markup=get_projects_keyboard(),
    )


@router.callback_query(UploadPhotosState.choosing_project, F.data.startswith("project:"))
async def choose_project(callback: CallbackQuery, state: FSMContext) -> None:
    project_id = callback.data.split(":", maxsplit=1)[1]
    await state.update_data(project=project_id)
    await state.set_state(UploadPhotosState.choosing_slot)
    if isinstance(callback.message, Message):
        await callback.message.answer(
            "Выберите временной слот:",
            reply_markup=get_time_slots_keyboard(project_id),
        )
    await callback.answer()


@router.callback_query(UploadPhotosState.choosing_slot, F.data.startswith("slot:"))
async def choose_slot(callback: CallbackQuery, state: FSMContext) -> None:
    time_slot = callback.data.split(":", maxsplit=1)[1]
    await state.update_data(time=time_slot)
    await state.set_state(UploadPhotosState.waiting_photos)
    if isinstance(callback.message, Message):
        await callback.message.answer("Отправьте фотографии.")
    await callback.answer()


@router.message(UploadPhotosState.waiting_photos, F.photo | F.document)
async def handle_photos(message: Message, state: FSMContext, bot: Bot) -> None:
    if not _is_image(message):
        return

    data = await state.get_data()

    if message.media_group_id and message.from_user:
        key = (message.chat.id, message.from_user.id, message.media_group_id)
        media_group = _media_groups.setdefault(key, {"messages": [], "data": data})
        media_group["messages"].append(message)

        if key not in _media_group_tasks:
            _media_group_tasks[key] = asyncio.create_task(
                _send_media_group_result(key, bot, state)
            )

        return

    try:
        project_name, upload_date, time_slot, uploaded_count = await _upload_messages(
            [message],
            data,
            bot,
        )
    except UploadError as error:
        await _send_upload_error(message, error)
        return

    await state.clear()
    await message.answer(
        _build_success_message(project_name, upload_date, time_slot, uploaded_count),
        reply_markup=get_main_keyboard(),
    )
