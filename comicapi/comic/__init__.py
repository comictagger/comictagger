from __future__ import annotations

from .comicfile import BadComic, ComicFile, WrongType
from .folder import FolderComic
from .zip import ZipComic


class UnknownArchiver(ComicFile):
    name = "Unknown"
    enabled = False
    tag_locations = frozenset()
    extension = ""
    supported_extensions = frozenset()


__all__ = ("ComicFile", "UnknownArchiver", "FolderComic", "ZipComic", "BadComic", "WrongType")
