from __future__ import annotations

from comicapi.archivers.archiver import Archiver
from comicapi.archivers.folder import FolderArchiver
from comicapi.archivers.rar import RarArchiver
from comicapi.archivers.sevenzip import SevenZipArchiver
from comicapi.archivers.zip import ZipArchiver


class UnknownArchiver(Archiver):
    def name(self) -> str:
        return "Unknown"


__all__ = ["Archiver", "UnknownArchiver", "FolderArchiver", "RarArchiver", "ZipArchiver", "SevenZipArchiver"]
