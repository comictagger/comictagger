from __future__ import annotations

import logging
import os
import pathlib
import shutil
import tempfile
from collections.abc import Collection, Iterable
from typing import IO, BinaryIO, cast

from comicapi.comic import BadComic, ComicFile, WrongType
from comicapi.tags import TagLocation

try:
    import py7zr

    z7_support = True
except ImportError:
    z7_support = False

logger = logging.getLogger(__name__)


class SevenZipComic(ComicFile):
    """7Z implementation"""

    name = "Seven Zip"
    enabled = z7_support

    tag_locations = frozenset((TagLocation.FILE,))

    extension = "cb7"
    supported_extensions = frozenset((".7z", ".cb7"))

    def __init__(self, path: pathlib.Path) -> None:
        super().__init__(path)
        if not path.exists():
            with py7zr.SevenZipFile(self.path, mode="w"):
                ...
        self._filename_list: list[str] = []

    def read_file(self, filename: str) -> bytes:
        try:
            with py7zr.SevenZipFile(self.path, "r") as zf:
                data = cast(dict[str, IO[bytes]], zf.read([filename]))[filename].read()  # typing is wrong in py7zr
                return data
        except (py7zr.Bad7zFile, OSError) as e:
            raise BadComic(f"Error reading file in 7zip archive [{e}]: {self.path} :: {filename}") from e

    def read_files(self, filenames: Collection[str]) -> Iterable[tuple[str, bytes]]:
        with py7zr.SevenZipFile(self.path, mode="r") as zin:
            for filename, buffer in cast(dict[str, IO[bytes]], zin.read(filenames)).items():
                yield filename, buffer.read()

    def remove_files(self, filenames: Collection[str]) -> None:
        self._filename_list = []
        return self._rebuild(filenames)

    def write_file(self, filename: str, data: bytes) -> None:
        # At the moment, no other option but to rebuild the whole
        # archive w/o the indicated file. Very sucky, but maybe
        # another solution can be found
        files = self.get_filename_list()
        self._filename_list = []
        if filename in files:
            self.remove_files([filename])

        try:
            # now just add the archive file as a new one
            with py7zr.SevenZipFile(self.path, "a") as zf:
                zf.writestr(data, filename)
        except py7zr.Bad7zFile as e:
            raise BadComic(f"Error writing file in 7zip archive [{e}]: {self.path} :: {filename}") from e

    def write_files(self, *, files: Iterable[tuple[str, bytes]], filenames: Collection[str]) -> None:
        # py7zr treats all archives as if they used solid compression
        # so we need to get the filename list first to read all the files at once

        self._filename_list = []
        current_filenames = self.get_filename_list()

        existing_files = set(current_filenames).difference(filenames)

        try:
            with tempfile.NamedTemporaryFile(dir=os.path.dirname(self.path), delete=False) as tmp_file:
                # py7zr has wrong typing here it accepts IO[bytes]
                with py7zr.SevenZipFile(cast(BinaryIO, tmp_file.file), mode="w") as zout:
                    with py7zr.SevenZipFile(self.path, mode="r") as zin:
                        old_files = cast(dict[str, IO[bytes]], zin.read())
                        for filename in existing_files:
                            zout.writef(old_files[filename], filename)
                        for filename, buffer in files:
                            zout.writestr(buffer, filename)

                self.path.unlink(missing_ok=True)
                tmp_file.close()  # Required on windows

                shutil.move(tmp_file.name, self.path)
        except py7zr.Bad7zFile as e:
            list(files)
            raise BadComic(f"Error rebuilding 7zip archive [{e}]: {self.path}") from e

    def get_filename_list(self) -> list[str]:
        if self._filename_list:
            return self._filename_list
        try:
            with py7zr.SevenZipFile(self.path, "r") as zf:
                namelist: list[str] = [file.filename for file in zf.list() if not file.is_directory]

            self._filename_list = namelist
            return namelist
        except py7zr.Bad7zFile as e:
            raise BadComic(f"Error listing files in 7zip archive [{e}]: {self.path}") from e

    def _rebuild(self, exclude_list: Collection[str]) -> None:
        # py7zr treats all archives as if they used solid compression
        # so we need to get the filename list first to read all the files at once

        self._filename_list = []
        filenames = self.get_filename_list()
        targets = set(filenames).difference(exclude_list)
        if targets == set(filenames):
            return

        try:
            with tempfile.NamedTemporaryFile(dir=os.path.dirname(self.path), delete=False) as tmp_file:
                # py7zr has wrong typing here it accepts IO[bytes]
                with py7zr.SevenZipFile(cast(BinaryIO, tmp_file.file), mode="w") as zout:
                    with py7zr.SevenZipFile(self.path, mode="r") as zin:
                        for filename, buffer in cast(dict[str, IO[bytes]], zin.read(targets)).items():
                            zout.writef(buffer, filename)

                self.path.unlink(missing_ok=True)
                tmp_file.close()  # Required on windows

                shutil.move(tmp_file.name, self.path)
        except py7zr.Bad7zFile as e:
            raise BadComic(f"Error rebuilding 7zip archive [{e}]: {self.path}") from e

    def is_writable(self) -> bool:
        return True

    def validate_comic(self) -> None:
        with py7zr.SevenZipFile(self.path, mode="r") as zf:
            filename = zf.testzip()
            if filename:
                raise BadComic(f"Error testing files in zip archive: {self.path} :: {filename}")

    @staticmethod
    def check_path(path: pathlib.Path) -> None:
        if not py7zr.is_7zfile(path):
            raise WrongType


assert isinstance(SevenZipComic(pathlib.Path("")), ComicFile)
