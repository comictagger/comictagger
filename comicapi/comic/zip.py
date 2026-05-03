from __future__ import annotations

import logging
import pathlib
from collections.abc import Collection, Iterable

import chardet
from zipremove import ZIP_DEFLATED, BadZipfile, ZipFile, is_zipfile

from comicapi.comic import BadComic, ComicFile, WrongType
from comicapi.tags import TagLocation

logger = logging.getLogger(__name__)


class ZipComic(ComicFile):
    """ZIP implementation"""

    name = "ZIP"
    enabled = True

    tag_locations = frozenset((TagLocation.FILE, TagLocation.COMMENT))

    extension = ".cbz"
    supported_extensions = frozenset((".cbz", ".zip"))

    exe = ""

    def __init__(self, path: pathlib.Path) -> None:
        self.path = path
        if not self.path.exists():
            with ZipFile(self.path, mode="w"):
                ...
        self._filename_list: list[str] = []

    def get_filename_list(self) -> list[str]:
        if self._filename_list:
            return self._filename_list
        try:
            with ZipFile(self.path, mode="r") as zf:
                self._filename_list = [file.filename for file in zf.infolist() if not file.is_dir()]
                return self._filename_list
        except BadZipfile as e:
            raise BadComic(f"Error listing files in zip archive [{e}]: {self.path}") from e

    def read_comment(self) -> str:
        comment: str = ""
        with ZipFile(self.path, "r") as zf:
            encoding = chardet.detect(zf.comment, True)
            if encoding["confidence"] > 60:
                try:
                    comment = zf.comment.decode(encoding["encoding"])
                except UnicodeDecodeError:
                    comment = zf.comment.decode("utf-8", errors="replace")
            else:
                comment = zf.comment.decode("utf-8", errors="replace")
        return comment

    def write_comment(self, comment: str) -> None:
        try:
            with ZipFile(self.path, mode="a") as zf:
                zf.comment = bytes(comment, "utf-8")
        except BadZipfile as e:
            raise BadComic(f"Error writing zip comment [{e}]: {self.path}") from e

    def read_file(self, filename: str) -> bytes:
        data = b""
        with ZipFile(self.path, mode="r") as zf:
            try:
                data = zf.read(filename)
            except BadZipfile as e:
                raise BadComic(f"Error reading file in zip archive [{e}]: {self.path} :: {filename}") from e
        return data

    def read_files(self, filenames: Collection[str]) -> Iterable[tuple[str, bytes]]:
        for filename in filenames:
            with ZipFile(self.path, mode="r") as zf:
                try:
                    yield filename, zf.read(filename)
                except BadZipfile as e:
                    raise BadComic(f"Error reading file in zip archive [{e}]: {self.path} :: {filename}") from e

    def remove_files(self, filenames: Collection[str]) -> None:
        files = self.get_filename_list()
        self._filename_list = []
        try:
            with ZipFile(self.path, mode="a", allowZip64=True, compression=ZIP_DEFLATED) as zf:
                removed_files = []
                for filename in filenames:
                    if filename in files:
                        removed_files.append(zf.remove(filename))
                zf.repack(removed_files)
        except BadZipfile as e:
            raise BadComic(f"Error removing file in zip archive [{e}]: {self.path} :: {filenames}") from e

    def write_files(self, *, files: Iterable[tuple[str, bytes]], filenames: Collection[str]) -> None:
        filenames = self.get_filename_list()
        self._filename_list = []
        filename = ""
        try:
            with ZipFile(self.path, mode="a", allowZip64=True, compression=ZIP_DEFLATED) as zf:
                removed = []
                for name, data in files:
                    filename = name
                    if name in filenames:
                        removed.append(zf.remove(name))

                    zf.writestr(name, data)

                filename = ""
                zf.repack(removed)
        except BadZipfile as e:
            list(files)
            raise BadComic(f"Error writing zip archive [{e}]: {self.path} :: {filename}") from e
        except Exception:
            list(files)
            raise

    def write_file(self, filename: str, data: bytes) -> None:
        files = self.get_filename_list()
        self._filename_list = []

        try:
            with ZipFile(self.path, mode="a", allowZip64=True, compression=ZIP_DEFLATED) as zf:
                if filename in files:
                    zf.repack([zf.remove(filename)])
                zf.writestr(filename, data)
        except BadZipfile as e:
            raise BadComic(f"Error writing zip archive [{e}]: {self.path} :: {filename}") from e

    def is_writable(self) -> bool:
        return True

    def validate_comic(self) -> None:
        try:
            with ZipFile(self.path, mode="r") as zf:
                filename = zf.testzip()
                if filename:
                    raise BadComic(f"Error testing files in zip archive: {self.path} :: {filename}")
        except BadZipfile as e:
            raise BadComic("Unable to open zip file") from e

    @staticmethod
    def check_path(path: pathlib.Path) -> None:
        if not is_zipfile(path):  # only checks central directory at the end of the archive
            raise WrongType


zc = ZipComic(pathlib.Path(""))
assert isinstance(zc, ComicFile)
