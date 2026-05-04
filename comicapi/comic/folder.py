from __future__ import annotations

import logging
import os
import pathlib
from collections.abc import Collection

from comicapi.comic import ComicFile, WrongType
from comicapi.tags import TagLocation

logger = logging.getLogger(__name__)


class FolderComic(ComicFile):
    """Folder implementation"""

    name = "Folder"

    enabled = True

    tag_locations = frozenset((TagLocation.FILE,))

    extension = ""
    supported_extensions = frozenset()

    def __init__(self, path: pathlib.Path) -> None:
        super().__init__(path)
        self._filename_list: list[str] = []

    def get_filename_list(self) -> list[str]:
        if self._filename_list:
            return self._filename_list
        filenames = []
        for root, _dirs, files in os.walk(self.path):
            for f in files:
                filenames.append(os.path.relpath(os.path.join(root, f), self.path).replace(os.path.sep, "/"))
        self._filename_list = filenames
        return filenames

    def read_file(self, filename: str) -> bytes:
        return (self.path / filename).read_bytes()

    def remove_files(self, filenames: Collection[str]) -> None:
        self._filename_list = []
        for filename in filenames:
            (self.path / filename).unlink(missing_ok=True)

    def write_file(self, filename: str, data: bytes) -> None:
        self._filename_list = []
        file_path = self.path / filename
        file_path.parent.mkdir(exist_ok=True, parents=True)
        file_path.write_bytes(data)

    def is_writable(self) -> bool:
        return True

    @staticmethod
    def check_path(path: pathlib.Path) -> None:
        if path.is_dir():
            return
        raise WrongType
