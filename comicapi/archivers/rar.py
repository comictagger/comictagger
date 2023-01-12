from __future__ import annotations

import logging
import os
import pathlib
import platform
import shutil
import subprocess
import tempfile
import time

from comicapi.archivers import UnknownArchiver

try:
    from unrar.cffi import rarfile

    rar_support = True
except ImportError:
    rar_support = False


logger = logging.getLogger(__name__)

if not rar_support:
    logger.error("unrar-cffi unavailable")


class RarArchiver(UnknownArchiver):
    """RAR implementation"""

    def __init__(self, path: pathlib.Path | str, rar_exe_path: str = "rar") -> None:
        super().__init__(path)
        self.rar_exe_path = shutil.which(rar_exe_path) or ""

        # windows only, keeps the cmd.exe from popping up
        if platform.system() == "Windows":
            self.startupinfo = subprocess.STARTUPINFO()  # type: ignore
            self.startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW  # type: ignore
        else:
            self.startupinfo = None

    def get_comment(self) -> str:
        rarc = self.get_rar_obj()
        return rarc.comment.decode("utf-8") if rarc else ""

    def set_comment(self, comment: str) -> bool:
        if rar_support and self.rar_exe_path:
            try:
                # write comment to temp file
                with tempfile.TemporaryDirectory() as tmp_dir:
                    tmp_file = pathlib.Path(tmp_dir) / "rar_comment.txt"
                    tmp_file.write_text(comment, encoding="utf-8")

                    working_dir = os.path.dirname(os.path.abspath(self.path))

                    # use external program to write comment to Rar archive
                    proc_args = [
                        self.rar_exe_path,
                        "c",
                        f"-w{working_dir}",
                        "-c-",
                        f"-z{tmp_file}",
                        str(self.path),
                    ]
                    subprocess.run(
                        proc_args,
                        startupinfo=self.startupinfo,
                        stdout=subprocess.DEVNULL,
                        stdin=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        check=True,
                    )

                if platform.system() == "Darwin":
                    time.sleep(1)
            except (subprocess.CalledProcessError, OSError) as e:
                logger.exception("Error writing comment to rar archive [%s]: %s", e, self.path)
                return False
            else:
                return True
        else:
            return False

    def read_file(self, archive_file: str) -> bytes:

        rarc = self.get_rar_obj()
        if rarc is None:
            return b""

        tries = 0
        while tries < 7:
            try:
                tries = tries + 1
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
                    continue

            except OSError as e:
                logger.error("Error reading rar archive [%s]: %s :: %s :: tries #%d", e, self.path, archive_file, tries)
                time.sleep(1)
            except Exception as e:
                logger.error(
                    "Unexpected exception reading rar archive [%s]: %s :: %s :: tries #%d",
                    e,
                    self.path,
                    archive_file,
                    tries,
                )
                break

            else:
                # Success. Entries is a list of of tuples:  ( rarinfo, filedata)
                if len(entries) == 1:
                    return entries[0][1]

                raise OSError

        raise OSError

    def remove_file(self, archive_file: str) -> bool:
        if self.rar_exe_path:
            # use external program to remove file from Rar archive
            result = subprocess.run(
                [self.rar_exe_path, "d", "-c-", self.path, archive_file],
                startupinfo=self.startupinfo,
                stdout=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

            if platform.system() == "Darwin":
                time.sleep(1)
            if result.returncode != 0:
                logger.error(
                    "Error removing file from rar archive [exitcode: %d]: %s :: %s",
                    result.returncode,
                    self.path,
                    archive_file,
                )
                return False
            return True
        else:
            return False

    def write_file(self, archive_file: str, data: bytes) -> bool:
        if self.rar_exe_path:
            archive_path = pathlib.PurePosixPath(archive_file)
            archive_name = archive_path.name
            archive_parent = str(archive_path.parent).lstrip("./")

            # use external program to write file to Rar archive
            result = subprocess.run(
                [self.rar_exe_path, "a", f"-si{archive_name}", f"-ap{archive_parent}", "-c-", "-ep", self.path],
                input=data,
                startupinfo=self.startupinfo,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

            if platform.system() == "Darwin":
                time.sleep(1)
            if result.returncode != 0:
                logger.error(
                    "Error writing rar archive [exitcode: %d]: %s :: %s", result.returncode, self.path, archive_file
                )
                return False
            else:
                return True
        else:
            return False

    def get_filename_list(self) -> list[str]:
        rarc = self.get_rar_obj()
        tries = 0
        if rar_support and rarc:
            while tries < 7:
                try:
                    tries = tries + 1
                    namelist = []
                    for item in rarc.infolist():
                        if item.file_size != 0:
                            namelist.append(item.filename)

                except OSError as e:
                    logger.error("Error listing files in rar archive [%s]: %s :: attempt #%d", e, self.path, tries)
                    time.sleep(1)

                else:
                    return namelist
        return []

    def copy_from_archive(self, other_archive: UnknownArchiver) -> bool:
        """Replace the current archive with one copied from another archive"""
        try:
            with tempfile.TemporaryDirectory() as tmp_dir:
                tmp_path = pathlib.Path(tmp_dir)
                rar_cwd = tmp_path / "rar"
                rar_cwd.mkdir(exist_ok=True)
                rar_path = (tmp_path / self.path.name).with_suffix(".rar")

                for filename in other_archive.get_filename_list():
                    (rar_cwd / filename).parent.mkdir(exist_ok=True, parents=True)
                    data = other_archive.read_file(filename)
                    if data is not None:
                        with open(rar_cwd / filename, mode="w+b") as tmp_file:
                            tmp_file.write(data)
                result = subprocess.run(
                    [self.rar_exe_path, "a", "-r", "-c-", str(rar_path.absolute()), "."],
                    cwd=rar_cwd.absolute(),
                    startupinfo=self.startupinfo,
                    stdout=subprocess.DEVNULL,
                    stdin=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                if result.returncode != 0:
                    logger.error("Error while copying to rar archive [exitcode: %d]: %s", result.returncode, self.path)
                    return False

                self.path.unlink(missing_ok=True)
                shutil.move(rar_path, self.path)
        except Exception as e:
            logger.exception("Error while copying to rar archive [%s]: from %s to %s", e, other_archive.path, self.path)
            return False
        else:
            return True

    def get_rar_obj(self) -> rarfile.RarFile | None:
        if rar_support:
            try:
                rarc = rarfile.RarFile(str(self.path))
            except (OSError, rarfile.RarFileError) as e:
                logger.error("Unable to get rar object [%s]: %s", e, self.path)
            else:
                return rarc

        return None
