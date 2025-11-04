from __future__ import annotations

import functools
import logging
import os
import pathlib
import platform
import shutil
import subprocess
import tempfile

from comicapi.archivers import Archiver

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


class RarArchiver(Archiver):
    """RAR implementation"""

    enabled = rar_support
    exe = "rar"
    supported_extensions = frozenset({".cbr", ".rar"})

    _rar: rarfile.RarFile | None = None
    _rar_setup: rarfile.ToolSetup | None = None
    _writeable: bool | None = None
    _exe_ok: bool | None = None

    def __init__(self) -> None:
        super().__init__()
        self._filename_list: list[str] = []

    def get_comment(self) -> str:
        rarc = self.get_rar_obj()
        return (rarc.comment if rarc else "") or ""

    def set_comment(self, comment: str) -> None:
        self._reset()
        if not (rar_support and self.exe):
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
            raise OSError(f"Error writing comment to rar archive [exitcode: {result.returncode}]: {self.path}")

    def supports_comment(self) -> bool:
        return True

    def read_file(self, archive_file: str) -> bytes:
        rarc = self.get_rar_obj()
        if rarc is None:
            return b""

        tries = 0
        error = None
        entries = []
        while tries < 7:
            tries += 1
            try:
                data: bytes = rarc.open(archive_file).read()
                entries = [(rarc.getinfo(archive_file), data)]

                if entries[0][0].file_size != len(entries[0][1]):
                    logger.info(
                        "Error reading rar archive [file is not expected size: %d vs %d]  %s :: %s :: tries #%d",
                        entries[0][0].file_size,
                        len(entries[0][1]),
                        self.path,
                        archive_file,
                        tries,
                    )
                    error = OSError(
                        '"Error reading rar archive [file is not expected size: {:d} vs {:d}]  {} :: {} :: tries #{:d}"'.format(
                            entries[0][0].file_size,
                            len(entries[0][1]),
                            self.path,
                            archive_file,
                            tries,
                        )
                    )
                    continue

            except OSError as e:
                logger.error(
                    "Error reading file from rar archive [%s]: %s :: %s :: tries #%d", e, self.path, archive_file, tries
                )
                error = OSError(
                    f"Error reading file from rar archive [{e}]: {self.path} :: {archive_file} :: tries#{tries}"
                )
            except Exception as e:
                logger.error(
                    "Unexpected exception reading rar archive [%s]: %s :: %s :: tries #%d",
                    e,
                    self.path,
                    archive_file,
                    tries,
                )
                raise RuntimeError(
                    f"Unexpected exception reading file from rar archive [{e}]: {self.path} :: {archive_file} :: tries#{tries}"
                )

            if error is None:
                # Success, return early. Entries is a list of of tuples:  ( rarinfo, filedata)
                if len(entries) == 1:
                    return entries[0][1]
                raise OSError(
                    f"Error reading file from rar archive [File not found]: {self.path} :: {archive_file} :: tries#{tries}"
                )

        if error is None:
            # Somehow we have success but exited the loop
            raise RuntimeError("Something failed")
        raise error

    def remove_file(self, archive_file: str) -> None:
        self._reset()
        if not self.exe:
            return
        working_dir = os.path.dirname(os.path.abspath(self.path))
        # use external program to remove file from Rar archive
        try:
            result = subprocess.run(
                [self.exe, "d", f"-w{working_dir}", "-c-", self.path, archive_file],
                startupinfo=STARTUPINFO,
                stdin=subprocess.DEVNULL,
                capture_output=True,
                encoding="utf-8",
                cwd=self.path.absolute().parent,
            )
        except Exception as e:
            raise OSError(f"Error removing file from rar archive [{e}]: {self.path}:: {archive_file}")

        if result.returncode != 0:
            logger.error(
                "Error removing file from rar archive [exitcode: %d]: %s :: %s",
                result.returncode,
                self.path,
                archive_file,
            )
            raise RuntimeError(
                "Error removing file from rar archive [exitcode: {:d}]: {} :: {}".format(
                    result.returncode,
                    self.path,
                    archive_file,
                )
            )

    def write_file(self, archive_file: str, data: bytes) -> None:
        self._reset()
        if not self.exe:
            return

        archive_path = pathlib.PurePosixPath(archive_file)
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
            raise OSError(f"Error writing file to rar archive [{e}]: {self.path}:: {archive_file}")
        if result.returncode != 0:
            logger.error(
                "Error writing rar archive [exitcode: %d]: %s :: %s :: %s",
                result.returncode,
                self.path,
                archive_file,
                result.stderr,
            )
            raise OSError(
                f"Error writing file to rar archive [exitcode: {result.returncode}]: {self.path}:: {archive_file}"
            )

    def get_filename_list(self) -> list[str]:
        if self._filename_list:
            return self._filename_list
        rarc = self.get_rar_obj()
        tries = 0
        if not (rar_support and rarc):
            return []

        error = None
        while tries < 7:
            tries += 1
            try:
                namelist = []
                for item in rarc.infolist():
                    if item.file_size != 0:
                        namelist.append(item.filename)

            except OSError as e:
                logger.error("Error listing files in rar archive [%s]: %s :: attempt #%d", e, self.path, tries)
                error = OSError(f"Error listing files in rar archive [{e}]: {self.path} :: tries#{tries}")
            else:
                self._filename_list = namelist
                return self._filename_list

        if error is None:
            # Somehow we have success but exited the loop
            raise RuntimeError("Something failed")
        raise error

    def supports_files(self) -> bool:
        return True

    def copy_from_archive(self, other_archive: Archiver) -> None:
        """Replace the current archive with one copied from another archive"""
        self._reset()
        try:
            with tempfile.TemporaryDirectory() as tmp_dir:
                tmp_path = pathlib.Path(tmp_dir)
                rar_cwd = tmp_path / "rar"
                rar_cwd.mkdir(exist_ok=True)
                rar_path = (tmp_path / self.path.name).with_suffix(".rar")
                working_dir = os.path.dirname(os.path.abspath(self.path))

                for filename in other_archive.get_filename_list():
                    (rar_cwd / filename).parent.mkdir(exist_ok=True, parents=True)
                    data = other_archive.read_file(filename)
                    if data is not None:
                        with open(rar_cwd / filename, mode="w+b") as tmp_file:
                            tmp_file.write(data)
                result = subprocess.run(
                    [self.exe, "a", f"-w{working_dir}", "-r", "-c-", str(rar_path.absolute()), "."],
                    cwd=rar_cwd.absolute(),
                    startupinfo=STARTUPINFO,
                    stdin=subprocess.DEVNULL,
                    capture_output=True,
                    encoding="utf-8",
                )

                self.path.unlink(missing_ok=True)
                shutil.move(rar_path, self.path)
        except Exception as e:
            logger.exception("Error while copying to rar archive [%s]: from %s to %s", e, other_archive.path, self.path)
            raise OSError(f"Error listing files in rar archive [{e}]: from {other_archive.path} to {self.path}") from e
        if result.returncode != 0:
            logger.error(
                "Error while copying to rar archive [exitcode: %d]: %s: %s",
                result.returncode,
                self.path,
                result.stderr,
            )
            raise OSError(
                f"Error while copying to rar archive [exitcode: {result.returncode}]: {self.path}: {result.stderr}"
            )

    @classmethod
    @functools.cache
    def _log_not_writeable(cls, exe: str) -> None:
        logger.warning("Unable to find a useable copy of %r, will not be able to write rar files", exe)

    def is_writable(self) -> bool:
        return bool(self._writeable and bool(self.exe and (os.path.exists(self.exe) or shutil.which(self.exe))))

    def extension(self) -> str:
        return ".cbr"

    def name(self) -> str:
        return "RAR"

    @classmethod
    def _setup_rar(cls) -> None:

        cls._exe_ok = False
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
                cls._exe_ok = True
            except OSError:
                cls._writeable = False

        if cls._rar_setup is None:
            assert rarfile
            orig = rarfile.UNRAR_TOOL
            if cls._exe_ok:
                # pyrefly: ignore [bad-assignment]
                rarfile.UNRAR_TOOL = cls.exe
            success = False
            try:
                # First we disable 7z as it's known to have issues with current rar format
                # Should probably also disable bsdtar as macos bsdtar has issues with `--` added directly after the `-f` flag
                cls._rar_setup = rarfile.tool_setup(sevenzip=False, sevenzip2=False, force=True)
                success = True
            except rarfile.RarCannotExec as e:
                logger.debug("Failed to setup tool for rarfile", exc_info=e)
                rarfile.UNRAR_TOOL = orig

            try:
                if not success:
                    cls._rar_setup = rarfile.tool_setup(force=True)
            except rarfile.RarCannotExec as e:
                logger.info(e)

        if not cls._writeable:
            cls._log_not_writeable(cls.exe or "rar")

    @classmethod
    def is_valid(cls, path: pathlib.Path) -> bool:
        if rar_support:
            assert rarfile
            cls._setup_rar()

            # Fallback to standard
            try:
                return rarfile.is_rarfile(str(path))
            except rarfile.RarCannotExec as e:
                logger.info(e)
        return False

    def _reset(self) -> None:
        self._rar = None
        self._filename_list = []

    def get_rar_obj(self) -> rarfile.RarFile | None:
        if self._rar is not None:
            return self._rar
        if rar_support:
            try:
                rarc = rarfile.RarFile(str(self.path))
                self._rar = rarc
            except (OSError, rarfile.Error) as e:
                logger.error("Unable to get rar object [%s]: %s", e, self.path)
            else:
                return rarc

        return None
