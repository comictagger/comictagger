from __future__ import annotations

import functools
import logging
import os
import pathlib
import platform
import shutil
import subprocess
import tempfile
from collections.abc import Collection, Iterable

from comicapi.comic import BadComic, WrongType
from comicapi.tags import TagLocation

try:
    import rarfile

    rar_support = True
except ImportError:
    rar_support = False


logger = logging.getLogger(__name__)

if not rar_support:
    logger.error("rar unavailable")
# windows only, keeps the cmd.exe from popping up
STARTUPINFO = None
if platform.system() == "Windows":
    STARTUPINFO = subprocess.STARTUPINFO()  # type: ignore
    STARTUPINFO.dwFlags |= subprocess.STARTF_USESHOWWINDOW  # type: ignore


class RarComic:
    """RAR implementation"""

    name = "RAR"

    enabled = rar_support

    tag_locations = frozenset((TagLocation.FILE, TagLocation.COMMENT))

    extension = ".cbr"
    supported_extensions = frozenset({".cbr", ".rar"})

    exe = "rar"

    _rar: rarfile.RarFile | None = None
    _rar_setup: rarfile.ToolSetup | None = None
    _writeable: bool | None = None

    def __init__(self, path: pathlib.Path) -> None:
        self.path = path
        self._filename_list: list[str] = []

    def read_comment(self) -> str:
        rarc = self._get_rar_obj()
        return (rarc.comment if rarc else "") or ""

    def write_comment(self, comment: str) -> None:
        self._reset()
        if not self.is_writable():
            return

        try:
            # write comment to temp file
            with tempfile.TemporaryDirectory() as tmp_dir:
                tmp_file = pathlib.Path(tmp_dir) / "rar_comment.txt"
                tmp_file.write_text(comment, encoding="utf-8")

                working_dir = os.path.dirname(os.path.abspath(self.path))

                # use external program to write comment to Rar archive
                proc_args = [
                    self.exe,
                    "c",
                    f"-w{working_dir}",
                    "-c-",
                    f"-z{tmp_file}",
                    str(self.path),
                ]
                result = subprocess.run(
                    proc_args,
                    startupinfo=STARTUPINFO,
                    stdin=subprocess.DEVNULL,
                    capture_output=True,
                    encoding="utf-8",
                    cwd=tmp_dir,
                )
        except Exception as e:
            logger.exception("Error writing comment to rar archive [%s]: %s", e, self.path)
            raise OSError(f"Error writing comment to rar archive [{e}]: {self.path}")
        if result.returncode != 0:
            logger.error(
                "Error writing comment to rar archive [exitcode: %d]: %s :: %s",
                result.returncode,
                self.path,
                result.stderr,
            )
            raise OSError(
                f"Error writing comment to rar archive check log for more information [exitcode: {result.returncode}]: {self.path}"
            )

    def supports_comment(self) -> bool:
        return True

    def read_file(self, filename: str) -> bytes:
        rarc = self._get_rar_obj()

        entry: tuple[rarfile.RarInfo, bytes] = (rarfile.RarInfo(), b"")
        try:
            data: bytes = rarc.open(filename).read()
            entry = (rarc.getinfo(filename), data)

        except rarfile.Error as e:
            logger.error("Error reading file from rar archive [%s]: %s :: %s", e, self.path, filename)
            raise BadComic(f"Error reading file from rar archive [{e}]: {self.path} :: {filename}")
        if entry[0].file_size != len(entry[1]):
            raise BadComic(
                '"Error reading rar archive [file is not expected size: {:d} vs {:d}]  {} :: {}"'.format(
                    entry[0].file_size,
                    len(entry[1]),
                    self.path,
                    filename,
                )
            )

        return entry[1]

    def read_files(self, filenames: Collection[str]) -> Iterable[bytes]:
        for filename in filenames:
            yield self.read_file(filename)

    def remove_files(self, filenames: Collection[str]) -> None:
        self._reset()
        if not self.is_writable():
            return
        working_dir = os.path.dirname(os.path.abspath(self.path))

        try:
            result = subprocess.run(
                [self.exe, "d", f"-w{working_dir}", "-c-", self.path, *filenames],
                startupinfo=STARTUPINFO,
                stdin=subprocess.DEVNULL,
                capture_output=True,
                encoding="utf-8",
                cwd=self.path.absolute().parent,
            )
        except Exception as e:
            raise OSError(f"Error removing files from rar archive [{e}]: {self.path}:: {filenames}")

        if result.returncode != 0:
            logger.error(
                "Error removing file from rar archive [exitcode: %d]: %s :: %s",
                result.returncode,
                self.path,
                filenames,
            )
            raise RuntimeError(
                "Error removing file from rar archive check log for more information [exitcode: {:d}]: {} :: {}".format(
                    result.returncode,
                    self.path,
                    filenames,
                )
            )

    def write_file(self, filename: str, data: bytes) -> None:
        self._reset()
        if not self.is_writable():
            return

        archive_path = pathlib.PurePosixPath(filename)
        archive_name = archive_path.name
        archive_parent = str(archive_path.parent).lstrip("./")
        working_dir = os.path.dirname(os.path.abspath(self.path))

        try:
            # use external program to write file to Rar archive
            result = subprocess.run(
                [
                    self.exe,
                    "a",
                    f"-w{working_dir}",
                    f"-si{archive_name}",
                    f"-ap{archive_parent}",
                    "-c-",
                    "-ep",
                    self.path,
                ],
                input=data,
                startupinfo=STARTUPINFO,
                capture_output=True,
                cwd=self.path.absolute().parent,
            )
        except Exception as e:
            raise OSError(f"Error writing file to rar archive [{e}]: {self.path}:: {filename}")
        if result.returncode != 0:
            logger.error(
                "Error writing rar archive [exitcode: %d]: %s :: %s :: %s",
                result.returncode,
                self.path,
                filename,
                result.stderr,
            )
            raise OSError(
                f"Error writing file to rar archive check log for more information [exitcode: {result.returncode}]: {self.path}:: {filename}"
            )

    def write_files(self, *, files: Iterable[tuple[str, bytes]], filenames: Collection[str]) -> None:
        # TODO: Write everything out to a temp directory first for performance
        try:
            for filename, data in files:
                self.write_file(filename, data)
        except Exception:
            list(files)
            raise

    def get_filename_list(self) -> list[str]:
        if not self.path.exists():
            return []
        if self._filename_list:
            return self._filename_list
        rarc = self._get_rar_obj()

        namelist = []
        for item in rarc.infolist():  # infolist should never cause an exception it's only an attribute access
            if item.file_size != 0:
                namelist.append(item.filename)
        self._filename_list = namelist
        return self._filename_list

    def is_writable(self) -> bool:
        return bool(self._writeable and bool(self.exe and (os.path.exists(self.exe) or shutil.which(self.exe))))

    def validate_archive(self) -> None:
        rarc = self._get_rar_obj()
        try:
            rarc.testrar()
        except rarfile.Error as e:
            raise BadComic(f"Error testing files in zip archive: {self.path} :: [{e}]")

    @staticmethod
    def check_path(path: pathlib.Path) -> None:
        RarComic._setup_rar()

        try:
            if not rarfile.is_rarfile(str(path)):
                raise WrongType
        except rarfile.RarCannotExec as e:
            raise BadComic(e)

    @classmethod
    def _setup_rar(cls) -> None:
        if cls._rar_setup is None:
            orig = rarfile.UNRAR_TOOL
            rarfile.UNRAR_TOOL = cls.exe
            try:
                cls._rar_setup = rarfile.tool_setup(sevenzip=False, sevenzip2=False, force=True)
            except rarfile.RarCannotExec:
                rarfile.UNRAR_TOOL = orig

            try:
                cls._rar_setup = rarfile.tool_setup(force=True)
            except rarfile.RarCannotExec as e:
                logger.info(e)
        if cls._writeable is None:
            try:
                cls._writeable = (
                    subprocess.run(
                        (cls.exe,),
                        startupinfo=STARTUPINFO,
                        capture_output=True,
                        # cwd=cls.path.absolute().parent,
                    )
                    .stdout.strip()
                    .startswith(b"RAR")
                )
            except OSError:
                cls._writeable = False

        if not cls._writeable:
            cls._log_not_writeable(cls.exe or "rar")

    @classmethod
    @functools.cache
    def _log_not_writeable(cls, exe: str) -> None:
        logger.warning("Unable to find a useable copy of %r, will not be able to write rar files", exe)

    def _reset(self) -> None:
        self._rar = None
        self._filename_list = []

    def _get_rar_obj(self) -> rarfile.RarFile:
        if self._rar is not None:
            return self._rar
        try:
            rarc = rarfile.RarFile(str(self.path))
            self._rar = rarc
            return rarc
        except rarfile.NotRarFile:
            raise WrongType
        except rarfile.Error as e:
            raise BadComic(f"Unable to get rar object [{e}]: {self.path}")
