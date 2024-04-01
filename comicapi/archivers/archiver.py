from __future__ import annotations

import pathlib
from typing import Protocol, runtime_checkable


@runtime_checkable
class Archiver(Protocol):
    """Archiver Protocol"""

    """The path to the archive"""
    path: pathlib.Path

    """
    The name of the executable used for this archiver. This should be the base name of the executable.
    For example if 'rar.exe' is needed this should be "rar".
    If an executable is not used this should be the empty string.
    """
    exe: str = ""

    """
    Whether or not this archiver is enabled.
    If external imports are required and are not available this should be false. See rar.py and sevenzip.py.
    """
    enabled: bool = True

    def __init__(self) -> None:
        self.path = pathlib.Path()

    def get_comment(self) -> str:
        """
        Returns the comment from the current archive as a string.
        Should always return a string. If comments are not supported in the archive the empty string should be returned.
        """
        return ""

    def set_comment(self, comment: str) -> bool:
        """
        Returns True if the comment was successfully set on the current archive.
        Should always return a boolean. If comments are not supported in the archive False should be returned.
        """
        return False

    def supports_comment(self) -> bool:
        """
        Returns True if the current archive supports comments.
        Should always return a boolean. If comments are not supported in the archive False should be returned.
        """
        return False

    def read_file(self, archive_file: str) -> bytes:
        """
        Reads the named file from the current archive.
        archive_file should always come from the output of get_filename_list.
        Should always return a bytes object. Exceptions should be of the type OSError.
        """
        raise NotImplementedError

    def remove_file(self, archive_file: str) -> bool:
        """
        Removes the named file from the current archive.
        archive_file should always come from the output of get_filename_list.
        Should always return a boolean. Failures should return False.

        Rebuilding the archive without the named file is a standard way to remove a file.
        """
        return False

    def write_file(self, archive_file: str, data: bytes) -> bool:
        """
        Writes the named file to the current archive.
        Should always return a boolean. Failures should return False.
        """
        return False

    def get_filename_list(self) -> list[str]:
        """
        Returns a list of filenames in the current archive.
        Should always return a list of string. Failures should return an empty list.
        """
        return []

    def supports_files(self) -> bool:
        """
        Returns True if the current archive supports arbitrary non-picture files.
        Should always return a boolean.
        If arbitrary non-picture files are not supported in the archive False should be returned.
        """
        return False

    def copy_from_archive(self, other_archive: Archiver) -> bool:
        """
        Copies the contents of another archive to the current archive.
        Should always return a boolean. Failures should return False.
        """
        return False

    def is_writable(self) -> bool:
        """
        Returns True if the current archive is writeable
        Should always return a boolean. Failures should return False.
        """
        return False

    def extension(self) -> str:
        """
        Returns the extension that this archiver should use eg ".cbz".
        Should always return a string. Failures should return the empty string.
        """
        return ""

    def name(self) -> str:
        """
        Returns the name of this archiver for display purposes eg "CBZ".
        Should always return a string. Failures should return the empty string.
        """
        return ""

    @classmethod
    def is_valid(cls, path: pathlib.Path) -> bool:
        """
        Returns True if the given path can be opened by this archiver.
        Should always return a boolean. Failures should return False.
        """
        return False

    @classmethod
    def open(cls, path: pathlib.Path) -> Archiver:
        """
        Opens the given archive.
        Should always return a an Archver.
        Should never cause an exception no file operations should take place in this method,
        is_valid will always be called before open.
        """
        archiver = cls()
        archiver.path = path
        return archiver
