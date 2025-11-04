from __future__ import annotations

import logging
import os
import pathlib

from comicapi.archivers import Archiver

logger = logging.getLogger(__name__)


class FolderArchiver(Archiver):
    """Folder implementation"""

    hashable = False

    def __init__(self) -> None:
        super().__init__()
        self.comment_file_name = "ComicTaggerFolderComment.txt"
        self._filename_list: list[str] = []

    def get_comment(self) -> str:
        try:
            return (self.path / self.comment_file_name).read_text()
        except OSError:
            return ""

    def set_comment(self, comment: str) -> None:
        self._filename_list = []
        try:
            if comment:
                file_path = self.path / self.comment_file_name
                file_path.parent.mkdir(exist_ok=True, parents=True)
                file_path.write_text(comment, encoding="utf-8")
            else:
                (self.path / self.comment_file_name).unlink(missing_ok=True)
        except OSError as e:
            logger.error(
                "Error writing comment for folder archive [%s]: %s :: %s", e, self.path, self.comment_file_name
            )
            raise OSError(
                f"Error writing comment for folder archive [{e}]: {self.path} :: {self.comment_file_name}"
            ) from e

    def supports_comment(self) -> bool:
        return True

    def read_file(self, archive_file: str) -> bytes:
        try:
            return (self.path / archive_file).read_bytes()
        except OSError as e:
            logger.error("Error reading folder archive [%s]: %s :: %s", e, self.path, archive_file)
            raise OSError(f"Error reading folder archive [{e}]: {self.path} :: {archive_file}") from e

    def remove_file(self, archive_file: str) -> None:
        self._filename_list = []
        try:
            (self.path / archive_file).unlink(missing_ok=True)
        except OSError as e:
            logger.error("Error removing file for folder archive [%s]: %s :: %s", e, self.path, archive_file)
            raise OSError(f"Error removing file for folder archive [{e}]: {self.path} :: {archive_file}") from e

    def write_file(self, archive_file: str, data: bytes) -> None:
        self._filename_list = []
        try:
            file_path = self.path / archive_file
            file_path.parent.mkdir(exist_ok=True, parents=True)
            file_path.write_bytes(data)
        except OSError as e:
            logger.error("Error writing folder archive [%s]: %s :: %s", e, self.path, archive_file)
            raise OSError(f"Error writing folder archive [{e}]: {self.path} :: {archive_file}") from e

    def get_filename_list(self) -> list[str]:
        if self._filename_list:
            return self._filename_list
        filenames = []
        try:
            for root, _dirs, files in os.walk(self.path):
                for f in files:
                    filenames.append(os.path.relpath(os.path.join(root, f), self.path).replace(os.path.sep, "/"))
            self._filename_list = filenames
            return filenames
        except OSError as e:
            logger.error("Error listing files in folder archive [%s]: %s", e, self.path)
            raise OSError(f"Error listing files in folder archive [{e}]: {self.path}") from e

    def supports_files(self) -> bool:
        return True

    def copy_from_archive(self, other_archive: Archiver) -> None:
        """Replace the current zip with one copied from another archive"""
        self._filename_list = []
        try:
            for filename in other_archive.get_filename_list():
                data = other_archive.read_file(filename)
                if data is not None:
                    self.write_file(filename, data)

            # preserve the old comment
            self.set_comment(other_archive.get_comment())
        except Exception as e:
            logger.exception(
                "Error while copying to folder archive [%s]: from %s to %s", e, other_archive.path, self.path
            )
            raise OSError(
                f"Error while copying to folder archive [{e}]: from {str(other_archive)!r} to {str(self.path)!r}"
            ) from e

    def is_writable(self) -> bool:
        return True

    def name(self) -> str:
        return "Folder"

    @classmethod
    def is_valid(cls, path: pathlib.Path) -> bool:
        return path.is_dir()
