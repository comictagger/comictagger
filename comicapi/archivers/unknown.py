from __future__ import annotations

import pathlib


class UnknownArchiver:

    """Unknown implementation"""

    def __init__(self, path: pathlib.Path | str) -> None:
        self.path = pathlib.Path(path)

    def get_comment(self) -> str:
        return ""

    def set_comment(self, comment: str) -> bool:
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

    def copy_from_archive(self, other_archive: UnknownArchiver) -> bool:
        return False
