from typing import TypedDict

from locations import LOCATIONS


class LocationSummary(TypedDict):
    id: str
    name: str
    chat_id: int | None


class ProjectSummary(TypedDict):
    id: str
    name: str


def get_locations() -> list[LocationSummary]:
    return [
        {
            "id": location_id,
            "name": location["name"],
            "chat_id": location["chat_id"],
        }
        for location_id, location in LOCATIONS.items()
    ]


def get_location_projects(location_id: str) -> list[ProjectSummary]:
    location = LOCATIONS.get(location_id)
    if location is None:
        return []

    return [
        {"id": project_id, "name": project["name"]}
        for project_id, project in location["projects"].items()
    ]


def get_project_time_slots(location_id: str, project_id: str) -> list[str]:
    location = LOCATIONS.get(location_id)
    if location is None:
        return []

    project = location["projects"].get(project_id)
    if project is None:
        return []

    return list(project["time_slots"])
