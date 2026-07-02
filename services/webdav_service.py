import logging
import time
from http import HTTPStatus
from os import PathLike
from pathlib import Path
from typing import Callable, TypeVar

from webdav4.client import Client, HTTPError, ResourceAlreadyExists, ResourceNotFound

from config import WEBDAV_LOGIN, WEBDAV_PASSWORD, WEBDAV_URL

logger = logging.getLogger(__name__)
T = TypeVar("T")


class WebDAVService:
    def __init__(self) -> None:
        if not WEBDAV_URL:
            raise ValueError("WEBDAV_URL is not set")

        self.client = Client(
            WEBDAV_URL,
            auth=(WEBDAV_LOGIN, WEBDAV_PASSWORD),
            timeout=60,
        )

    def close(self) -> None:
        close_client = getattr(self.client, "close", None)
        if callable(close_client):
            close_client()
            return

        http_client = getattr(self.client, "_http", None)
        if http_client is not None and hasattr(http_client, "close"):
            http_client.close()

    def folder_exists(self, path: str) -> bool:
        try:
            return self.client.exists(path) and self.client.isdir(path)
        except ResourceNotFound:
            return False
        except HTTPError as exc:
            if exc.status_code in (HTTPStatus.NOT_FOUND, HTTPStatus.BAD_REQUEST):
                return False
            raise

    @staticmethod
    def _listing_paths(folder_path: str) -> tuple[str, ...]:
        normalized = folder_path.strip("/")
        if not normalized:
            return ("/",)

        with_slash = f"{normalized}/"
        if with_slash == normalized:
            return (normalized,)

        return (with_slash, normalized)

    @staticmethod
    def _parse_listing_entries(entries: list[str] | list[dict[str, object]], folder_path: str) -> set[str]:
        folder_name = Path(folder_path.strip("/")).name
        names: set[str] = set()

        for entry in entries:
            if isinstance(entry, dict):
                entry_path = str(entry.get("name") or entry.get("path") or "")
            else:
                entry_path = str(entry)

            entry_path = entry_path.rstrip("/")
            if not entry_path:
                continue

            name = Path(entry_path).name
            if not name or name == folder_name:
                continue

            names.add(name)

        return names

    def create_folder(self, path: str) -> None:
        try:
            self.client.mkdir(path)
        except ResourceAlreadyExists:
            return
        except HTTPError as exc:
            if exc.status_code == HTTPStatus.METHOD_NOT_ALLOWED:
                return
            raise

    def create_folders(self, path: str) -> None:
        current_path = ""

        for folder in path.strip("/").split("/"):
            current_path = f"{current_path}/{folder}" if current_path else folder
            self._with_retry(
                operation_name="WebDAV create folder",
                path=current_path,
                operation=lambda folder_path=current_path: self.create_folder(folder_path),
            )

    def list_file_names(self, folder_path: str) -> set[str]:
        def _collect() -> set[str]:
            last_error: Exception | None = None

            for listing_path in self._listing_paths(folder_path):
                try:
                    entries = self.client.ls(listing_path, detail=False)
                except ResourceNotFound:
                    continue
                except HTTPError as exc:
                    if exc.status_code in (
                        HTTPStatus.NOT_FOUND,
                        HTTPStatus.BAD_REQUEST,
                    ):
                        last_error = exc
                        continue
                    raise

                return self._parse_listing_entries(entries, folder_path)

            if last_error is not None:
                logger.warning(
                    "WebDAV listing unavailable for %s, assuming empty folder",
                    folder_path,
                    exc_info=last_error,
                )

            return set()

        return self._with_retry(
            operation_name="WebDAV list files",
            path=folder_path,
            operation=_collect,
        )

    def _with_retry(
        self,
        operation_name: str,
        path: str,
        operation: Callable[[], T],
    ) -> T:
        for attempt in range(1, 4):
            try:
                return operation()
            except Exception:
                if attempt == 3:
                    logger.exception("%s failed: %s", operation_name, path)
                    raise

                logger.warning(
                    "%s failed, retrying %s/3: %s",
                    operation_name,
                    attempt,
                    path,
                    exc_info=True,
                )
                time.sleep(1)

        raise RuntimeError(f"{operation_name} failed: {path}")

    def upload_file(
        self,
        local_path: str | PathLike[str],
        remote_path: str,
        overwrite: bool = True,
    ) -> None:
        # Mail.ru WebDAV returns 400 on PROPFIND; webdav4 calls exists() when overwrite=False.
        self._with_retry(
            operation_name="WebDAV upload",
            path=remote_path,
            operation=lambda: (
                self.client.upload_file(
                    from_path=local_path,
                    to_path=remote_path,
                    overwrite=overwrite,
                )
            ),
        )
