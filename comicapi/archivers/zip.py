from __future__ import annotations

import logging
import os
import pathlib
import shutil
import struct
import tempfile
import zipfile
from typing import cast

from comicapi.archivers import UnknownArchiver

logger = logging.getLogger(__name__)


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
