"""A class to represent a single comic, be it file or folder of images"""
# Copyright 2012-2014 ComicTagger Authors
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
import shutil
import sys
import traceback
from typing import cast

from comicapi import filenamelexer, filenameparser, utils
from comicapi.archivers import Archiver, UnknownArchiver, ZipArchiver
from comicapi.comet import CoMet
from comicapi.comicbookinfo import ComicBookInfo
from comicapi.comicinfoxml import ComicInfoXml
from comicapi.genericmetadata import GenericMetadata, PageType

logger = logging.getLogger(__name__)

archivers: list[type[Archiver]] = []


def load_archive_plugins() -> None:
    if not archivers:
        if sys.version_info < (3, 10):
            from importlib_metadata import entry_points
        else:
            from importlib.metadata import entry_points
        builtin: list[type[Archiver]] = []
        for arch in entry_points(group="comicapi.archiver"):
            try:
                archiver: type[Archiver] = arch.load()
                if archiver.enabled:
                    if arch.module.startswith("comicapi"):
                        builtin.append(archiver)
                    else:
                        archivers.append(archiver)
            except Exception:
                logger.warning("Failed to load talker: %s", arch.name)
        archivers.extend(builtin)


class MetaDataStyle:
    CBI = 0
    CIX = 1
    COMET = 2
    name = ["ComicBookLover", "ComicRack", "CoMet"]
    short_name = ["cbl", "cr", "comet"]


class ComicArchive:
    logo_data = b""
    pil_available = True

    def __init__(self, path: pathlib.Path | str, default_image_path: pathlib.Path | str | None = None) -> None:
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

        self.ci_xml_filename = "ComicInfo.xml"
        self.comet_default_filename = "CoMet.xml"
        self.reset_cache()
        self.default_image_path = default_image_path

        self.archiver: Archiver = UnknownArchiver.open(self.path)

        load_archive_plugins()
        for archiver in archivers:
            if archiver.is_valid(self.path):
                self.archiver = archiver.open(self.path)
                break

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

    def is_writable(self, check_archive_status: bool = True) -> bool:
        if isinstance(self.archiver, UnknownArchiver):
            return False

        if check_archive_status and not self.archiver.is_writable():
            return False

        if not (os.access(self.path, os.W_OK) or os.access(self.path.parent, os.W_OK)):
            return False

        return True

    def is_writable_for_style(self, data_style: int) -> bool:
        return not (data_style == MetaDataStyle.CBI and not self.archiver.supports_comment())

    def is_zip(self) -> bool:
        return self.archiver.name() == "ZIP"

    def seems_to_be_a_comic_archive(self) -> bool:
        if not (isinstance(self.archiver, UnknownArchiver)) and self.get_number_of_pages() > 0:
            return True

        return False

    def extension(self) -> str:
        return self.archiver.extension()

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
            except Exception as e:
                tb = traceback.extract_tb(e.__traceback__)
                logger.error(
                    "%s:%s: Error reading in page %d. Substituting logo page.", tb[1].filename, tb[1].lineno, index
                )
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
                files = cast(list[str], utils.os_sorted(files))

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
                tb = traceback.extract_tb(e.__traceback__)
                logger.error("%s:%s: Error saving CBI! for %s: %s", tb[1].filename, tb[1].lineno, self.path, e)

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
            tb = traceback.extract_tb(e.__traceback__)
            logger.error("%s:%s: Error reading in raw CIX! for %s: %s", tb[1].filename, tb[1].lineno, self.path, e)
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
                tb = traceback.extract_tb(e.__traceback__)
                logger.error("%s:%s: Error saving CIX! for %s: %s", tb[1].filename, tb[1].lineno, self.path, e)

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
                tb = traceback.extract_tb(e.__traceback__)
                logger.error(
                    "%s:%s: Error reading in raw CoMet! for %s: %s", tb[1].filename, tb[1].lineno, self.path, e
                )
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
                        tb = traceback.extract_tb(e.__traceback__)
                        logger.warning(
                            "%s:%s: Error reading in Comet XML for validation! from %s: %s",
                            tb[1].filename,
                            tb[1].lineno,
                            self.path,
                            e,
                        )
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
                if self.pil_available:
                    try:
                        from PIL import Image

                        self.pil_available = True
                    except ImportError:
                        self.pil_available = False
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
            import wordninja

            filename = " ".join(wordninja.split(self.path.stem)) + self.path.suffix

        if complicated_parser:
            lex = filenamelexer.Lex(filename)
            p = filenameparser.Parse(
                lex.items, remove_c2c=remove_c2c, remove_fcbd=remove_fcbd, remove_publisher=remove_publisher
            )
            metadata.alternate_number = utils.xlate(p.filename_info["alternate"])
            metadata.issue = utils.xlate(p.filename_info["issue"])
            metadata.issue_count = utils.xlate_int(p.filename_info["issue_count"])
            metadata.publisher = utils.xlate(p.filename_info["publisher"])
            metadata.series = utils.xlate(p.filename_info["series"])
            metadata.title = utils.xlate(p.filename_info["title"])
            metadata.volume = utils.xlate_int(p.filename_info["volume"])
            metadata.volume_count = utils.xlate_int(p.filename_info["volume_count"])
            metadata.year = utils.xlate_int(p.filename_info["year"])

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
                metadata.volume = utils.xlate_int(fnp.volume)
            if fnp.year:
                metadata.year = utils.xlate_int(fnp.year)
            if fnp.issue_count:
                metadata.issue_count = utils.xlate_int(fnp.issue_count)
            if fnp.remainder:
                metadata.scan_info = fnp.remainder

        metadata.is_empty = False

        return metadata

    def export_as_zip(self, zip_filename: pathlib.Path) -> bool:
        if self.archiver.name() == "ZIP":
            # nothing to do, we're already a zip
            return True

        zip_archiver = ZipArchiver.open(zip_filename)
        return zip_archiver.copy_from_archive(self.archiver)
