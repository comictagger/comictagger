from __future__ import annotations

import logging
import os
import pathlib
import shutil
import tempfile
import zipfile
from typing import cast

import chardet
from zipremove import ZipFile

from comicapi.archivers import Archiver

logger = logging.getLogger(__name__)


class ZipArchiver(Archiver):
    """ZIP implementation"""

    supported_extensions = frozenset((".cbz", ".zip"))

    def __init__(self) -> None:
        super().__init__()
        self._filename_list: list[str] = []

    def supports_comment(self) -> bool:
        return True

    def get_comment(self) -> str:
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

    def set_comment(self, comment: str) -> None:
        try:
            with ZipFile(self.path, mode="a") as zf:
                zf.comment = bytes(comment, "utf-8")
        except Exception as e:
            logger.error("Error writing zip comment [%s]: %s", e, self.path)
            raise OSError(f"Error writing zip comment [{e}]: {self.path}") from e

    def read_file(self, archive_file: str) -> bytes:
        with ZipFile(self.path, mode="r") as zf:
            try:
                data = zf.read(archive_file)
            except (zipfile.BadZipfile, OSError) as e:
                logger.exception("Error reading file in zip archive [%s]: %s :: %s", e, self.path, archive_file)
                raise OSError(f"Error reading file in zip archive [{e}]: {self.path} :: {archive_file}") from e
        return data

    def remove_file(self, archive_file: str) -> None:
        files = self.get_filename_list()
        self._filename_list = []
        try:
            with ZipFile(self.path, mode="a", allowZip64=True, compression=zipfile.ZIP_DEFLATED) as zf:
                if archive_file in files:
                    zf.repack([zf.remove(archive_file)])
        except (zipfile.BadZipfile, OSError) as e:
            logger.error("Error removing file in zip archive [%s]: %s :: %s", e, self.path, archive_file)
            raise OSError(f"Error removing file in zip archive [{e}]: {self.path} :: {archive_file}") from e

    def write_file(self, archive_file: str, data: bytes) -> None:
        files = self.get_filename_list()
        self._filename_list = []

        try:
            # now just add the archive file as a new one
            with ZipFile(self.path, mode="a", allowZip64=True, compression=zipfile.ZIP_DEFLATED) as zf:
                if archive_file in files:
                    zf.repack([zf.remove(archive_file)])
                zf.writestr(archive_file, data)
        except (zipfile.BadZipfile, OSError) as e:
            logger.error("Error writing zip archive [%s]: %s :: %s", e, self.path, archive_file)
            raise OSError(f"Error writing zip archive [{e}]: {self.path} :: {archive_file}") from e

    def get_filename_list(self) -> list[str]:
        if self._filename_list:
            return self._filename_list
        try:
            with ZipFile(self.path, mode="r") as zf:
                self._filename_list = [file.filename for file in zf.infolist() if not file.is_dir()]
                return self._filename_list
        except (zipfile.BadZipfile, OSError) as e:
            logger.error("Error listing files in zip archive [%s]: %s", e, self.path)
            raise OSError(f"Error listing files in zip archive [{e}]: {self.path}") from e

    def supports_files(self) -> bool:
        return True

    def rebuild(self, exclude_list: list[str]) -> bool:
        """Zip helper func

        This recompresses the zip archive, without the files in the exclude_list
        """
        self._filename_list = []
        try:
            with ZipFile(
                tempfile.NamedTemporaryFile(dir=os.path.dirname(self.path), delete=False), "w", allowZip64=True
            ) as zout:
                with ZipFile(self.path, mode="r") as zin:
                    for item in zin.infolist():
                        buffer = zin.read(item.filename)
                        if item.filename not in exclude_list:
                            zout.writestr(item, buffer)

                    # preserve the old comment
                    zout.comment = zin.comment

                # replace with the new file
                self.path.unlink(missing_ok=True)
                zout.close()  # Required on windows

                shutil.move(cast(str, zout.filename), self.path)

        except (zipfile.BadZipfile, OSError) as e:
            logger.error("Error rebuilding zip file [%s]: %s", e, self.path)
            return False
        return True

    def copy_from_archive(self, other_archive: Archiver) -> None:
        """Replace the current zip with one copied from another archive"""
        self._filename_list = []
        try:
            with ZipFile(self.path, mode="w", allowZip64=True) as zout:
                for filename in other_archive.get_filename_list():
                    data = other_archive.read_file(filename)
                    if data is not None:
                        zout.writestr(filename, data)

            # preserve the old comment
            self.set_comment(other_archive.get_comment())
        except Exception as e:
            logger.error("Error while copying to zip archive [%s]: from %s to %s", e, other_archive.path, self.path)
            raise OSError(
                f"Error while copying to zip archive [{e}]: from {str(other_archive)!r} to {str(self.path)!r}"
            ) from e

    def is_writable(self) -> bool:
        return True

    def extension(self) -> str:
        return ".cbz"

    def name(self) -> str:
        return "ZIP"

    @classmethod
    def is_valid(cls, path: pathlib.Path) -> bool:
        return zipfile.is_zipfile(path)  # only checks central directory ot the end of the archive
