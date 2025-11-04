from __future__ import annotations

import logging
import os
import pathlib
import shutil
import tempfile

from comicapi.archivers import Archiver

try:
    import py7zr

    z7_support = True
except ImportError:
    z7_support = False

logger = logging.getLogger(__name__)


class SevenZipArchiver(Archiver):
    """7Z implementation"""

    enabled = z7_support
    supported_extensions = frozenset({".7z", ".cb7"})

    def __init__(self) -> None:
        super().__init__()
        self._filename_list: list[str] = []

    def read_file(self, archive_file: str) -> bytes:
        data = b""
        try:
            with py7zr.SevenZipFile(self.path, "r") as zf:
                data = zf.read([archive_file])[archive_file].read()
        except (py7zr.Bad7zFile, OSError) as e:
            logger.error("Error reading file in 7zip archive [%s]: %s :: %s", e, self.path, archive_file)
            raise OSError(f"Error reading file in 7zip archive [{e}]: {self.path} :: {archive_file}") from e

        return data

    def remove_file(self, archive_file: str) -> None:
        self._filename_list = []
        return self.rebuild([archive_file])

    def write_file(self, archive_file: str, data: bytes) -> None:
        # At the moment, no other option but to rebuild the whole
        # archive w/o the indicated file. Very sucky, but maybe
        # another solution can be found
        files = self.get_filename_list()
        self._filename_list = []
        if archive_file in files:
            self.rebuild([archive_file])

        try:
            # now just add the archive file as a new one
            with py7zr.SevenZipFile(self.path, "a") as zf:
                zf.writestr(data, archive_file)
        except (py7zr.Bad7zFile, OSError) as e:
            logger.error("Error writing file in 7zip archive [%s]: %s :: %s", e, self.path, archive_file)
            raise OSError(f"Error writing file in 7zip archive [{e}]: {self.path} :: {archive_file}") from e

    def get_filename_list(self) -> list[str]:
        if self._filename_list:
            return self._filename_list
        try:
            with py7zr.SevenZipFile(self.path, "r") as zf:
                namelist: list[str] = [file.filename for file in zf.list() if not file.is_directory]

            self._filename_list = namelist
            return namelist
        except (py7zr.Bad7zFile, OSError) as e:
            logger.error("Error listing files in 7zip archive [%s]: %s", e, self.path)
            raise OSError(f"Error listing files in 7zip archive [{e}]: {self.path}") from e

    def supports_files(self) -> bool:
        return True

    def rebuild(self, exclude_list: list[str]) -> None:
        """Zip helper func

        This recompresses the zip archive, without the files in the exclude_list
        """

        self._filename_list = []
        try:
            # py7zr treats all archives as if they used solid compression
            # so we need to get the filename list first to read all the files at once
            with py7zr.SevenZipFile(self.path, mode="r") as zin:
                targets = [f for f in zin.getnames() if f not in exclude_list]
            with tempfile.NamedTemporaryFile(dir=os.path.dirname(self.path), delete=False) as tmp_file:
                with py7zr.SevenZipFile(tmp_file.file, mode="w") as zout:
                    with py7zr.SevenZipFile(self.path, mode="r") as zin:
                        for filename, buffer in zin.read(targets).items():
                            zout.writef(buffer, filename)

                self.path.unlink(missing_ok=True)
                tmp_file.close()  # Required on windows

                shutil.move(tmp_file.name, self.path)
        except (py7zr.Bad7zFile, OSError) as e:
            logger.error("Error rebuilding 7zip archive [%s]: %s", e, self.path)
            raise OSError(f"Error rebuilding 7zip archive [{e}]: {self.path}") from e

    def copy_from_archive(self, other_archive: Archiver) -> None:
        """Replace the current zip with one copied from another archive"""
        self._filename_list = []
        try:
            with py7zr.SevenZipFile(self.path, "w") as zout:
                for filename in other_archive.get_filename_list():
                    data = other_archive.read_file(
                        filename
                    )  # This will be very inefficient if other_archive is a 7z file
                    if data is not None:
                        zout.writestr(data, filename)
        except Exception as e:
            logger.error("Error while copying to 7zip archive [%s]: from %s to %s", e, other_archive.path, self.path)
            raise OSError(f"Error while copying to 7zip archive [{e}]: from {other_archive.path} to {self.path}") from e

    def is_writable(self) -> bool:
        return True

    def extension(self) -> str:
        return ".cb7"

    def name(self) -> str:
        return "Seven Zip"

    @classmethod
    def is_valid(cls, path: pathlib.Path) -> bool:
        return py7zr.is_7zfile(path)
