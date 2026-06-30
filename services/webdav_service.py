import logging
import time
from http import HTTPStatus
from os import PathLike
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

    def folder_exists(self, path: str) -> bool:
        try:
            return self.client.exists(path) and self.client.isdir(path)
        except ResourceNotFound:
            return False
        except HTTPError as exc:
            if exc.status_code == HTTPStatus.NOT_FOUND:
                return False
            raise

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
        overwrite: bool = False,
    ) -> None:
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
