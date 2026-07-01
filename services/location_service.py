from typing import TypedDict

from services.config_service import ConfigService


class LocationSummary(TypedDict):
    id: str
    name: str
    chat_id: int | None


class ProjectSummary(TypedDict):
    id: str
    name: str


class ConfigProject(TypedDict):
    id: str
    name: str
    time_slots: list[str]


class ConfigLocation(TypedDict):
    id: str
    name: str
    chat_id: int | None
    projects: list[ConfigProject]


def _get_config_locations() -> list[ConfigLocation]:
    config = ConfigService().read_config()
    locations = config.get("locations", [])
    if not isinstance(locations, list):
        return []

    return [
        location
        for location in locations
        if isinstance(location, dict)
        and isinstance(location.get("id"), str)
        and isinstance(location.get("name"), str)
        and isinstance(location.get("projects"), list)
    ]


def _get_location(location_id: str) -> ConfigLocation | None:
    for location in _get_config_locations():
        if location["id"] == location_id:
            return location

    return None


def _get_chat_id(location: ConfigLocation) -> int | None:
    chat_id = location.get("chat_id")
    if chat_id is None:
        return None

    try:
        return int(chat_id)
    except (TypeError, ValueError):
        return None


def _get_projects(location: ConfigLocation) -> list[ConfigProject]:
    projects = location.get("projects", [])
    if not isinstance(projects, list):
        return []

    return [
        project
        for project in projects
        if isinstance(project, dict)
        and isinstance(project.get("id"), str)
        and isinstance(project.get("name"), str)
        and isinstance(project.get("time_slots"), list)
    ]


def get_locations() -> list[LocationSummary]:
    return [
        {
            "id": location["id"],
            "name": location["name"],
            "chat_id": _get_chat_id(location),
        }
        for location in _get_config_locations()
    ]


def get_location_projects(location_id: str) -> list[ProjectSummary]:
    location = _get_location(location_id)
    if location is None:
        return []

    return [
        {"id": project["id"], "name": project["name"]}
        for project in _get_projects(location)
    ]


def get_project_time_slots(location_id: str, project_id: str) -> list[str]:
    location = _get_location(location_id)
    if location is None:
        return []

    for project in _get_projects(location):
        if project["id"] == project_id:
            return [
                time_slot
                for time_slot in project["time_slots"]
                if isinstance(time_slot, str)
            ]

    return []
