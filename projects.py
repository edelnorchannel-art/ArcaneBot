PROJECTS: dict[str, dict] = {
    "project_1": {
        "name": "Катарсис",
        "time_slots": ["09:10", "10:25", "11:40", "12:55", "14:10", "15:25", "16:40", "17:55", "19:10", "20:25", "21:40", "22:55", "00:10", "01:25", "02:40"],
    },
    "project_2": {
        "name": "Дурак",
        "time_slots": ["09:30", "10:45", "12:00", "13:15", "14:30", "15:45", "17:00", "18:15", "19:30", "20:45", "22:00", "23:15", "00:30", "01:45", "03:00"],
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
