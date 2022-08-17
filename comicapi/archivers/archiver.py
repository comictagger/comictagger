from __future__ import annotations

import pathlib
from typing import Protocol, runtime_checkable


@runtime_checkable
class Archiver(Protocol):

    """Archiver Protocol"""

    path: pathlib.Path
    enabled: bool = True

    def __init__(self):
        self.path = pathlib.Path()

    def get_comment(self) -> str:
        return ""

    def set_comment(self, comment: str) -> bool:
        return False

    def supports_comment(self) -> bool:
        return False

    def read_file(self, archive_file: str) -> bytes:
        raise NotImplementedError

    def remove_file(self, archive_file: str) -> bool:
        return False

    def write_file(self, archive_file: str, data: bytes) -> bool:
        return False

    def get_filename_list(self) -> list[str]:
        return []

    def rebuild(self, exclude_list: list[str]) -> bool:
        return False

    def copy_from_archive(self, other_archive: Archiver) -> bool:
        return False

    def is_writable(self) -> bool:
        return False

    def extension(self) -> str:
        return ""

    def name(self) -> str:
        return ""

    @classmethod
    def is_valid(cls, path: pathlib.Path) -> bool:
        return False

    @classmethod
    def open(cls, path: pathlib.Path) -> Archiver:
        archiver = cls()
        archiver.path = path
        return archiver
