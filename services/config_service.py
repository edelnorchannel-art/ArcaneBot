from copy import deepcopy
import json
from json import JSONDecodeError
from pathlib import Path
from typing import Any, ClassVar


class ConfigService:
    _cached_config: ClassVar[dict[str, Any] | None] = None
    _cached_mtime: ClassVar[float | None] = None

    def __init__(self) -> None:
        self.config_path = Path(__file__).resolve().parents[1] / "config" / "config.json"
        self.default_config = {"locations": []}
        self.ensure_config_exists()

    def ensure_config_exists(self) -> None:
        if self.config_path.exists():
            return

        self.write_config(self.default_config)

    def read_config(self) -> dict[str, Any]:
        self.ensure_config_exists()
        current_mtime = self.config_path.stat().st_mtime

        if (
            self.__class__._cached_config is not None
            and self.__class__._cached_mtime == current_mtime
        ):
            return deepcopy(self.__class__._cached_config)

        config = self._load_config()
        self.__class__._cached_config = config
        self.__class__._cached_mtime = current_mtime
        return deepcopy(config)

    def _load_config(self) -> dict[str, Any]:
        try:
            with self.config_path.open("r", encoding="utf-8") as file:
                config = json.load(file)
        except JSONDecodeError:
            return deepcopy(self.default_config)

        if not isinstance(config, dict):
            return deepcopy(self.default_config)

        config.setdefault("locations", [])
        return config

    def write_config(self, config: dict[str, Any]) -> None:
        self.config_path.parent.mkdir(parents=True, exist_ok=True)

        with self.config_path.open("w", encoding="utf-8") as file:
            json.dump(config, file, ensure_ascii=False, indent=2)

        self.__class__._cached_config = deepcopy(config)
        self.__class__._cached_mtime = self.config_path.stat().st_mtime
