PROJECTS: dict[str, dict] = {
    "project_1": {
        "name": "Катарсис",
        "time_slots": ["09:10", "10:25", "11:40", "12:55", "14:10", "15:25", "16:40", "17:55"],
    },
    "project_2": {
        "name": "Дурак",
        "time_slots": ["09:30", "10:45", "12:00", "13:15", "14:30", "15:45", "17:00", "18:15"],
    },
}


def get_projects() -> list[dict[str, str]]:
    return [
        {"id": project_id, "name": project["name"]}
        for project_id, project in PROJECTS.items()
    ]


def get_time_slots(project_id: str) -> list[str]:
    project = PROJECTS.get(project_id)
    if project is None:
        return []
    return list(project["time_slots"])
