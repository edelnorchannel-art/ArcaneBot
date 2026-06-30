import logging
import time
from os import PathLike

from webdav4.client import Client

from config import WEBDAV_LOGIN, WEBDAV_PASSWORD, WEBDAV_URL

logger = logging.getLogger(__name__)


class WebDAVService:
    def __init__(self) -> None:
        if not WEBDAV_URL:
            raise ValueError("WEBDAV_URL is not set")

        self.client = Client(
            WEBDAV_URL,
            auth=(WEBDAV_LOGIN, WEBDAV_PASSWORD),
        )

    def folder_exists(self, path: str) -> bool:
        return self.client.exists(path) and self.client.isdir(path)

    def create_folder(self, path: str) -> None:
        if not self.folder_exists(path):
            self.client.mkdir(path)

    def create_folders(self, path: str) -> None:
        current_path = ""

        for folder in path.strip("/").split("/"):
            current_path = f"{current_path}/{folder}" if current_path else folder
            self.create_folder(current_path)

    def upload_file(
        self,
        local_path: str | PathLike[str],
        remote_path: str,
        overwrite: bool = False,
    ) -> None:
        for attempt in range(1, 4):
            try:
                self.client.upload_file(
                    from_path=local_path,
                    to_path=remote_path,
                    overwrite=overwrite,
                )
                return
            except Exception:
                if attempt == 3:
                    logger.exception("Failed to upload file to WebDAV: %s", remote_path)
                    raise

                logger.warning(
                    "WebDAV upload failed, retrying %s/3: %s",
                    attempt,
                    remote_path,
                    exc_info=True,
                )
                time.sleep(1)
