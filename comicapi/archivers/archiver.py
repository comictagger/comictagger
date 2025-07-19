from __future__ import annotations

import pathlib
from collections.abc import Collection
from typing import ClassVar, Protocol, runtime_checkable


@runtime_checkable
class Archiver(Protocol):
    """Archiver Protocol"""

    path: pathlib.Path
    """The path to the archive"""

    exe: ClassVar[str] = ""
    """
    The name of the executable used for this archiver. This should be the base name of the executable.
    For example if 'rar.exe' is needed this should be "rar".
    If an executable is not used this should be the empty string.
    """

    enabled: ClassVar[bool] = True
    """
    Whether or not this archiver is enabled.
    If external imports are required and are not available this should be false. See rar.py and sevenzip.py.
    """

    hashable: bool = True
    """
    If self.path is a single file that can be hashed.
    For example directories cannot be hashed.
    """

    supported_extensions: Collection[str] = set()

    def __init__(self) -> None:
        self.path = pathlib.Path()

    def get_comment(self) -> str:
        """
        Returns the comment from the current archive as a string.
        If comments are not supported in the archive the empty string should be returned.
        """
        raise NotImplementedError

    def set_comment(self, comment: str) -> None:
        """
        Should raise an exception if a comment cannot be set
        """
        raise NotImplementedError

    def supports_comment(self) -> bool:
        """
        Returns True if the current archive supports comments.
        Should always return a boolean.
        MUST NOT cause an exception.
        """
        return False

    def read_file(self, archive_file: str) -> bytes:
        """
        Reads the named file from the current archive.
        archive_file should always come from the output of get_filename_list.
        Should always return a bytes object. Exceptions should be of the type OSError.
        """
        raise NotImplementedError

    def remove_file(self, archive_file: str) -> None:
        """
        Removes the named file from the current archive.
        archive_file will always come from the output of get_filename_list.

        Rebuilding the archive without the named file is a standard way to remove a file.
        """
        raise NotImplementedError

    def write_file(self, archive_file: str, data: bytes) -> None:
        """
        Writes the named file to the current archive.
        """
        raise NotImplementedError

    def get_filename_list(self) -> list[str]:
        """
        Returns a list of filenames in the current archive.
        Should always return a list of string.
        """
        raise NotImplementedError

    def supports_files(self) -> bool:
        """
        Returns True if the current archive supports arbitrary non-picture files.
        Should always return a boolean.
        MUST NOT cause an exception.
        """
        raise NotImplementedError

    def copy_from_archive(self, other_archive: Archiver) -> None:
        """
        Copies the contents of another achive to the current archive.
        """
        raise NotImplementedError

    def is_writable(self) -> bool:
        """
        Retuns True if the current archive is writeable
        """
        raise NotImplementedError

    def extension(self) -> str:
        """
        Returns the extension that this archiver should use eg ".cbz".
        MUST NOT cause an exception.
        """
        return ""

    def name(self) -> str:
        """
        Returns the name of this archiver for display purposes eg "CBZ".
        MUST NOT cause an exception.
        """
        return ""

    @classmethod
    def is_valid(cls, path: pathlib.Path) -> bool:
        """
        Returns True if the given path can be opened by this archiver.
        Should always return a boolean. Failures should return False.
        MUST NOT cause an exception.
        """
        return False

    @classmethod
    def open(cls, path: pathlib.Path) -> Archiver:
        """
        Opens the given archive.
        Should always return a an Archver.
        is_valid will always be called before open.
        Should validate that file can be opened.
        NOTE: is_7zfile from py7zr does not validate that py7zr can open the file
        MUST not keep file open.
        """
        archiver = cls()
        archiver.path = path
        return archiver
