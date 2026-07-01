import hmac
import shutil
from datetime import datetime
from html import escape
from hashlib import sha256
from pathlib import Path
from urllib.parse import parse_qs
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import (
    FileResponse,
    HTMLResponse,
    PlainTextResponse,
    RedirectResponse,
    Response,
)

from admin_panel.config_service import ConfigService
from config import ADMIN_PASSWORD

app = FastAPI(title="Photo Bot Admin Panel")
config_service = ConfigService()
templates_dir = Path(__file__).parent / "templates"
SESSION_COOKIE_NAME = "admin_session"
SESSION_PAYLOAD = "admin"


def _render_login_page(error_message: str = "") -> str:
    template = (templates_dir / "login.html").read_text(encoding="utf-8")
    if error_message:
        error_message = f"<p>{error_message}</p>"

    return template.replace("{{ error_message }}", error_message)


async def _read_form_data(request: Request) -> dict[str, str]:
    body = (await request.body()).decode("utf-8")
    return {
        key: values[0]
        for key, values in parse_qs(body).items()
    }


def _get_locations() -> list[dict[str, Any]]:
    config = config_service.read_config()
    locations = config.get("locations", [])
    if not isinstance(locations, list):
        return []

    return [
        location
        for location in locations
        if isinstance(location, dict)
    ]


def _write_locations(locations: list[dict[str, Any]]) -> None:
    config = config_service.read_config()
    config["locations"] = locations
    config_service.write_config(config)


def _create_config_backup() -> None:
    config_service.ensure_config_exists()
    backups_dir = config_service.config_path.parent / "backups"
    backups_dir.mkdir(parents=True, exist_ok=True)
    backup_name = f"config_{datetime.now().strftime('%Y_%m_%d_%H_%M_%S')}.json"
    shutil.copy2(config_service.config_path, backups_dir / backup_name)


def _get_backups_dir() -> Path:
    backups_dir = config_service.config_path.parent / "backups"
    backups_dir.mkdir(parents=True, exist_ok=True)
    return backups_dir


def _render_backups_page() -> str:
    template = (templates_dir / "backups.html").read_text(encoding="utf-8")
    backups = sorted(
        _get_backups_dir().glob("config_*.json"),
        key=lambda path: path.name,
        reverse=True,
    )
    items = [
        f'<li>{escape(path.name)} '
        f'<a href="/admin/backups/{escape(path.name)}">Скачать</a></li>'
        for path in backups
        if path.is_file()
    ]
    return template.replace("{{ backups_items }}", "\n".join(items))


def _get_location(location_id: str) -> dict[str, Any] | None:
    for location in _get_locations():
        if location.get("id") == location_id:
            return location

    return None


def _parse_chat_id(value: str) -> int | None:
    value = value.strip()
    if not value:
        return None

    try:
        return int(value)
    except ValueError:
        return None


def _generate_location_id(locations: list[dict[str, Any]]) -> str:
    max_number = 0

    for location in locations:
        location_id = str(location.get("id", ""))
        if not location_id.startswith("location_"):
            continue

        try:
            max_number = max(max_number, int(location_id.removeprefix("location_")))
        except ValueError:
            continue

    return f"location_{max_number + 1}"


def _get_projects(location: dict[str, Any]) -> list[dict[str, Any]]:
    projects = location.get("projects", [])
    if isinstance(projects, dict):
        return [
            {"id": project_id, **project}
            for project_id, project in projects.items()
            if isinstance(project, dict)
        ]

    if not isinstance(projects, list):
        location["projects"] = []
        return location["projects"]

    return [
        project
        for project in projects
        if isinstance(project, dict)
    ]


def _get_project(
    location_id: str,
    project_id: str,
) -> tuple[dict[str, Any], dict[str, Any]] | None:
    location = _get_location(location_id)
    if location is None:
        return None

    for project in _get_projects(location):
        if project.get("id") == project_id:
            return location, project

    return None


def _get_time_slots(project: dict[str, Any]) -> list[str]:
    time_slots = project.get("time_slots", [])
    if not isinstance(time_slots, list):
        project["time_slots"] = []
        return project["time_slots"]

    return [
        time_slot
        for time_slot in time_slots
        if isinstance(time_slot, str)
    ]


def _generate_project_id(projects: list[dict[str, Any]]) -> str:
    max_number = 0

    for project in projects:
        project_id = str(project.get("id", ""))
        if not project_id.startswith("project_"):
            continue

        try:
            max_number = max(max_number, int(project_id.removeprefix("project_")))
        except ValueError:
            continue

    return f"project_{max_number + 1}"


def _get_project_entries() -> list[tuple[str, str, dict[str, Any], dict[str, Any]]]:
    entries = []

    for location in _get_locations():
        location_id = str(location.get("id", ""))
        if not location_id:
            continue

        for project in _get_projects(location):
            project_id = str(project.get("id", ""))
            if not project_id:
                continue

            entries.append((location_id, project_id, location, project))

    return entries


def _render_locations_page() -> str:
    template = (templates_dir / "locations.html").read_text(encoding="utf-8")
    rows = []

    for location in _get_locations():
        location_id = escape(str(location.get("id", "")))
        name = escape(str(location.get("name", "")))
        chat_id = escape(str(location.get("chat_id", "")))
        rows.append(
            "<tr>"
            f"<td>{name}</td>"
            f"<td>{chat_id}</td>"
            "<td>"
            f'<a href="/admin/locations/{location_id}/edit">'
            '<button type="button">Редактировать</button>'
            "</a>"
            f'<form method="post" action="/admin/locations/{location_id}/delete" '
            'style="display:inline">'
            '<button type="submit">Удалить</button>'
            "</form>"
            "</td>"
            "</tr>"
        )

    return template.replace("{{ locations_rows }}", "\n".join(rows))


def _render_location_form(
    title: str,
    action: str,
    name: str = "",
    chat_id: int | None = None,
) -> str:
    template = (templates_dir / "location_form.html").read_text(encoding="utf-8")
    return (
        template
        .replace("{{ title }}", escape(title))
        .replace("{{ action }}", escape(action))
        .replace("{{ name }}", escape(name))
        .replace("{{ chat_id }}", "" if chat_id is None else escape(str(chat_id)))
    )


def _render_projects_page() -> str:
    template = (templates_dir / "projects.html").read_text(encoding="utf-8")
    rows = []

    for location in _get_locations():
        location_id = escape(str(location.get("id", "")))
        location_name = escape(str(location.get("name", "")))

        for project in _get_projects(location):
            project_id = escape(str(project.get("id", "")))
            project_name = escape(str(project.get("name", "")))
            rows.append(
                "<tr>"
                f"<td>{location_name}</td>"
                f"<td>{project_name}</td>"
                "<td>"
                f'<a href="/admin/projects/{location_id}/{project_id}/edit">'
                '<button type="button">Редактировать</button>'
                "</a>"
                f'<form method="post" action="/admin/projects/{location_id}/{project_id}/delete" '
                'style="display:inline">'
                '<button type="submit">Удалить</button>'
                "</form>"
                "</td>"
                "</tr>"
            )

    return template.replace("{{ projects_rows }}", "\n".join(rows))


def _render_project_form(
    title: str,
    action: str,
    name: str = "",
    selected_location_id: str = "",
) -> str:
    template = (templates_dir / "project_form.html").read_text(encoding="utf-8")
    options = []

    for location in _get_locations():
        location_id = str(location.get("id", ""))
        location_name = escape(str(location.get("name", "")))
        selected = " selected" if location_id == selected_location_id else ""
        options.append(
            f'<option value="{escape(location_id)}"{selected}>{location_name}</option>'
        )

    return (
        template
        .replace("{{ title }}", escape(title))
        .replace("{{ action }}", escape(action))
        .replace("{{ locations_options }}", "\n".join(options))
        .replace("{{ name }}", escape(name))
    )


def _build_project_options(
    selected_project_key: str = "",
    include_all_option: bool = False,
) -> str:
    options = []
    if include_all_option:
        selected = " selected" if not selected_project_key else ""
        options.append(f'<option value=""{selected}>Все проекты</option>')

    for location_id, project_id, location, project in _get_project_entries():
        location_name = str(location.get("name", ""))
        project_name = str(project.get("name", ""))
        project_key = f"{location_id}:{project_id}"
        selected = " selected" if project_key == selected_project_key else ""
        option_text = f"{location_name} — {project_name}"
        options.append(
            f'<option value="{escape(project_key)}"{selected}>{escape(option_text)}</option>'
        )

    return "\n".join(options)


def _render_slots_page(selected_project_key: str = "") -> str:
    template = (templates_dir / "slots.html").read_text(encoding="utf-8")
    rows = []

    for location in _get_locations():
        location_id = str(location.get("id", ""))
        escaped_location_id = escape(location_id)
        location_name = escape(str(location.get("name", "")))

        for project in _get_projects(location):
            project_id = str(project.get("id", ""))
            project_key = f"{location_id}:{project_id}"
            if selected_project_key and project_key != selected_project_key:
                continue

            escaped_project_id = escape(project_id)
            project_name = escape(str(project.get("name", "")))

            for index, time_slot in enumerate(_get_time_slots(project)):
                rows.append(
                    "<tr>"
                    f"<td>{location_name}</td>"
                    f"<td>{project_name}</td>"
                    f"<td>{escape(time_slot)}</td>"
                    "<td>"
                    f'<a href="/admin/slots/{escaped_location_id}/{escaped_project_id}/{index}/edit">'
                    '<button type="button">Редактировать</button>'
                    "</a>"
                    f'<form method="post" action="/admin/slots/{escaped_location_id}/{escaped_project_id}/{index}/delete" '
                    'style="display:inline">'
                    '<button type="submit">Удалить</button>'
                    "</form>"
                    "</td>"
                    "</tr>"
                )

    return (
        template
        .replace("{{ projects_filter_options }}", _build_project_options(selected_project_key, True))
        .replace("{{ slots_rows }}", "\n".join(rows))
    )


def _render_slot_form(
    title: str,
    action: str,
    time_slot: str = "",
    selected_project_key: str = "",
) -> str:
    template = (templates_dir / "slot_form.html").read_text(encoding="utf-8")
    return (
        template
        .replace("{{ title }}", escape(title))
        .replace("{{ action }}", escape(action))
        .replace("{{ projects_options }}", _build_project_options(selected_project_key))
        .replace("{{ time }}", escape(time_slot))
    )


def _parse_project_key(project_key: str) -> tuple[str, str] | None:
    if ":" not in project_key:
        return None

    location_id, project_id = project_key.split(":", maxsplit=1)
    if not location_id or not project_id:
        return None

    return location_id, project_id


def _create_session_token() -> str:
    signature = hmac.new(
        (ADMIN_PASSWORD or "").encode("utf-8"),
        SESSION_PAYLOAD.encode("utf-8"),
        sha256,
    ).hexdigest()
    return f"{SESSION_PAYLOAD}:{signature}"


def _is_authenticated(request: Request) -> bool:
    if not ADMIN_PASSWORD:
        return False

    session_token = request.cookies.get(SESSION_COOKIE_NAME)
    return hmac.compare_digest(session_token or "", _create_session_token())


@app.middleware("http")
async def admin_auth_middleware(request: Request, call_next):
    if request.url.path.startswith("/admin") and not _is_authenticated(request):
        return RedirectResponse(url="/login", status_code=303)

    return await call_next(request)


@app.get("/", response_class=PlainTextResponse)
async def index() -> str:
    return "Photo Bot Admin Panel"


@app.get("/login", response_class=HTMLResponse)
async def login_page() -> str:
    return _render_login_page()


@app.post("/login")
async def login(request: Request) -> Response:
    form_data = await _read_form_data(request)
    password = form_data.get("password", "")

    if not ADMIN_PASSWORD or not hmac.compare_digest(password, ADMIN_PASSWORD):
        return HTMLResponse(_render_login_page("Неверный пароль"), status_code=401)

    response = RedirectResponse(url="/admin", status_code=303)
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=_create_session_token(),
        httponly=True,
        samesite="lax",
    )
    return response


@app.get("/logout")
async def logout() -> RedirectResponse:
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie(SESSION_COOKIE_NAME)
    return response


@app.get("/admin", response_class=HTMLResponse)
async def admin_page() -> str:
    return (templates_dir / "admin.html").read_text(encoding="utf-8")


@app.post("/admin/backup")
async def create_backup() -> RedirectResponse:
    _create_config_backup()
    return RedirectResponse(url="/admin", status_code=303)


@app.get("/admin/backups", response_class=HTMLResponse)
async def backups_page() -> str:
    return _render_backups_page()


@app.get("/admin/backups/{backup_name}")
async def download_backup(backup_name: str) -> Response:
    if Path(backup_name).name != backup_name:
        return RedirectResponse(url="/admin/backups", status_code=303)

    backup_path = _get_backups_dir() / backup_name
    if not backup_path.is_file() or not backup_name.startswith("config_") or backup_path.suffix != ".json":
        return RedirectResponse(url="/admin/backups", status_code=303)

    return FileResponse(
        backup_path,
        media_type="application/json",
        filename=backup_name,
    )


@app.get("/admin/locations", response_class=HTMLResponse)
async def admin_locations_page() -> str:
    return _render_locations_page()


@app.get("/admin/locations/add", response_class=HTMLResponse)
async def add_location_page() -> str:
    return _render_location_form(
        title="Добавить локацию",
        action="/admin/locations/add",
    )


@app.post("/admin/locations/add")
async def add_location(request: Request) -> RedirectResponse:
    form_data = await _read_form_data(request)
    locations = _get_locations()
    locations.append(
        {
            "id": _generate_location_id(locations),
            "name": form_data.get("name", "").strip(),
            "chat_id": _parse_chat_id(form_data.get("chat_id", "")),
            "projects": [],
        }
    )
    _write_locations(locations)
    return RedirectResponse(url="/admin/locations", status_code=303)


@app.get("/admin/locations/{location_id}/edit", response_class=HTMLResponse)
async def edit_location_page(location_id: str) -> Response:
    location = _get_location(location_id)
    if location is None:
        return RedirectResponse(url="/admin/locations", status_code=303)

    return HTMLResponse(
        _render_location_form(
            title="Редактировать локацию",
            action=f"/admin/locations/{location_id}/edit",
            name=str(location.get("name", "")),
            chat_id=location.get("chat_id"),
        )
    )


@app.post("/admin/locations/{location_id}/edit")
async def edit_location(location_id: str, request: Request) -> RedirectResponse:
    form_data = await _read_form_data(request)
    locations = _get_locations()

    for location in locations:
        if location.get("id") == location_id:
            location["name"] = form_data.get("name", "").strip()
            location["chat_id"] = _parse_chat_id(form_data.get("chat_id", ""))
            location.setdefault("projects", [])
            break

    _write_locations(locations)
    return RedirectResponse(url="/admin/locations", status_code=303)


@app.post("/admin/locations/{location_id}/delete")
async def delete_location(location_id: str) -> RedirectResponse:
    locations = [
        location
        for location in _get_locations()
        if location.get("id") != location_id
    ]
    _write_locations(locations)
    return RedirectResponse(url="/admin/locations", status_code=303)


@app.get("/admin/projects", response_class=HTMLResponse)
async def admin_projects_page() -> str:
    return _render_projects_page()


@app.get("/admin/projects/add", response_class=HTMLResponse)
async def add_project_page() -> str:
    return _render_project_form(
        title="Добавить проект",
        action="/admin/projects/add",
    )


@app.post("/admin/projects/add")
async def add_project(request: Request) -> RedirectResponse:
    form_data = await _read_form_data(request)
    location_id = form_data.get("location_id", "")
    locations = _get_locations()

    for location in locations:
        if location.get("id") == location_id:
            projects = _get_projects(location)
            projects.append(
                {
                    "id": _generate_project_id(projects),
                    "name": form_data.get("name", "").strip(),
                    "time_slots": [],
                }
            )
            location["projects"] = projects
            break

    _write_locations(locations)
    return RedirectResponse(url="/admin/projects", status_code=303)


@app.get("/admin/projects/{location_id}/{project_id}/edit", response_class=HTMLResponse)
async def edit_project_page(
    location_id: str,
    project_id: str,
) -> Response:
    result = _get_project(location_id, project_id)
    if result is None:
        return RedirectResponse(url="/admin/projects", status_code=303)

    _, project = result
    return HTMLResponse(
        _render_project_form(
            title="Редактировать проект",
            action=f"/admin/projects/{location_id}/{project_id}/edit",
            name=str(project.get("name", "")),
            selected_location_id=location_id,
        )
    )


@app.post("/admin/projects/{location_id}/{project_id}/edit")
async def edit_project(
    location_id: str,
    project_id: str,
    request: Request,
) -> RedirectResponse:
    form_data = await _read_form_data(request)
    new_location_id = form_data.get("location_id", "")
    locations = _get_locations()
    project_to_move: dict[str, Any] | None = None

    for location in locations:
        if location.get("id") != location_id:
            continue

        projects = _get_projects(location)
        for project in projects:
            if project.get("id") == project_id:
                project["name"] = form_data.get("name", "").strip()
                project.setdefault("time_slots", [])
                project_to_move = project
                break

        if project_to_move is not None and new_location_id != location_id:
            location["projects"] = [
                project
                for project in projects
                if project.get("id") != project_id
            ]
        break

    if project_to_move is not None and new_location_id != location_id:
        for location in locations:
            if location.get("id") == new_location_id:
                projects = _get_projects(location)
                project_to_move["id"] = _generate_project_id(projects)
                projects.append(project_to_move)
                location["projects"] = projects
                break

    _write_locations(locations)
    return RedirectResponse(url="/admin/projects", status_code=303)


@app.post("/admin/projects/{location_id}/{project_id}/delete")
async def delete_project(location_id: str, project_id: str) -> RedirectResponse:
    locations = _get_locations()

    for location in locations:
        if location.get("id") == location_id:
            location["projects"] = [
                project
                for project in _get_projects(location)
                if project.get("id") != project_id
            ]
            break

    _write_locations(locations)
    return RedirectResponse(url="/admin/projects", status_code=303)


@app.get("/admin/slots", response_class=HTMLResponse)
async def admin_slots_page(project_key: str = "") -> str:
    return _render_slots_page(project_key)


@app.get("/admin/slots/add", response_class=HTMLResponse)
async def add_slot_page() -> str:
    return _render_slot_form(
        title="Добавить слот",
        action="/admin/slots/add",
    )


@app.post("/admin/slots/add")
async def add_slot(request: Request) -> RedirectResponse:
    form_data = await _read_form_data(request)
    project_key = _parse_project_key(form_data.get("project_key", ""))
    if project_key is None:
        return RedirectResponse(url="/admin/slots", status_code=303)

    location_id, project_id = project_key
    locations = _get_locations()

    for location in locations:
        if location.get("id") != location_id:
            continue

        for project in _get_projects(location):
            if project.get("id") == project_id:
                time_slots = _get_time_slots(project)
                time_slots.append(form_data.get("time", "").strip())
                project["time_slots"] = time_slots
                break
        break

    _write_locations(locations)
    return RedirectResponse(url="/admin/slots", status_code=303)


@app.get("/admin/slots/{location_id}/{project_id}/{slot_index}/edit", response_class=HTMLResponse)
async def edit_slot_page(
    location_id: str,
    project_id: str,
    slot_index: int,
) -> Response:
    result = _get_project(location_id, project_id)
    if result is None:
        return RedirectResponse(url="/admin/slots", status_code=303)

    _, project = result
    time_slots = _get_time_slots(project)
    if slot_index < 0 or slot_index >= len(time_slots):
        return RedirectResponse(url="/admin/slots", status_code=303)

    return HTMLResponse(
        _render_slot_form(
            title="Редактировать слот",
            action=f"/admin/slots/{location_id}/{project_id}/{slot_index}/edit",
            time_slot=time_slots[slot_index],
            selected_project_key=f"{location_id}:{project_id}",
        )
    )


@app.post("/admin/slots/{location_id}/{project_id}/{slot_index}/edit")
async def edit_slot(
    location_id: str,
    project_id: str,
    slot_index: int,
    request: Request,
) -> RedirectResponse:
    form_data = await _read_form_data(request)
    new_project_key = _parse_project_key(form_data.get("project_key", ""))
    if new_project_key is None:
        return RedirectResponse(url="/admin/slots", status_code=303)

    locations = _get_locations()
    edited_time = form_data.get("time", "").strip()
    moved_slot: str | None = None

    for location in locations:
        if location.get("id") != location_id:
            continue

        for project in _get_projects(location):
            if project.get("id") != project_id:
                continue

            time_slots = _get_time_slots(project)
            if slot_index < 0 or slot_index >= len(time_slots):
                break

            if new_project_key == (location_id, project_id):
                time_slots[slot_index] = edited_time
                project["time_slots"] = time_slots
            else:
                moved_slot = edited_time
                project["time_slots"] = [
                    time_slot
                    for index, time_slot in enumerate(time_slots)
                    if index != slot_index
                ]
            break
        break

    if moved_slot is not None:
        new_location_id, new_project_id = new_project_key
        for location in locations:
            if location.get("id") != new_location_id:
                continue

            for project in _get_projects(location):
                if project.get("id") == new_project_id:
                    time_slots = _get_time_slots(project)
                    time_slots.append(moved_slot)
                    project["time_slots"] = time_slots
                    break
            break

    _write_locations(locations)
    return RedirectResponse(url="/admin/slots", status_code=303)


@app.post("/admin/slots/{location_id}/{project_id}/{slot_index}/delete")
async def delete_slot(
    location_id: str,
    project_id: str,
    slot_index: int,
) -> RedirectResponse:
    locations = _get_locations()

    for location in locations:
        if location.get("id") != location_id:
            continue

        for project in _get_projects(location):
            if project.get("id") != project_id:
                continue

            project["time_slots"] = [
                time_slot
                for index, time_slot in enumerate(_get_time_slots(project))
                if index != slot_index
            ]
            break
        break

    _write_locations(locations)
    return RedirectResponse(url="/admin/slots", status_code=303)
