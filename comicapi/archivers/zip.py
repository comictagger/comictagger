from __future__ import annotations

import logging
import os
import pathlib
import shutil
import tempfile
import zipfile
from typing import cast

import chardet

from comicapi.archivers import Archiver

logger = logging.getLogger(__name__)


class ZipArchiver(Archiver):
    """ZIP implementation"""

    def __init__(self) -> None:
        super().__init__()

    def supports_comment(self) -> bool:
        return True

    def get_comment(self) -> str:
        with zipfile.ZipFile(self.path, "r") as zf:
            encoding = chardet.detect(zf.comment, True)
            if encoding["confidence"] > 60:
                try:
                    comment = zf.comment.decode(encoding["encoding"])
                except UnicodeDecodeError:
                    comment = zf.comment.decode("utf-8", errors="replace")
            else:
                comment = zf.comment.decode("utf-8", errors="replace")
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
                logger.exception("Error reading zip archive [%s]: %s :: %s", e, self.path, archive_file)
                raise
        return data

    def remove_file(self, archive_file: str) -> bool:
        return self.rebuild([archive_file])

    def write_file(self, archive_file: str, data: bytes) -> bool:
        # At the moment, no other option but to rebuild the whole
        # zip archive w/o the indicated file. Very sucky, but maybe
        # another solution can be found
        files = self.get_filename_list()

        try:
            # now just add the archive file as a new one
            with zipfile.ZipFile(self.path, mode="a", allowZip64=True, compression=zipfile.ZIP_DEFLATED) as zf:
                _patch_zipfile(zf)
                if archive_file in files:
                    zf.remove(archive_file)  # type: ignore
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

    def supports_files(self) -> bool:
        return True

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

    def copy_from_archive(self, other_archive: Archiver) -> bool:
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
                if not self.set_comment(comment):
                    return False
        except Exception as e:
            logger.error("Error while copying to zip archive [%s]: from %s to %s", e, other_archive.path, self.path)
            return False
        else:
            return True

    def is_writable(self) -> bool:
        return True

    def extension(self) -> str:
        return ".cbz"

    def name(self) -> str:
        return "ZIP"

    @classmethod
    def is_valid(cls, path: pathlib.Path) -> bool:
        if not zipfile.is_zipfile(path):  # only checks central directory ot the end of the archive
            return False
        try:
            # test all the files in the zip. adds about 0.1 to execution time per zip
            with zipfile.ZipFile(path) as zf:
                for zipinfo in zf.filelist:
                    zf.open(zipinfo).close()
            return True
        except Exception:
            return False


def _patch_zipfile(zf):  # type: ignore
    zf.remove = _zip_remove.__get__(zf, zipfile.ZipFile)
    zf._remove_members = _zip_remove_members.__get__(zf, zipfile.ZipFile)


def _zip_remove(self, zinfo_or_arcname):  # type: ignore
    """Remove a member from the archive."""

    if self.mode not in ("w", "x", "a"):
        raise ValueError("remove() requires mode 'w', 'x', or 'a'")
    if not self.fp:
        raise ValueError("Attempt to write to ZIP archive that was already closed")
    if self._writing:
        raise ValueError("Can't write to ZIP archive while an open writing handle exists")

    # Make sure we have an existing info object
    if isinstance(zinfo_or_arcname, zipfile.ZipInfo):
        zinfo = zinfo_or_arcname
        # make sure zinfo exists
        if zinfo not in self.filelist:
            raise KeyError("There is no item %r in the archive" % zinfo_or_arcname)
    else:
        # get the info object
        zinfo = self.getinfo(zinfo_or_arcname)

    return self._remove_members({zinfo})


def _zip_remove_members(self, members, *, remove_physical=True, chunk_size=2**20):  # type: ignore
    """Remove members in a zip file.
    All members (as zinfo) should exist in the zip; otherwise the zip file
    will erroneously end in an inconsistent state.
    """
    fp = self.fp
    entry_offset = 0
    member_seen = False

    # get a sorted filelist by header offset, in case the dir order
    # doesn't match the actual entry order
    filelist = sorted(self.filelist, key=lambda x: x.header_offset)
    for i in range(len(filelist)):
        info = filelist[i]
        is_member = info in members

        if not (member_seen or is_member):
            continue

        # get the total size of the entry
        try:
            offset = filelist[i + 1].header_offset
        except IndexError:
            offset = self.start_dir
        entry_size = offset - info.header_offset

        if is_member:
            member_seen = True
            entry_offset += entry_size

            # update caches
            self.filelist.remove(info)
            try:
                del self.NameToInfo[info.filename]
            except KeyError:
                pass
            continue

        # update the header and move entry data to the new position
        if remove_physical:
            old_header_offset = info.header_offset
            info.header_offset -= entry_offset
            read_size = 0
            while read_size < entry_size:
                fp.seek(old_header_offset + read_size)
                data = fp.read(min(entry_size - read_size, chunk_size))
                fp.seek(info.header_offset + read_size)
                fp.write(data)
                fp.flush()
                read_size += len(data)

    # Avoid missing entry if entries have a duplicated name.
    # Reverse the order as NameToInfo normally stores the last added one.
    for info in reversed(self.filelist):
        self.NameToInfo.setdefault(info.filename, info)

    # update state
    if remove_physical:
        self.start_dir -= entry_offset
    self._didModify = True

    # seek to the start of the central dir
    fp.seek(self.start_dir)
