from __future__ import annotations

import asyncio
import logging
import re
import tempfile
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, TypedDict, cast

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from keyboards.inline import (
    get_location_projects_keyboard,
    get_location_time_slots_keyboard,
    get_locations_keyboard,
)
from keyboards.reply import get_cancel_keyboard, get_main_keyboard
from services.location_access_service import LocationAccessService
from services.location_service import get_locations, get_location_projects
from services.watermark_service import WatermarkError, apply_watermark
from services.webdav_service import WebDAVService
from states import UploadPhotosState

router = Router()
logger = logging.getLogger(__name__)

_media_groups: dict[tuple[int, int, str], MediaGroupData] = {}
_media_group_tasks: dict[tuple[int, int, str], asyncio.Task[None]] = {}
_MONTH_NAMES = [
    "Январь",
    "Февраль",
    "Март",
    "Апрель",
    "Май",
    "Июнь",
    "Июль",
    "Август",
    "Сентябрь",
    "Октябрь",
    "Ноябрь",
    "Декабрь",
]

WEBDAV_ERROR_MESSAGE = (
    "Не удалось загрузить фотографии в хранилище. Попробуйте позже."
)
DOWNLOAD_ERROR_MESSAGE = (
    "Не удалось скачать файл из Telegram. Попробуйте отправить фотографии снова."
)
WATERMARK_ERROR_MESSAGE = (
    "Не удалось обработать фотографию. Попробуйте отправить файл в формате JPG или HEIC."
)


class UploadError(Exception):
    def __init__(self, user_message: str) -> None:
        self.user_message = user_message
        super().__init__(user_message)


class UploadStateData(TypedDict):
    location: str
    project: str
    slot: str


class MediaGroupData(TypedDict):
    messages: list[Message]
    data: UploadStateData


@dataclass(frozen=True)
class UploadResult:
    location_id: str
    location_name: str
    project_name: str
    upload_date: str
    time_slot: str
    uploaded_count: int


def _is_image(message: Message) -> bool:
    return bool(
        message.photo
        or (
            message.document
            and message.document.mime_type
            and message.document.mime_type.startswith("image/")
        )
    )


def _as_upload_state_data(data: dict[str, Any]) -> UploadStateData:
    return cast(UploadStateData, data)


def _get_location_project_name(location_id: str, project_id: str) -> str:
    for project in get_location_projects(location_id):
        if project["id"] == project_id:
            return project["name"]

    return project_id


def _get_location_name(location_id: str) -> str:
    for location in get_locations():
        if location["id"] == location_id:
            return str(location["name"])

    return location_id


def _get_location_chat_id(location_id: str) -> int | None:
    for location in get_locations():
        if location["id"] == location_id:
            chat_id = location["chat_id"]
            if chat_id is None:
                return None
            return int(chat_id)

    return None


def _get_message_file(message: Message) -> tuple[Any | None, str]:
    if message.photo:
        return message.photo[-1], ".jpg"

    if message.document:
        file_name = message.document.file_name or f"{message.document.file_unique_id}.jpg"
        return message.document, Path(file_name).suffix or ".jpg"

    return None, ".jpg"


def _sanitize_remote_path_part(value: str) -> str:
    safe_value = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "-", value)
    return safe_value.strip(" .") or "unknown"


def _allocate_unique_filename(used_names: set[str]) -> str:
    index = 1
    while True:
        candidate = f"{index}.jpg"
        if candidate not in used_names:
            used_names.add(candidate)
            return candidate
        index += 1


def _build_success_message(
    location_name: str,
    project_name: str,
    upload_date: str,
    time_slot: str,
    count: int,
) -> str:
    return (
        "Фотографии успешно загружены.\n\n"
        f"Локация: {location_name}\n"
        f"Проект: {project_name}\n"
        f"Дата: {upload_date}\n"
        f"Слот: {time_slot}\n"
        f"Количество фотографий: {count}"
    )


async def _upload_messages(
    messages: list[Message],
    data: UploadStateData,
    bot: Bot,
) -> UploadResult:
    location_id = data["location"]
    project_id = data["project"]
    time_slot = data["slot"]
    location_name = _get_location_name(location_id)
    project_name = _get_location_project_name(location_id, project_id)
    current_date = date.today()
    upload_date = current_date.strftime("%d-%m-%Y")
    remote_folder = "/".join(
        [
            _sanitize_remote_path_part("Фотографии игроков"),
            _sanitize_remote_path_part(location_name),
            _sanitize_remote_path_part(project_name),
            _sanitize_remote_path_part(str(current_date.year)),
            _sanitize_remote_path_part(_MONTH_NAMES[current_date.month - 1]),
            _sanitize_remote_path_part(upload_date),
            _sanitize_remote_path_part(time_slot),
        ]
    )
    uploaded_count = 0

    try:
        webdav_service = WebDAVService()
        await asyncio.to_thread(webdav_service.create_folders, remote_folder)
        used_names = await asyncio.to_thread(
            webdav_service.list_file_names,
            remote_folder,
        )
    except Exception as exc:
        raise UploadError(WEBDAV_ERROR_MESSAGE) from exc

    with tempfile.TemporaryDirectory() as temp_dir:
        for index, message in enumerate(messages, start=1):
            telegram_file, suffix = _get_message_file(message)
            if telegram_file is None:
                continue

            downloaded_path = Path(temp_dir) / f"{index}{suffix}"
            try:
                await bot.download(telegram_file, destination=downloaded_path)
            except Exception as exc:
                raise UploadError(DOWNLOAD_ERROR_MESSAGE) from exc

            watermarked_path = Path(temp_dir) / f"{index}.jpg"
            try:
                await asyncio.to_thread(
                    apply_watermark,
                    downloaded_path,
                    watermarked_path,
                )
            except WatermarkError as exc:
                raise UploadError(WATERMARK_ERROR_MESSAGE) from exc

            uploaded = False
            for _ in range(1000):
                remote_filename = _allocate_unique_filename(used_names)
                remote_path = f"{remote_folder}/{remote_filename}"
                try:
                    await asyncio.to_thread(
                        webdav_service.upload_file,
                        watermarked_path,
                        remote_path,
                        False,
                    )
                    uploaded = True
                    break
                except Exception as exc:
                    if webdav_service.is_upload_name_conflict(exc):
                        continue
                    raise UploadError(WEBDAV_ERROR_MESSAGE) from exc

            if not uploaded:
                raise UploadError(WEBDAV_ERROR_MESSAGE)
            uploaded_count += 1

    return UploadResult(
        location_id=location_id,
        location_name=location_name,
        project_name=project_name,
        upload_date=upload_date,
        time_slot=time_slot,
        uploaded_count=uploaded_count,
    )


async def _send_upload_error(message: Message, error: UploadError) -> None:
    logger.exception("Photo upload failed")
    await message.answer(error.user_message)


async def _send_success_copy(
    bot: Bot,
    location_id: str,
    success_message: str,
) -> None:
    chat_id = _get_location_chat_id(location_id)
    if chat_id is None:
        logger.warning("Location chat_id is not set, success copy was not sent")
        return

    try:
        await bot.send_message(
            chat_id=chat_id,
            text=success_message,
        )
    except Exception:
        logger.exception("Failed to send success upload copy to location chat")


async def _finish_successful_upload(
    message: Message,
    state: FSMContext,
    bot: Bot,
    result: UploadResult,
) -> None:
    await state.clear()
    success_message = _build_success_message(
        result.location_name,
        result.project_name,
        result.upload_date,
        result.time_slot,
        result.uploaded_count,
    )
    await message.answer(
        success_message,
        reply_markup=get_main_keyboard(),
    )
    await _send_success_copy(bot, result.location_id, success_message)


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
            result = await _upload_messages(
                messages,
                media_group["data"],
                bot,
            )
        except UploadError as error:
            await _send_upload_error(messages[-1], error)
            return

        await _finish_successful_upload(messages[-1], state, bot, result)


@router.message(F.text == "Загрузить фотографии")
async def upload_photos(message: Message, state: FSMContext, bot: Bot) -> None:
    if message.from_user is None:
        return

    access_service = LocationAccessService(bot)
    available_locations = await access_service.get_available_locations(message.from_user.id)

    if len(available_locations) == 1:
        location_id = str(available_locations[0]["id"])
        await state.update_data(location=location_id)
        await state.set_state(UploadPhotosState.choosing_project)
        await message.answer(
            "Выберите проект:",
            reply_markup=get_cancel_keyboard(),
        )
        await message.answer(
            "Список проектов:",
            reply_markup=get_location_projects_keyboard(location_id),
        )
        return

    await state.set_state(UploadPhotosState.choosing_location)
    await message.answer(
        "Выберите локацию",
        reply_markup=get_cancel_keyboard(),
    )
    await message.answer(
        "Список локаций:",
        reply_markup=get_locations_keyboard(available_locations),
    )


@router.message(F.text == "Отмена")
async def cancel_upload(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(
        "Действие отменено.",
        reply_markup=get_main_keyboard(),
    )


@router.callback_query(UploadPhotosState.choosing_location, F.data.startswith("location:"))
async def choose_location(callback: CallbackQuery, state: FSMContext) -> None:
    location_id = callback.data.split(":", maxsplit=1)[1]
    await state.update_data(location=location_id)
    await state.set_state(UploadPhotosState.choosing_project)
    if isinstance(callback.message, Message):
        await callback.message.answer(
            "Выберите проект:",
            reply_markup=get_location_projects_keyboard(location_id),
        )
    await callback.answer()


@router.callback_query(UploadPhotosState.choosing_project, F.data.startswith("project:"))
async def choose_project(callback: CallbackQuery, state: FSMContext) -> None:
    project_id = callback.data.split(":", maxsplit=1)[1]
    data = _as_upload_state_data(await state.get_data())
    await state.update_data(project=project_id)
    await state.set_state(UploadPhotosState.choosing_slot)
    if isinstance(callback.message, Message):
        await callback.message.answer(
            "Выберите временной слот:",
            reply_markup=get_location_time_slots_keyboard(data["location"], project_id),
        )
    await callback.answer()


@router.callback_query(UploadPhotosState.choosing_slot, F.data.startswith("slot:"))
async def choose_slot(callback: CallbackQuery, state: FSMContext) -> None:
    time_slot = callback.data.split(":", maxsplit=1)[1]
    data = _as_upload_state_data(await state.get_data())
    project_name = _get_location_project_name(data["location"], data["project"])
    await state.update_data(slot=time_slot)
    await state.set_state(UploadPhotosState.waiting_photos)
    if isinstance(callback.message, Message):
        await callback.message.answer(
            f"Загрузите фотографии после игры в {time_slot}, на локации {project_name}"
        )
    await callback.answer()


@router.message(UploadPhotosState.waiting_photos, F.photo | F.document)
async def handle_photos(message: Message, state: FSMContext, bot: Bot) -> None:
    if not _is_image(message):
        return

    data = _as_upload_state_data(await state.get_data())

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
        result = await _upload_messages(
            [message],
            data,
            bot,
        )
    except UploadError as error:
        await _send_upload_error(message, error)
        return

    await _finish_successful_upload(message, state, bot, result)
