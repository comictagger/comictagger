from __future__ import annotations

import pathlib
from collections.abc import Collection, Iterable
from typing import ClassVar, Protocol, runtime_checkable

from comicapi.genericmetadata import GenericMetadata
from comicapi.tags import TagLocation


class WrongType(Exception): ...


class BadComic(Exception): ...


@runtime_checkable
class ComicFile(Protocol):
    """A file containing a comic"""

    name: ClassVar[str]
    """
    Display name for this ComicFile

    Should be considered a ReadOnly attribute.
    """

    enabled: ClassVar[bool]
    """
    When false ComicTagger will refuse to load this ComicFile.
    If external imports are required and are not available this should be false. See rar.py and sevenzip.py.

    Should be considered a ReadOnly attribute.
    """

    tag_locations: ClassVar[frozenset[TagLocation]]

    extension: ClassVar[str]
    """
    Canonical extension.
    eg the Zip ComicFile uses ".cbz"

    Should be considered a ReadOnly attribute.
    """

    supported_extensions: ClassVar[frozenset[str]] = frozenset()
    """
    Only used to optimize ComicFile selection.
    For example the Zip ComicFile sets this to {".cbz", ".zip"}.
    `check_path` will be called to verify that an archive can be opened.

    Should be considered a ReadOnly attribute.
    """

    exe: ClassVar[str] = ""
    """
    Name of executable needed.
    eg The RAR ComicFile needs the 'rar' executable to write rar files
    The caller may set this value to explicitly state which excutable to use

    Should be considered a ReadOnly attribute.
    """

    supported_attributes: ClassVar[frozenset[str]] = frozenset()
    """
    Only needed when tag_storage includes TagLocation.CUSTOM
    For display to user in GUI. Has no effect on data processed or given
    """

    path: pathlib.Path
    """The path to the archive"""

    def __init__(self, path: pathlib.Path) -> None:
        """
        Opens the given archive.
        `check_path` will always be called before this.
        If the path does not exist then this is a new comic and the file should be created.
        Raise `comicapi.comic.BadComic` if the comic is corrupt but the correct archive type.
        Raise `comicapi.comic.WrongType` if the comic is not the correct type.

        NOTE: is_7zfile from py7zr does not validate that py7zr can open the file
        MUST not keep an open file.
        """

        self.path = path

    def get_filename_list(self) -> list[str]:
        """
        Returns a list of filenames in the archive.
        It is recommended to cache this list for performance.
        """
        raise NotImplementedError

    def is_writable(self) -> bool:
        """
        Retuns True if the archive is writeable.

        eg RAR archives can only be written if the rar executable is available.
        """
        raise NotImplementedError

    def read_comment(self) -> str:
        """
        Returns the comment from the archive as a string.
        Not Required if `comment_allowed` is False
        """
        raise NotImplementedError

    def write_comment(self, comment: str) -> None:
        """
        If an empty string is provided, remove the comment.
        Not Required if `comment_allowed` is False

        if get_filename_list is cached evict it during this call.
        """
        raise NotImplementedError

    def read_file(self, filename: str) -> bytes:
        """
        Reads the named file from the archive.
        filename should always come directly from the output of get_filename_list.
        """
        raise NotImplementedError

    def read_files(self, filenames: Collection[str]) -> Iterable[tuple[str, bytes]]:
        """
        Reads the named files from the archive.
        filenames should always come from the output of get_filename_list.
        Specifically this is used in an attempt to optimize exporting to a different Archive type.

        The iterable must always be completely read. If in doubt make a list.
        ```
        files_iterable = ComicFile.read_files(['file1','file2'])
        files = list(files_iterable)
        ```
        """
        for file in filenames:
            yield file, self.read_file(file)

    def write_file(self, filename: str, data: bytes) -> None:
        """
        Writes the named file to the archive.

        if get_filename_list is cached evict it during this call.
        """
        raise NotImplementedError

    def write_files(self, *, files: Iterable[tuple[str, bytes]], filenames: Collection[str]) -> None:
        """
        Specifically this is used in an attempt to optimize exporting to a different Archive type.

        `files` must always be completely read. If in doubt make a list.
        ```
        files = list(files)
        ```

        if get_filename_list is cached evict it during this call.
        """
        try:
            for name, data in files:
                self.write_file(name, data)
        except Exception:
            list(files)
            raise

    def remove_files(self, filenames: Collection[str]) -> None:
        """
        Removes the named files from the archive.
        filename will always come from the output of get_filename_list.

        if get_filename_list is cached evict it during this call.

        Rebuilding the archive without the named file is a standard (but incredibly inefficient) way to remove a file.
        """
        raise NotImplementedError

    @staticmethod
    def check_path(path: pathlib.Path) -> None:
        """
        Check if the given path is valid for this ComicFile.
        This method should do basic identification checks, validity and corruption checks can be done in `open`.

        Raise `comicapi.comic.BadComic` if the comic is corrupt but the correct comic type.

        Raise `comicapi.comic.WrongType` if the comic is not the correct type.
        """
        raise NotImplementedError

    def validate_comic(self) -> None:
        """Full validation of comic. Not required to be implemented"""
        raise NotImplementedError

    # ---

    def display_tags(self) -> str:
        """Only needed when when tag_storage includes TagLocation.CUSTOM. See `comicapi.tags.Tag.display_tags`"""
        raise NotImplementedError

    def load_tags(self) -> GenericMetadata:
        """Only needed when when tag_storage includes TagLocation.CUSTOM. See `comicapi.tags.Tag.read_tags`"""
        raise NotImplementedError

    def write_tags(self, version: str, metadata: GenericMetadata) -> None:
        """Only needed when when tag_storage includes TagLocation.CUSTOM. See `comicapi.tags.Tag.write_tags`"""
        raise NotImplementedError

    def has_tags(self) -> bool:
        """Only needed when when tag_storage includes TagLocation.CUSTOM"""
        raise NotImplementedError

    def remove_tags(self) -> None:
        """Only needed when when tag_storage includes TagLocation.CUSTOM"""
        raise NotImplementedError

    def supports_credit_role(self, role: str) -> bool:
        """
        Only needed when tag_storage includes TagLocation.CUSTOM

        For display to user in GUI. Has no effect on data processed or given
        """
        raise NotImplementedError
