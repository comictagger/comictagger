"""A class to represent a single comic, be it file or folder of images"""

# Copyright 2012-2014 Anthony Beville

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at

#     http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import io
import logging
import os
import pathlib
import platform
import struct
import subprocess
import sys
import tempfile
import time
import zipfile

import natsort
import py7zr
import wordninja

try:
    from unrar.cffi import rarfile

    rar_support = True
except:
    rar_support = False

try:
    from PIL import Image

    pil_available = True
except ImportError:
    pil_available = False

from typing import List, Optional, Union, cast

from comicapi import filenamelexer, filenameparser, utils
from comicapi.comet import CoMet
from comicapi.comicbookinfo import ComicBookInfo
from comicapi.comicinfoxml import ComicInfoXml
from comicapi.genericmetadata import GenericMetadata, PageType

logger = logging.getLogger(__name__)
if not pil_available:
    logger.exception("PIL unavalable")

sys.path.insert(0, os.path.abspath("."))


class MetaDataStyle:
    CBI = 0
    CIX = 1
    COMET = 2
    name = ["ComicBookLover", "ComicRack", "CoMet"]


class UnknownArchiver:

    """Unknown implementation"""

    def __init__(self, path: Union[pathlib.Path, str]) -> None:
        self.path = path

    def get_comment(self) -> str:
        return ""

    def set_comment(self, comment: str) -> bool:
        return False

    def read_file(self, archive_file: str) -> Optional[bytes]:
        return None

    def write_file(self, archive_file: str, data: bytes) -> bool:
        return False

    def remove_file(self, archive_file: str) -> bool:
        return False

    def get_filename_list(self) -> list[str]:
        return []


class SevenZipArchiver(UnknownArchiver):

    """7Z implementation"""

    def __init__(self, path: Union[pathlib.Path, str]) -> None:
        self.path = pathlib.Path(path)

    # @todo: Implement Comment?
    def get_comment(self) -> str:
        return ""

    def set_comment(self, comment: str) -> bool:
        return False

    def read_file(self, archive_file: str) -> bytes:
        data = bytes()
        try:
            with py7zr.SevenZipFile(self.path, "r") as zf:
                data = zf.read(archive_file)[archive_file].read()
        except py7zr.Bad7zFile as e:
            logger.error("bad 7zip file [%s]: %s :: %s", e, self.path, archive_file)
            raise IOError from e
        except Exception as e:
            logger.error("bad 7zip file [%s]: %s :: %s", e, self.path, archive_file)
            raise IOError from e

        return data

    def remove_file(self, archive_file: str) -> bool:
        try:
            self.rebuild_zip_file([archive_file])
        except:
            logger.exception("Failed to remove %s from 7zip archive", archive_file)
            return False
        else:
            return True

    def write_file(self, archive_file: str, data: bytes) -> bool:
        #  At the moment, no other option but to rebuild the whole
        #  zip archive w/o the indicated file. Very sucky, but maybe
        # another solution can be found
        try:
            files = self.get_filename_list()
            if archive_file in files:
                self.rebuild_zip_file([archive_file])

            # now just add the archive file as a new one
            with py7zr.SevenZipFile(self.path, "a") as zf:
                zf.writestr(data, archive_file)
            return True
        except:
            logger.exception("Writing zip file failed")
            return False

    def get_filename_list(self) -> list[str]:
        try:
            with py7zr.SevenZipFile(self.path, "r") as zf:
                namelist: list[str] = zf.getnames()

            return namelist
        except Exception as e:
            logger.error("Unable to get 7zip file list [%s]: %s", e, self.path)
            return []

    def rebuild_zip_file(self, exclude_list: list[str]) -> None:
        """Zip helper func

        This recompresses the zip archive, without the files in the exclude_list
        """
        tmp_fd, tmp_name = tempfile.mkstemp(dir=os.path.dirname(self.path))
        os.close(tmp_fd)

        try:
            with py7zr.SevenZipFile(self.path, "r") as zin:
                targets = [f for f in zin.getnames() if f not in exclude_list]
            with py7zr.SevenZipFile(self.path, "r") as zin:
                with py7zr.SevenZipFile(tmp_name, "w") as zout:
                    for fname, bio in zin.read(targets).items():
                        zout.writef(bio, fname)
        except Exception:
            logger.exception("Error rebuilding 7zip file: %s", self.path)

        # replace with the new file
        os.remove(self.path)
        os.rename(tmp_name, self.path)

    def copy_from_archive(self, otherArchive: UnknownArchiver) -> bool:
        """Replace the current zip with one copied from another archive"""
        try:
            with py7zr.SevenZipFile(self.path, "w") as zout:
                for fname in otherArchive.get_filename_list():
                    data = otherArchive.read_file(fname)
                    if data is not None:
                        zout.writestr(data, fname)
        except Exception as e:
            logger.exception("Error while copying to %s: %s", self.path, e)
            return False
        else:
            return True


class ZipArchiver(UnknownArchiver):

    """ZIP implementation"""

    def __init__(self, path: Union[pathlib.Path, str]) -> None:
        self.path = pathlib.Path(path)

    def get_comment(self) -> str:
        with zipfile.ZipFile(self.path, "r") as zf:
            comment = zf.comment.decode("utf-8")
        return comment

    def set_comment(self, comment: str) -> bool:
        with zipfile.ZipFile(self.path, "a") as zf:
            zf.comment = bytes(comment, "utf-8")
        return True

    def read_file(self, archive_file: str) -> bytes:
        with zipfile.ZipFile(self.path, "r") as zf:
            try:
                data = zf.read(archive_file)
            except zipfile.BadZipfile as e:
                logger.error("bad zipfile [%s]: %s :: %s", e, self.path, archive_file)
                raise IOError from e
            except Exception as e:
                logger.error("bad zipfile [%s]: %s :: %s", e, self.path, archive_file)
                raise IOError from e
        return data

    def remove_file(self, archive_file: str) -> bool:
        try:
            self.rebuild_zip_file([archive_file])
        except:
            logger.exception("Failed to remove %s from zip archive", archive_file)
            return False
        else:
            return True

    def write_file(self, archive_file: str, data: bytes) -> bool:
        #  At the moment, no other option but to rebuild the whole
        #  zip archive w/o the indicated file. Very sucky, but maybe
        # another solution can be found
        try:
            files = self.get_filename_list()
            if archive_file in files:
                self.rebuild_zip_file([archive_file])

            # now just add the archive file as a new one
            with zipfile.ZipFile(self.path, mode="a", allowZip64=True, compression=zipfile.ZIP_DEFLATED) as zf:
                zf.writestr(archive_file, data)
            return True
        except Exception as e:
            logger.error("writing zip file failed [%s]: %s", e, self.path)
            return False

    def get_filename_list(self) -> List[str]:
        try:
            with zipfile.ZipFile(self.path, "r") as zf:
                namelist = zf.namelist()
            return namelist
        except Exception as e:
            logger.error("Unable to get zipfile list [%s]: %s", e, self.path)
            return []

    def rebuild_zip_file(self, exclude_list: List[str]) -> None:
        """Zip helper func

        This recompresses the zip archive, without the files in the exclude_list
        """
        tmp_fd, tmp_name = tempfile.mkstemp(dir=os.path.dirname(self.path))
        os.close(tmp_fd)

        try:
            with zipfile.ZipFile(self.path, "r") as zin:
                with zipfile.ZipFile(tmp_name, "w", allowZip64=True) as zout:
                    for item in zin.infolist():
                        buffer = zin.read(item.filename)
                        if item.filename not in exclude_list:
                            zout.writestr(item, buffer)

                    # preserve the old comment
                    zout.comment = zin.comment
        except Exception:
            logger.exception("Error rebuilding zip file: %s", self.path)

        # replace with the new file
        os.remove(self.path)
        os.rename(tmp_name, self.path)

    def write_zip_comment(self, filename: Union[pathlib.Path, str], comment: str) -> bool:
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
            with open(filename, "r+b") as fo:

                # the starting position, relative to EOF
                pos = -4

                found = False

                # walk backwards to find the "End of Central Directory" record
                while (not found) and (-pos != file_length):
                    # seek, relative to EOF
                    fo.seek(pos, 2)

                    value = fo.read(4)

                    # look for the end of central directory signature
                    if bytearray(value) == bytearray([0x50, 0x4B, 0x05, 0x06]):
                        found = True
                    else:
                        # not found, step back another byte
                        pos = pos - 1

                if found:

                    # now skip forward 20 bytes to the comment length word
                    pos += 20
                    fo.seek(pos, 2)

                    # Pack the length of the comment string
                    fmt = "H"  # one 2-byte integer
                    comment_length = struct.pack(fmt, len(comment))  # pack integer in a binary string

                    # write out the length
                    fo.write(comment_length)
                    fo.seek(pos + 2, 2)

                    # write out the comment itself
                    fo.write(comment.encode("utf-8"))
                    fo.truncate()
                else:
                    raise Exception("Failed to write comment to zip file!")
        except Exception:
            logger.exception("Writing comment to %s failed", filename)
            return False
        else:
            return True

    def copy_from_archive(self, other_archive: UnknownArchiver) -> bool:
        """Replace the current zip with one copied from another archive"""
        try:
            with zipfile.ZipFile(self.path, "w", allowZip64=True) as zout:
                for fname in other_archive.get_filename_list():
                    data = other_archive.read_file(fname)
                    if data is not None:
                        zout.writestr(fname, data)

            # preserve the old comment
            comment = other_archive.get_comment()
            if comment is not None:
                if not self.write_zip_comment(self.path, comment):
                    return False
        except Exception:
            logger.exception("Error while copying to %s", self.path)
            return False
        else:
            return True


class RarArchiver(UnknownArchiver):
    """RAR implementation"""

    devnull = None

    def __init__(self, path: Union[pathlib.Path, str], rar_exe_path: str) -> None:
        self.path = pathlib.Path(path)
        self.rar_exe_path = rar_exe_path

        if RarArchiver.devnull is None:
            RarArchiver.devnull = open(os.devnull, "bw")

        # windows only, keeps the cmd.exe from popping up
        if platform.system() == "Windows":
            self.startupinfo = subprocess.STARTUPINFO()  # type: ignore
            self.startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW  # type: ignore
        else:
            self.startupinfo = None

    def get_comment(self) -> str:
        rarc = self.get_rar_obj()
        return str(rarc.comment) if rarc else ""

    def set_comment(self, comment: str) -> bool:
        if self.rar_exe_path:
            try:
                # write comment to temp file
                tmp_fd, tmp_name = tempfile.mkstemp()
                with os.fdopen(tmp_fd, "wb") as f:
                    f.write(comment.encode("utf-8"))

                working_dir = os.path.dirname(os.path.abspath(self.path))

                # use external program to write comment to Rar archive
                proc_args = [self.rar_exe_path, "c", "-w" + working_dir, "-c-", "-z" + tmp_name, str(self.path)]
                subprocess.call(
                    proc_args,
                    startupinfo=self.startupinfo,
                    stdout=RarArchiver.devnull,
                    stdin=RarArchiver.devnull,
                    stderr=RarArchiver.devnull,
                )

                if platform.system() == "Darwin":
                    time.sleep(1)
                os.remove(tmp_name)
            except Exception:
                logger.exception("Failed to set a comment")
                return False
            else:
                return True
        else:
            return False

    def read_file(self, archive_file: str) -> bytes:

        rarc = self.get_rar_obj()
        if rarc is None:
            return bytes()

        tries = 0
        while tries < 7:
            try:
                tries = tries + 1
                data: bytes = rarc.open(archive_file).read()
                entries = [(rarc.getinfo(archive_file), data)]

                if entries[0][0].file_size != len(entries[0][1]):
                    logger.info(
                        "read_file(): [file is not expected size: %d vs %d]  %s:%s [attempt # %d]",
                        entries[0][0].file_size,
                        len(entries[0][1]),
                        self.path,
                        archive_file,
                        tries,
                    )
                    continue
            except (OSError, IOError) as e:
                logger.error("read_file(): [%s]  %s:%s attempt #%d", e, self.path, archive_file, tries)
                time.sleep(1)
            except Exception as e:
                logger.error(
                    "Unexpected exception in read_file(): [%s] for %s:%s attempt #%d", e, self.path, archive_file, tries
                )
                break

            else:
                # Success. Entries is a list of of tuples:  ( rarinfo, filedata)
                if tries > 1:
                    logger.info("Attempted read_files() {%d} times", tries)
                if len(entries) == 1:
                    return entries[0][1]

                raise IOError

        raise IOError

    def write_file(self, archive_file: str, data: bytes) -> bool:

        if self.rar_exe_path:
            try:
                tmp_folder = tempfile.mkdtemp()

                tmp_file = os.path.join(tmp_folder, archive_file)

                working_dir = os.path.dirname(os.path.abspath(self.path))

                # TODO: will this break if 'archive_file' is in a subfolder. i.e. "foo/bar.txt"
                # will need to create the subfolder above, I guess...
                with open(tmp_file, "wb") as f:
                    f.write(data)

                # use external program to write file to Rar archive
                subprocess.call(
                    [self.rar_exe_path, "a", "-w" + working_dir, "-c-", "-ep", self.path, tmp_file],
                    startupinfo=self.startupinfo,
                    stdout=RarArchiver.devnull,
                    stdin=RarArchiver.devnull,
                    stderr=RarArchiver.devnull,
                )

                if platform.system() == "Darwin":
                    time.sleep(1)
                os.remove(tmp_file)
                os.rmdir(tmp_folder)
            except Exception as e:
                logger.info(str(e))
                logger.exception("Failed write %s to rar archive", archive_file)
                return False
            else:
                return True
        else:
            return False

    def remove_file(self, archive_file: str) -> bool:
        if self.rar_exe_path:
            try:
                # use external program to remove file from Rar archive
                subprocess.call(
                    [self.rar_exe_path, "d", "-c-", self.path, archive_file],
                    startupinfo=self.startupinfo,
                    stdout=RarArchiver.devnull,
                    stdin=RarArchiver.devnull,
                    stderr=RarArchiver.devnull,
                )

                if platform.system() == "Darwin":
                    time.sleep(1)
            except:
                logger.exception("Failed to remove %s from rar archive", archive_file)
                return False
            else:
                return True
        else:
            return False

    def get_filename_list(self) -> list[str]:
        rarc = self.get_rar_obj()
        tries = 0
        # while tries < 7:
        namelist = []
        try:
            tries = tries + 1
            for item in rarc.infolist() if rarc else None:
                if item.file_size != 0:
                    namelist.append(item.filename)

        except (OSError, IOError) as e:
            logger.error(f"get_filename_list(): [{e}] {self.path} attempt #{tries}".format(str(e), self.path, tries))
            time.sleep(1)

        return namelist

    def get_rar_obj(self) -> "Optional[rarfile.RarFile]":
        try:
            rarc = rarfile.RarFile(str(self.path))
        except (OSError, IOError) as e:
            logger.error("getRARObj(): [%s] %s", e, self.path)
        else:
            return rarc

        return None


class FolderArchiver(UnknownArchiver):

    """Folder implementation"""

    def __init__(self, path: Union[pathlib.Path, str]) -> None:
        self.path = pathlib.Path(path)
        self.comment_file_name = "ComicTaggerFolderComment.txt"

    def get_comment(self) -> str:
        return self.read_file(self.comment_file_name).decode("utf-8")

    def set_comment(self, comment: str) -> bool:
        return self.write_file(self.comment_file_name, comment.encode("utf-8"))

    def read_file(self, archive_file: str) -> bytes:

        data = bytes()
        fname = os.path.join(self.path, archive_file)
        try:
            with open(fname, "rb") as f:
                data = f.read()
        except IOError:
            logger.exception("Failed to read: %s", fname)

        return data

    def write_file(self, archive_file: str, data: bytes) -> bool:

        fname = os.path.join(self.path, archive_file)
        try:
            with open(fname, "wb") as f:
                f.write(data)
        except:
            logger.exception("Failed to write: %s", fname)
            return False
        else:
            return True

    def remove_file(self, archive_file: str) -> bool:

        fname = os.path.join(self.path, archive_file)
        try:
            os.remove(fname)
        except:
            logger.exception("Failed to remove: %s", fname)
            return False
        else:
            return True

    def get_filename_list(self) -> list[str]:
        return self.list_files(self.path)

    def list_files(self, folder: Union[pathlib.Path, str]) -> list[str]:

        itemlist = []

        for item in os.listdir(folder):
            itemlist.append(item)
            if os.path.isdir(item):
                itemlist.extend(self.list_files(os.path.join(folder, item)))

        return itemlist


class ComicArchive:
    logo_data = bytes()

    class ArchiveType:
        SevenZip, Zip, Rar, Folder, Pdf, Unknown = list(range(6))

    def __init__(
        self,
        path: Union[pathlib.Path, str],
        rar_exe_path: str = "",
        default_image_path: Union[pathlib.Path, str, None] = None,
    ) -> None:
        self.cbi_md: Optional[GenericMetadata] = None
        self.cix_md: Optional[GenericMetadata] = None
        self.comet_filename: Optional[str] = None
        self.comet_md: Optional[GenericMetadata] = None
        self.has__cbi: Optional[bool] = None
        self.has__cix: Optional[bool] = None
        self.has__comet: Optional[bool] = None
        self.path = pathlib.Path(path)
        self.page_count: Optional[int] = None
        self.page_list: list[str] = []

        self.rar_exe_path = rar_exe_path
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

        if not ComicArchive.logo_data:
            fname = self.default_image_path
            if fname:
                with open(fname, "rb") as fd:
                    ComicArchive.logo_data = fd.read()

    def reset_cache(self) -> None:
        """Clears the cached data"""

        self.has__cix = None
        self.has__cbi = None
        self.has__comet = None
        self.comet_filename = None
        self.page_count = None
        self.page_list = []
        self.cix_md = None
        self.cbi_md = None
        self.comet_md = None

    def load_cache(self, style_list: List[int]) -> None:
        for style in style_list:
            self.read_metadata(style)

    def rename(self, path: Union[pathlib.Path, str]) -> None:
        self.path = pathlib.Path(path)
        self.archiver.path = pathlib.Path(path)

    def sevenzip_test(self) -> bool:
        return py7zr.is_7zfile(self.path)

    def zip_test(self) -> bool:
        return zipfile.is_zipfile(self.path)

    def rar_test(self) -> bool:
        try:
            return bool(rarfile.is_rarfile(str(self.path)))
        except:
            return False

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
        if (self.is_zip() or self.is_rar() or self.is_sevenzip()) and (self.get_number_of_pages() > 0):
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
        image_data = bytes()

        filename = self.get_page_name(index)

        if filename:
            try:
                image_data = self.archiver.read_file(filename) or bytes()
            except IOError:
                logger.exception("Error reading in page. Substituting logo page.")
                image_data = ComicArchive.logo_data

        return image_data

    def get_page_name(self, index: int) -> str:
        if index is None:
            return None

        page_list = self.get_page_name_list()

        num_pages = len(page_list)
        if num_pages == 0 or index >= num_pages:
            return ""

        return page_list[index]

    def get_scanner_page_index(self) -> Optional[int]:
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
        sorted_buckets = sorted(iter(length_buckets.items()), key=lambda k_v: (k_v[1], k_v[0]), reverse=True)

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

    def get_page_name_list(self, sort_list: bool = True) -> List[str]:
        if not self.page_list:
            # get the list file names in the archive, and sort
            files: list[str] = self.archiver.get_filename_list()

            # seems like some archive creators are on Windows, and don't know about case-sensitivity!
            if sort_list:

                files = cast(list[str], natsort.natsorted(files, alg=natsort.ns.IC | natsort.ns.I | natsort.ns.U))

            # make a sub-list of image files
            self.page_list = []
            for name in files:
                if (
                    os.path.splitext(name)[1].lower() in [".jpg", ".jpeg", ".png", ".gif", ".webp"]
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
        if self.has__cbi is None:
            if not self.seems_to_be_a_comic_archive():
                self.has__cbi = False
            else:
                comment = self.archiver.get_comment()
                self.has__cbi = ComicBookInfo().validate_string(comment)

        return self.has__cbi

    def write_cbi(self, metadata: GenericMetadata) -> bool:
        if metadata is not None:
            self.apply_archive_info_to_metadata(metadata)
            cbi_string = ComicBookInfo().string_from_metadata(metadata)
            write_success = self.archiver.set_comment(cbi_string)
            if write_success:
                self.has__cbi = True
                self.cbi_md = metadata
            self.reset_cache()
            return write_success

        return False

    def remove_cbi(self) -> bool:
        if self.has_cbi():
            write_success = self.archiver.set_comment("")
            if write_success:
                self.has__cbi = False
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
        except IOError as e:
            logger.error("Error reading in raw CIX!: %s", e)
            raw_cix = bytes()
        return raw_cix

    def write_cix(self, metadata: GenericMetadata) -> bool:
        if metadata is not None:
            self.apply_archive_info_to_metadata(metadata, calc_page_sizes=True)
            raw_cix = self.read_raw_cix()
            cix_string = ComicInfoXml().string_from_metadata(metadata, xml=raw_cix)
            write_success = self.archiver.write_file(self.ci_xml_filename, cix_string.encode("utf-8"))
            if write_success:
                self.has__cix = True
                self.cix_md = metadata
            self.reset_cache()
            return write_success

        return False

    def remove_cix(self) -> bool:
        if self.has_cix():
            write_success = self.archiver.remove_file(self.ci_xml_filename)
            if write_success:
                self.has__cix = False
                self.cix_md = None
            self.reset_cache()
            return write_success
        return True

    def has_cix(self) -> bool:
        if self.has__cix is None:

            if not self.seems_to_be_a_comic_archive():
                self.has__cix = False
            elif self.ci_xml_filename in self.archiver.get_filename_list():
                self.has__cix = True
            else:
                self.has__cix = False
        return self.has__cix

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
            logger.info("%s doesn't have CoMet data!", self.path)
            raw_comet = ""

        try:
            raw_bytes = self.archiver.read_file(cast(str, self.comet_filename))
            if raw_bytes:
                raw_comet = raw_bytes.decode("utf-8")
        except:
            logger.exception("Error reading in raw CoMet!")
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
                self.has__comet = True
                self.comet_md = metadata
            self.reset_cache()
            return write_success

        return False

    def remove_co_met(self) -> bool:
        if self.has_comet():
            write_success = self.archiver.remove_file(cast(str, self.comet_filename))
            if write_success:
                self.has__comet = False
                self.comet_md = None
            self.reset_cache()
            return write_success
        return True

    def has_comet(self) -> bool:
        if self.has__comet is None:
            self.has__comet = False
            if not self.seems_to_be_a_comic_archive():
                return self.has__comet

            # look at all xml files in root, and search for CoMet data, get first
            for n in self.archiver.get_filename_list():
                if os.path.dirname(n) == "" and os.path.splitext(n)[1].lower() == ".xml":
                    # read in XML file, and validate it
                    try:
                        data = ""
                        d = self.archiver.read_file(n)
                        if d:
                            data = d.decode("utf-8")
                    except Exception as e:
                        logger.warning("Error reading in Comet XML for validation!: %s", e)
                    if CoMet().validate_string(data):
                        # since we found it, save it!
                        self.comet_filename = n
                        self.has__comet = True
                        break

        return self.has__comet

    def apply_archive_info_to_metadata(self, md: GenericMetadata, calc_page_sizes: bool = False) -> None:
        md.page_count = self.get_number_of_pages()

        if calc_page_sizes:
            for p in md.pages:
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
                                logger.warning("decoding image failed: %s", e)
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

    def export_as_zip(self, zipfilename: str) -> bool:
        if self.archive_type == self.ArchiveType.Zip:
            # nothing to do, we're already a zip
            return True

        zip_archiver = ZipArchiver(zipfilename)
        return zip_archiver.copy_from_archive(self.archiver)
