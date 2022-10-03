"""A class to represent a single comic, be it file or folder of images"""
# Copyright 2012-2014 Anthony Beville
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
from __future__ import annotations

import io
import logging
import os
import pathlib
import platform
import shutil
import struct
import subprocess
import tempfile
import time
import zipfile
from typing import cast

import natsort
import py7zr
import wordninja

from comicapi import filenamelexer, filenameparser, utils
from comicapi.comet import CoMet
from comicapi.comicbookinfo import ComicBookInfo
from comicapi.comicinfoxml import ComicInfoXml
from comicapi.genericmetadata import GenericMetadata, PageType

try:
    from unrar.cffi import rarfile

    rar_support = True
except ImportError:
    rar_support = False

try:
    from PIL import Image

    pil_available = True
except ImportError:
    pil_available = False


logger = logging.getLogger(__name__)
if not pil_available:
    logger.error("PIL unavalable")
if not rar_support:
    logger.error("unrar-cffi unavailable")


class MetaDataStyle:
    CBI = 0
    CIX = 1
    COMET = 2
    name = ["ComicBookLover", "ComicRack", "CoMet"]
    short_name = ["cbl", "cr", "comet"]


class UnknownArchiver:

    """Unknown implementation"""

    def __init__(self, path: pathlib.Path | str) -> None:
        self.path = pathlib.Path(path)

    def get_comment(self) -> str:
        return ""

    def set_comment(self, comment: str) -> bool:
        return False

    def read_file(self, archive_file: str) -> bytes:
        raise NotImplementedError

    def remove_file(self, archive_file: str) -> bool:
        return False

    def write_file(self, archive_file: str, data: bytes) -> bool:
        return False

    def get_filename_list(self) -> list[str]:
        return []

    def rebuild(self, exclude_list: list[str]) -> bool:
        return False

    def copy_from_archive(self, other_archive: UnknownArchiver) -> bool:
        return False


class SevenZipArchiver(UnknownArchiver):

    """7Z implementation"""

    def __init__(self, path: pathlib.Path | str) -> None:
        super().__init__(path)

    # @todo: Implement Comment?
    def get_comment(self) -> str:
        return ""

    def set_comment(self, comment: str) -> bool:
        return False

    def read_file(self, archive_file: str) -> bytes:
        data = b""
        try:
            with py7zr.SevenZipFile(self.path, "r") as zf:
                data = zf.read(archive_file)[archive_file].read()
        except (py7zr.Bad7zFile, OSError) as e:
            logger.error("Error reading 7zip archive [%s]: %s :: %s", e, self.path, archive_file)
            raise

        return data

    def remove_file(self, archive_file: str) -> bool:
        return self.rebuild([archive_file])

    def write_file(self, archive_file: str, data: bytes) -> bool:
        # At the moment, no other option but to rebuild the whole
        # archive w/o the indicated file. Very sucky, but maybe
        # another solution can be found
        files = self.get_filename_list()
        if archive_file in files:
            if not self.rebuild([archive_file]):
                return False

        try:
            # now just add the archive file as a new one
            with py7zr.SevenZipFile(self.path, "a") as zf:
                zf.writestr(data, archive_file)
            return True
        except (py7zr.Bad7zFile, OSError) as e:
            logger.error("Error writing 7zip archive [%s]: %s :: %s", e, self.path, archive_file)
            return False

    def get_filename_list(self) -> list[str]:
        try:
            with py7zr.SevenZipFile(self.path, "r") as zf:
                namelist: list[str] = [file.filename for file in zf.list() if not file.is_directory]

            return namelist
        except (py7zr.Bad7zFile, OSError) as e:
            logger.error("Error listing files in 7zip archive [%s]: %s", e, self.path)
            return []

    def rebuild(self, exclude_list: list[str]) -> bool:
        """Zip helper func

        This recompresses the zip archive, without the files in the exclude_list
        """

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
            logger.error("Error rebuilding 7zip file [%s]: %s", e, self.path)
            return False
        return True

    def copy_from_archive(self, other_archive: UnknownArchiver) -> bool:
        """Replace the current zip with one copied from another archive"""
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
            return False
        else:
            return True


class ZipArchiver(UnknownArchiver):

    """ZIP implementation"""

    def __init__(self, path: pathlib.Path | str) -> None:
        super().__init__(path)

    def get_comment(self) -> str:
        with zipfile.ZipFile(self.path, "r") as zf:
            comment = zf.comment.decode("utf-8")
        return comment

    def set_comment(self, comment: str) -> bool:
        with zipfile.ZipFile(self.path, mode="a") as zf:
            zf.comment = bytes(comment, "utf-8")
        return True

    def read_file(self, archive_file: str) -> bytes:
        with zipfile.ZipFile(self.path, mode="r") as zf:
            try:
                data = zf.read(archive_file)
            except (zipfile.BadZipfile, OSError) as e:
                logger.error("Error reading zip archive [%s]: %s :: %s", e, self.path, archive_file)
                raise
        return data

    def remove_file(self, archive_file: str) -> bool:
        return self.rebuild([archive_file])

    def write_file(self, archive_file: str, data: bytes) -> bool:
        # At the moment, no other option but to rebuild the whole
        # zip archive w/o the indicated file. Very sucky, but maybe
        # another solution can be found
        files = self.get_filename_list()
        if archive_file in files:
            if not self.rebuild([archive_file]):
                return False

        try:
            # now just add the archive file as a new one
            with zipfile.ZipFile(self.path, mode="a", allowZip64=True, compression=zipfile.ZIP_DEFLATED) as zf:
                zf.writestr(archive_file, data)
            return True
        except (zipfile.BadZipfile, OSError) as e:
            logger.error("Error writing zip archive [%s]: %s :: %s", e, self.path, archive_file)
            return False

    def get_filename_list(self) -> list[str]:
        try:
            with zipfile.ZipFile(self.path, mode="r") as zf:
                namelist = [file.filename for file in zf.infolist() if not file.is_dir()]
            return namelist
        except (zipfile.BadZipfile, OSError) as e:
            logger.error("Error listing files in zip archive [%s]: %s", e, self.path)
            return []

    def rebuild(self, exclude_list: list[str]) -> bool:
        """Zip helper func

        This recompresses the zip archive, without the files in the exclude_list
        """
        try:
            with zipfile.ZipFile(
                tempfile.NamedTemporaryFile(dir=os.path.dirname(self.path), delete=False), "w", allowZip64=True
            ) as zout:
                with zipfile.ZipFile(self.path, mode="r") as zin:
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

    def copy_from_archive(self, other_archive: UnknownArchiver) -> bool:
        """Replace the current zip with one copied from another archive"""
        try:
            with zipfile.ZipFile(self.path, mode="w", allowZip64=True) as zout:
                for filename in other_archive.get_filename_list():
                    data = other_archive.read_file(filename)
                    if data is not None:
                        zout.writestr(filename, data)

            # preserve the old comment
            comment = other_archive.get_comment()
            if comment is not None:
                if not self.write_zip_comment(self.path, comment):
                    return False
        except Exception as e:
            logger.error("Error while copying to zip archive [%s]: from %s to %s", e, other_archive.path, self.path)
            return False
        else:
            return True

    def write_zip_comment(self, filename: pathlib.Path | str, comment: str) -> bool:
        """
        This is a custom function for writing a comment to a zip file,
        since the built-in one doesn't seem to work on Windows and Mac OS/X

        Fortunately, the zip comment is at the end of the file, and it's
        easy to manipulate.  See this website for more info:
        see: http://en.wikipedia.org/wiki/Zip_(file_format)#Structure
        """

        # get file size
        statinfo = os.stat(filename)
        file_length = statinfo.st_size

        try:
            with open(filename, mode="r+b") as file:

                # the starting position, relative to EOF
                pos = -4
                found = False

                # walk backwards to find the "End of Central Directory" record
                while (not found) and (-pos != file_length):
                    # seek, relative to EOF
                    file.seek(pos, 2)
                    value = file.read(4)

                    # look for the end of central directory signature
                    if bytearray(value) == bytearray([0x50, 0x4B, 0x05, 0x06]):
                        found = True
                    else:
                        # not found, step back another byte
                        pos = pos - 1

                if found:

                    # now skip forward 20 bytes to the comment length word
                    pos += 20
                    file.seek(pos, 2)

                    # Pack the length of the comment string
                    fmt = "H"  # one 2-byte integer
                    comment_length = struct.pack(fmt, len(comment))  # pack integer in a binary string

                    # write out the length
                    file.write(comment_length)
                    file.seek(pos + 2, 2)

                    # write out the comment itself
                    file.write(comment.encode("utf-8"))
                    file.truncate()
                else:
                    raise Exception("Could not find the End of Central Directory record!")
        except Exception as e:
            logger.error("Error writing comment to zip archive [%s]: %s", e, self.path)
            return False
        else:
            return True


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


class FolderArchiver(UnknownArchiver):

    """Folder implementation"""

    def __init__(self, path: pathlib.Path | str) -> None:
        super().__init__(path)
        self.comment_file_name = "ComicTaggerFolderComment.txt"

    def get_comment(self) -> str:
        try:
            return self.read_file(self.comment_file_name).decode("utf-8")
        except OSError:
            return ""

    def set_comment(self, comment: str) -> bool:
        if (self.path / self.comment_file_name).exists() or comment:
            return self.write_file(self.comment_file_name, comment.encode("utf-8"))
        return True

    def read_file(self, archive_file: str) -> bytes:
        try:
            with open(self.path / archive_file, mode="rb") as f:
                data = f.read()
        except OSError as e:
            logger.error("Error reading folder archive [%s]: %s :: %s", e, self.path, archive_file)
            raise

        return data

    def remove_file(self, archive_file: str) -> bool:
        try:
            (self.path / archive_file).unlink(missing_ok=True)
        except OSError as e:
            logger.error("Error removing file for folder archive [%s]: %s :: %s", e, self.path, archive_file)
            return False
        else:
            return True

    def write_file(self, archive_file: str, data: bytes) -> bool:
        try:
            file_path = self.path / archive_file
            file_path.parent.mkdir(exist_ok=True, parents=True)
            with open(self.path / archive_file, mode="wb") as f:
                f.write(data)
        except OSError as e:
            logger.error("Error writing folder archive [%s]: %s :: %s", e, self.path, archive_file)
            return False
        else:
            return True

    def get_filename_list(self) -> list[str]:
        filenames = []
        try:
            for root, _dirs, files in os.walk(self.path):
                for f in files:
                    filenames.append(os.path.relpath(os.path.join(root, f), self.path).replace(os.path.sep, "/"))
            return filenames
        except OSError as e:
            logger.error("Error listing files in folder archive [%s]: %s", e, self.path)
            return []

    def copy_from_archive(self, other_archive: UnknownArchiver) -> bool:
        """Replace the current zip with one copied from another archive"""
        try:
            for filename in other_archive.get_filename_list():
                data = other_archive.read_file(filename)
                if data is not None:
                    self.write_file(filename, data)

            # preserve the old comment
            comment = other_archive.get_comment()
            if comment is not None:
                if not self.set_comment(comment):
                    return False
        except Exception:
            logger.exception("Error while copying archive from %s to %s", other_archive.path, self.path)
            return False
        else:
            return True


class ComicArchive:
    logo_data = b""

    class ArchiveType:
        SevenZip, Zip, Rar, Folder, Pdf, Unknown = list(range(6))

    def __init__(
        self,
        path: pathlib.Path | str,
        rar_exe_path: str = "rar",
        default_image_path: pathlib.Path | str | None = None,
    ) -> None:
        self.cbi_md: GenericMetadata | None = None
        self.cix_md: GenericMetadata | None = None
        self.comet_filename: str | None = None
        self.comet_md: GenericMetadata | None = None
        self._has_cbi: bool | None = None
        self._has_cix: bool | None = None
        self._has_comet: bool | None = None
        self.path = pathlib.Path(path).absolute()
        self.page_count: int | None = None
        self.page_list: list[str] = []

        self.rar_exe_path = shutil.which(rar_exe_path or "rar") or ""
        self.ci_xml_filename = "ComicInfo.xml"
        self.comet_default_filename = "CoMet.xml"
        self.reset_cache()
        self.default_image_path = default_image_path

        # Use file extension to decide which archive test we do first
        ext = self.path.suffix

        self.archive_type = self.ArchiveType.Unknown
        self.archiver = UnknownArchiver(self.path)

        if ext in [".cbr", ".rar"]:
            if self.rar_test():
                self.archive_type = self.ArchiveType.Rar
                self.archiver = RarArchiver(self.path, rar_exe_path=self.rar_exe_path)

            elif self.zip_test():
                self.archive_type = self.ArchiveType.Zip
                self.archiver = ZipArchiver(self.path)
        else:
            if self.sevenzip_test():
                self.archive_type = self.ArchiveType.SevenZip
                self.archiver = SevenZipArchiver(self.path)

            elif self.zip_test():
                self.archive_type = self.ArchiveType.Zip
                self.archiver = ZipArchiver(self.path)

            elif self.rar_test():
                self.archive_type = self.ArchiveType.Rar
                self.archiver = RarArchiver(self.path, rar_exe_path=self.rar_exe_path)

            elif self.folder_test():
                self.archive_type = self.ArchiveType.Folder
                self.archiver = FolderArchiver(self.path)

        if not ComicArchive.logo_data and self.default_image_path:
            with open(self.default_image_path, mode="rb") as fd:
                ComicArchive.logo_data = fd.read()

    def reset_cache(self) -> None:
        """Clears the cached data"""

        self._has_cix = None
        self._has_cbi = None
        self._has_comet = None
        self.comet_filename = None
        self.page_count = None
        self.page_list = []
        self.cix_md = None
        self.cbi_md = None
        self.comet_md = None

    def load_cache(self, style_list: list[int]) -> None:
        for style in style_list:
            self.read_metadata(style)

    def rename(self, path: pathlib.Path | str) -> None:
        new_path = pathlib.Path(path).absolute()
        if new_path == self.path:
            return
        os.makedirs(new_path.parent, 0o777, True)
        shutil.move(self.path, new_path)
        self.path = new_path
        self.archiver.path = pathlib.Path(path)

    def sevenzip_test(self) -> bool:
        return py7zr.is_7zfile(self.path)

    def zip_test(self) -> bool:
        return zipfile.is_zipfile(self.path)

    def rar_test(self) -> bool:
        if rar_support:
            return rarfile.is_rarfile(str(self.path))
        return False

    def folder_test(self) -> bool:
        return self.path.is_dir()

    def is_sevenzip(self) -> bool:
        return self.archive_type == self.ArchiveType.SevenZip

    def is_zip(self) -> bool:
        return self.archive_type == self.ArchiveType.Zip

    def is_rar(self) -> bool:
        return self.archive_type == self.ArchiveType.Rar

    def is_pdf(self) -> bool:
        return self.archive_type == self.ArchiveType.Pdf

    def is_folder(self) -> bool:
        return self.archive_type == self.ArchiveType.Folder

    def is_writable(self, check_rar_status: bool = True) -> bool:
        if self.archive_type == self.ArchiveType.Unknown:
            return False

        if check_rar_status and self.is_rar() and not self.rar_exe_path:
            return False

        if not os.access(self.path, os.W_OK):
            return False

        if (self.archive_type != self.ArchiveType.Folder) and (not os.access(self.path.parent, os.W_OK)):
            return False

        return True

    def is_writable_for_style(self, data_style: int) -> bool:

        if (self.is_rar() or self.is_sevenzip()) and data_style == MetaDataStyle.CBI:
            return False

        return self.is_writable()

    def seems_to_be_a_comic_archive(self) -> bool:
        if (self.is_zip() or self.is_rar() or self.is_sevenzip() or self.is_folder()) and (
            self.get_number_of_pages() > 0
        ):
            return True

        return False

    def read_metadata(self, style: int) -> GenericMetadata:

        if style == MetaDataStyle.CIX:
            return self.read_cix()
        if style == MetaDataStyle.CBI:
            return self.read_cbi()
        if style == MetaDataStyle.COMET:
            return self.read_comet()
        return GenericMetadata()

    def write_metadata(self, metadata: GenericMetadata, style: int) -> bool:
        retcode = False
        if style == MetaDataStyle.CIX:
            retcode = self.write_cix(metadata)
        if style == MetaDataStyle.CBI:
            retcode = self.write_cbi(metadata)
        if style == MetaDataStyle.COMET:
            retcode = self.write_comet(metadata)
        return retcode

    def has_metadata(self, style: int) -> bool:
        if style == MetaDataStyle.CIX:
            return self.has_cix()
        if style == MetaDataStyle.CBI:
            return self.has_cbi()
        if style == MetaDataStyle.COMET:
            return self.has_comet()
        return False

    def remove_metadata(self, style: int) -> bool:
        retcode = True
        if style == MetaDataStyle.CIX:
            retcode = self.remove_cix()
        elif style == MetaDataStyle.CBI:
            retcode = self.remove_cbi()
        elif style == MetaDataStyle.COMET:
            retcode = self.remove_co_met()
        return retcode

    def get_page(self, index: int) -> bytes:
        image_data = b""

        filename = self.get_page_name(index)

        if filename:
            try:
                image_data = self.archiver.read_file(filename) or b""
            except Exception:
                logger.error("Error reading in page %d. Substituting logo page.", index)
                image_data = ComicArchive.logo_data

        return image_data

    def get_page_name(self, index: int) -> str:
        if index is None:
            return ""

        page_list = self.get_page_name_list()

        num_pages = len(page_list)
        if num_pages == 0 or index >= num_pages:
            return ""

        return page_list[index]

    def get_scanner_page_index(self) -> int | None:
        scanner_page_index = None

        # make a guess at the scanner page
        name_list = self.get_page_name_list()
        count = self.get_number_of_pages()

        # too few pages to really know
        if count < 5:
            return None

        # count the length of every filename, and count occurrences
        length_buckets: dict[int, int] = {}
        for name in name_list:
            fname = os.path.split(name)[1]
            length = len(fname)
            if length in length_buckets:
                length_buckets[length] += 1
            else:
                length_buckets[length] = 1

        # sort by most common
        sorted_buckets = sorted(length_buckets.items(), key=lambda tup: (tup[1], tup[0]), reverse=True)

        # statistical mode occurrence is first
        mode_length = sorted_buckets[0][0]

        # we are only going to consider the final image file:
        final_name = os.path.split(name_list[count - 1])[1]

        common_length_list = []
        for name in name_list:
            if len(os.path.split(name)[1]) == mode_length:
                common_length_list.append(os.path.split(name)[1])

        prefix = os.path.commonprefix(common_length_list)

        if mode_length <= 7 and prefix == "":
            # probably all numbers
            if len(final_name) > mode_length:
                scanner_page_index = count - 1

        # see if the last page doesn't start with the same prefix as most others
        elif not final_name.startswith(prefix):
            scanner_page_index = count - 1

        return scanner_page_index

    def get_page_name_list(self, sort_list: bool = True) -> list[str]:
        if not self.page_list:
            # get the list file names in the archive, and sort
            files: list[str] = self.archiver.get_filename_list()

            # seems like some archive creators are on Windows, and don't know about case-sensitivity!
            if sort_list:

                files = cast(list[str], natsort.os_sorted(files))

            # make a sub-list of image files
            self.page_list = []
            for name in files:
                if (
                    os.path.splitext(name)[1].casefold() in [".jpg", ".jpeg", ".png", ".gif", ".webp"]
                    and os.path.basename(name)[0] != "."
                ):
                    self.page_list.append(name)

        return self.page_list

    def get_number_of_pages(self) -> int:
        if self.page_count is None:
            self.page_count = len(self.get_page_name_list())
        return self.page_count

    def read_cbi(self) -> GenericMetadata:
        if self.cbi_md is None:
            raw_cbi = self.read_raw_cbi()
            if raw_cbi:
                self.cbi_md = ComicBookInfo().metadata_from_string(raw_cbi)
            else:
                self.cbi_md = GenericMetadata()

            self.cbi_md.set_default_page_list(self.get_number_of_pages())

        return self.cbi_md

    def read_raw_cbi(self) -> str:
        if not self.has_cbi():
            return ""

        return self.archiver.get_comment()

    def has_cbi(self) -> bool:
        if self._has_cbi is None:
            if not self.seems_to_be_a_comic_archive():
                self._has_cbi = False
            else:
                comment = self.archiver.get_comment()
                self._has_cbi = ComicBookInfo().validate_string(comment)

        return self._has_cbi

    def write_cbi(self, metadata: GenericMetadata) -> bool:
        if metadata is not None:
            try:
                self.apply_archive_info_to_metadata(metadata)
                cbi_string = ComicBookInfo().string_from_metadata(metadata)
                write_success = self.archiver.set_comment(cbi_string)
                if write_success:
                    self._has_cbi = True
                    self.cbi_md = metadata
                self.reset_cache()
                return write_success
            except Exception as e:
                logger.error("Error saving CBI! for %s: %s", self.path, e)

        return False

    def remove_cbi(self) -> bool:
        if self.has_cbi():
            write_success = self.archiver.set_comment("")
            if write_success:
                self._has_cbi = False
                self.cbi_md = None
            self.reset_cache()
            return write_success
        return True

    def read_cix(self) -> GenericMetadata:
        if self.cix_md is None:
            raw_cix = self.read_raw_cix()
            if raw_cix:
                self.cix_md = ComicInfoXml().metadata_from_string(raw_cix)
            else:
                self.cix_md = GenericMetadata()

            # validate the existing page list (make sure count is correct)
            if len(self.cix_md.pages) != 0:
                if len(self.cix_md.pages) != self.get_number_of_pages():
                    # pages array doesn't match the actual number of images we're seeing
                    # in the archive, so discard the data
                    self.cix_md.pages = []

            if len(self.cix_md.pages) == 0:
                self.cix_md.set_default_page_list(self.get_number_of_pages())

        return self.cix_md

    def read_raw_cix(self) -> bytes:
        if not self.has_cix():
            return b""
        try:
            raw_cix = self.archiver.read_file(self.ci_xml_filename) or b""
        except Exception as e:
            logger.error("Error reading in raw CIX! for %s: %s", self.path, e)
            raw_cix = b""
        return raw_cix

    def write_cix(self, metadata: GenericMetadata) -> bool:
        if metadata is not None:
            try:
                self.apply_archive_info_to_metadata(metadata, calc_page_sizes=True)
                raw_cix = self.read_raw_cix()
                cix_string = ComicInfoXml().string_from_metadata(metadata, xml=raw_cix)
                write_success = self.archiver.write_file(self.ci_xml_filename, cix_string.encode("utf-8"))
                if write_success:
                    self._has_cix = True
                    self.cix_md = metadata
                self.reset_cache()
                return write_success
            except Exception as e:
                logger.error("Error saving CIX! for %s: %s", self.path, e)

        return False

    def remove_cix(self) -> bool:
        if self.has_cix():
            write_success = self.archiver.remove_file(self.ci_xml_filename)
            if write_success:
                self._has_cix = False
                self.cix_md = None
            self.reset_cache()
            return write_success
        return True

    def has_cix(self) -> bool:
        if self._has_cix is None:

            if not self.seems_to_be_a_comic_archive():
                self._has_cix = False
            elif self.ci_xml_filename in self.archiver.get_filename_list():
                self._has_cix = True
            else:
                self._has_cix = False
        return self._has_cix

    def read_comet(self) -> GenericMetadata:
        if self.comet_md is None:
            raw_comet = self.read_raw_comet()
            if raw_comet is None or raw_comet == "":
                self.comet_md = GenericMetadata()
            else:
                self.comet_md = CoMet().metadata_from_string(raw_comet)

            self.comet_md.set_default_page_list(self.get_number_of_pages())
            # use the coverImage value from the comet_data to mark the cover in this struct
            # walk through list of images in file, and find the matching one for md.coverImage
            # need to remove the existing one in the default
            if self.comet_md.cover_image is not None:
                cover_idx = 0
                for idx, f in enumerate(self.get_page_name_list()):
                    if self.comet_md.cover_image == f:
                        cover_idx = idx
                        break
                if cover_idx != 0:
                    del self.comet_md.pages[0]["Type"]
                    self.comet_md.pages[cover_idx]["Type"] = PageType.FrontCover

        return self.comet_md

    def read_raw_comet(self) -> str:
        raw_comet = ""
        if not self.has_comet():
            raw_comet = ""
        else:
            try:
                raw_bytes = self.archiver.read_file(cast(str, self.comet_filename))
                if raw_bytes:
                    raw_comet = raw_bytes.decode("utf-8")
            except OSError as e:
                logger.exception("Error reading in raw CoMet!: %s", e)
        return raw_comet

    def write_comet(self, metadata: GenericMetadata) -> bool:

        if metadata is not None:
            if not self.has_comet():
                self.comet_filename = self.comet_default_filename

            self.apply_archive_info_to_metadata(metadata)
            # Set the coverImage value, if it's not the first page
            cover_idx = int(metadata.get_cover_page_index_list()[0])
            if cover_idx != 0:
                metadata.cover_image = self.get_page_name(cover_idx)

            comet_string = CoMet().string_from_metadata(metadata)
            write_success = self.archiver.write_file(cast(str, self.comet_filename), comet_string.encode("utf-8"))
            if write_success:
                self._has_comet = True
                self.comet_md = metadata
            self.reset_cache()
            return write_success

        return False

    def remove_co_met(self) -> bool:
        if self.has_comet():
            write_success = self.archiver.remove_file(cast(str, self.comet_filename))
            if write_success:
                self._has_comet = False
                self.comet_md = None
            self.reset_cache()
            return write_success
        return True

    def has_comet(self) -> bool:
        if self._has_comet is None:
            self._has_comet = False
            if not self.seems_to_be_a_comic_archive():
                return self._has_comet

            # look at all xml files in root, and search for CoMet data, get first
            for n in self.archiver.get_filename_list():
                if os.path.dirname(n) == "" and os.path.splitext(n)[1].casefold() == ".xml":
                    # read in XML file, and validate it
                    data = ""
                    try:
                        d = self.archiver.read_file(n)
                        if d:
                            data = d.decode("utf-8")
                    except Exception as e:
                        logger.warning("Error reading in Comet XML for validation! from %s: %s", self.path, e)
                    if CoMet().validate_string(data):
                        # since we found it, save it!
                        self.comet_filename = n
                        self._has_comet = True
                        break

        return self._has_comet

    def apply_archive_info_to_metadata(self, md: GenericMetadata, calc_page_sizes: bool = False) -> None:
        md.page_count = self.get_number_of_pages()

        if calc_page_sizes:
            for index, p in enumerate(md.pages):
                idx = int(p["Image"])
                if pil_available:
                    if "ImageSize" not in p or "ImageHeight" not in p or "ImageWidth" not in p:
                        data = self.get_page(idx)
                        if data:
                            try:
                                if isinstance(data, bytes):
                                    im = Image.open(io.BytesIO(data))
                                else:
                                    im = Image.open(io.StringIO(data))
                                w, h = im.size

                                p["ImageSize"] = str(len(data))
                                p["ImageHeight"] = str(h)
                                p["ImageWidth"] = str(w)
                            except Exception as e:
                                logger.warning("Error decoding image [%s] %s :: image %s", e, self.path, index)
                                p["ImageSize"] = str(len(data))

                else:
                    if "ImageSize" not in p:
                        data = self.get_page(idx)
                        p["ImageSize"] = str(len(data))

    def metadata_from_filename(
        self,
        complicated_parser: bool = False,
        remove_c2c: bool = False,
        remove_fcbd: bool = False,
        remove_publisher: bool = False,
        split_words: bool = False,
    ) -> GenericMetadata:

        metadata = GenericMetadata()

        filename = self.path.name
        if split_words:
            filename = " ".join(wordninja.split(self.path.stem)) + self.path.suffix

        if complicated_parser:
            lex = filenamelexer.Lex(filename)
            p = filenameparser.Parse(
                lex.items, remove_c2c=remove_c2c, remove_fcbd=remove_fcbd, remove_publisher=remove_publisher
            )
            metadata.alternate_number = utils.xlate(p.filename_info["alternate"])
            metadata.issue = utils.xlate(p.filename_info["issue"])
            metadata.issue_count = utils.xlate(p.filename_info["issue_count"])
            metadata.publisher = utils.xlate(p.filename_info["publisher"])
            metadata.series = utils.xlate(p.filename_info["series"])
            metadata.title = utils.xlate(p.filename_info["title"])
            metadata.volume = utils.xlate(p.filename_info["volume"])
            metadata.volume_count = utils.xlate(p.filename_info["volume_count"])
            metadata.year = utils.xlate(p.filename_info["year"])

            metadata.scan_info = utils.xlate(p.filename_info["remainder"])
            metadata.format = "FCBD" if p.filename_info["fcbd"] else None
            if p.filename_info["annual"]:
                metadata.format = "Annual"
        else:
            fnp = filenameparser.FileNameParser()
            fnp.parse_filename(filename)

            if fnp.issue:
                metadata.issue = fnp.issue
            if fnp.series:
                metadata.series = fnp.series
            if fnp.volume:
                metadata.volume = utils.xlate(fnp.volume, True)
            if fnp.year:
                metadata.year = utils.xlate(fnp.year, True)
            if fnp.issue_count:
                metadata.issue_count = utils.xlate(fnp.issue_count, True)
            if fnp.remainder:
                metadata.scan_info = fnp.remainder

        metadata.is_empty = False

        return metadata

    def export_as_zip(self, zip_filename: pathlib.Path | str) -> bool:
        if self.archive_type == self.ArchiveType.Zip:
            # nothing to do, we're already a zip
            return True

        zip_archiver = ZipArchiver(zip_filename)
        return zip_archiver.copy_from_archive(self.archiver)
