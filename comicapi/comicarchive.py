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

import hashlib
import importlib.util
import inspect
import io
import itertools
import logging
import os
import pathlib
import shutil
from collections.abc import Iterable

from comicapi import utils
from comicapi.archivers import Archiver, UnknownArchiver, ZipArchiver
from comicapi.genericmetadata import FileHash, GenericMetadata
from comicapi.tags import Tag
from comictaggerlib.ctversion import version

logger = logging.getLogger(__name__)

archivers: list[type[Archiver]] = []
tags: dict[str, Tag] = {}


def load_archive_plugins(local_plugins: Iterable[type[Archiver]] = tuple()) -> None:
    if archivers:
        return
    from importlib.metadata import entry_points

    builtin: list[type[Archiver]] = []
    archive_plugins: list[type[Archiver]] = []
    # A list is used first matching plugin wins

    for ep in itertools.chain(entry_points(group="comicapi.archiver")):
        try:
            spec = importlib.util.find_spec(ep.module)
        except ValueError:
            spec = None
        try:
            archiver: type[Archiver] = ep.load()

            if ep.module.startswith("comicapi"):
                builtin.append(archiver)
            else:
                archive_plugins.append(archiver)
        except Exception:
            if spec and spec.has_location:
                logger.exception("Failed to load archive plugin: %s from %s", ep.name, spec.origin)
            else:
                logger.exception("Failed to load archive plugin: %s", ep.name)
    archivers.clear()
    archivers.extend(local_plugins)
    archivers.extend(archive_plugins)
    archivers.extend(builtin)


def load_tag_plugins(version: str = f"ComicAPI/{version}", local_plugins: Iterable[type[Tag]] = tuple()) -> None:
    if tags:
        return
    from importlib.metadata import entry_points

    builtin: dict[str, Tag] = {}
    tag_plugins: dict[str, tuple[Tag, str]] = {}
    # A dict is used, last plugin wins
    for ep in entry_points(group="comicapi.tags"):
        location = "Unknown"
        try:
            _spec = importlib.util.find_spec(ep.module)
            if _spec and _spec.has_location and _spec.origin:
                location = _spec.origin
        except ValueError:
            location = "Unknown"

        try:
            tag: type[Tag] = ep.load()

            if ep.module.startswith("comicapi"):
                builtin[tag.id] = tag(version)
            else:
                if tag.id in tag_plugins:
                    logger.warning(
                        "Plugin %s from %s is overriding the existing plugin for %s tags",
                        ep.module,
                        location,
                        tag.id,
                    )
                tag_plugins[tag.id] = (tag(version), location)
        except Exception:
            logger.exception("Failed to load tag plugin: %s from %s", ep.name, location)
    # A dict is used, last plugin wins
    for tag in local_plugins:
        tag_plugins[tag.id] = (tag(version), "Local")

    for tag_id in set(builtin.keys()).intersection(tag_plugins):
        location = tag_plugins[tag_id][1]
        logger.warning("Builtin plugin for %s tags are being overridden by a plugin from %s", tag_id, location)

    tags.clear()
    tags.update(builtin)
    tags.update({s[0]: s[1][0] for s in tag_plugins.items()})


class ComicArchive:
    """Exceptions from tags/archive should already be logged. Caller must handle display to user and recovery"""

    logo_data = b""
    pil_available: bool | None = None

    def __init__(
        self,
        path: pathlib.Path | str | Archiver,
        default_image_path: pathlib.Path | str | None = None,
        hash_archive: str = "",
    ) -> None:
        self.md: dict[str, GenericMetadata] = {}
        self.page_count: int | None = None
        self.page_list: list[str] = []
        self.hash_archive = hash_archive

        self.reset_cache()
        self.default_image_path = default_image_path

        if isinstance(path, Archiver):
            self.path = path.path
            self.archiver: Archiver = path
        else:
            self.path = pathlib.Path(path).absolute()
            self.archiver = UnknownArchiver.open(self.path)

            load_archive_plugins()
            load_tag_plugins()
            archiver_missing = True
            for archiver in archivers:
                if self.path.suffix in archiver.supported_extensions and archiver.is_valid(self.path):
                    self.archiver = archiver.open(self.path)
                    archiver_missing = False
                    break

            if archiver_missing:
                for archiver in archivers:
                    if archiver.enabled and archiver.is_valid(self.path):
                        self.archiver = archiver.open(self.path)
                        break

        if not ComicArchive.logo_data and self.default_image_path:
            with open(self.default_image_path, mode="rb") as fd:
                ComicArchive.logo_data = fd.read()

    def reset_cache(self) -> None:
        """Clears the cached data"""

        self.page_count = None
        self.page_list.clear()
        self.md.clear()

    def load_cache(self, tag_ids: Iterable[str]) -> None:
        for tag_id in tag_ids:
            if tag_id not in tags:
                continue
            tag = tags[tag_id]
            if not tag.enabled:
                continue
            md = tag.read_tags(self.archiver)
            if not md.is_empty:
                self.md[tag_id] = md

    def get_supported_tags(self) -> list[str]:
        return [tag_id for tag_id, tag in tags.items() if tag.enabled and tag.supports_tags(self.archiver)]

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

        if not (os.access(self.path, os.W_OK) and os.access(self.path.parent, os.W_OK)):
            return False

        return True

    def is_zip(self) -> bool:
        return self.archiver.extension() == ".cbz"

    def seems_to_be_a_comic_archive(self) -> bool:
        try:
            if (
                not (isinstance(self.archiver, UnknownArchiver))
                and self.get_number_of_pages() > 0
                and self.archiver.is_valid(self.path)
            ):
                return True
        except Exception:
            ...

        return False

    def extension(self) -> str:
        return self.archiver.extension()

    def read_tags(self, tag_id: str) -> GenericMetadata:
        if tag_id in self.md:
            return self.md[tag_id]
        md = GenericMetadata()
        tag = tags[tag_id]
        if tag.enabled and tag.has_tags(self.archiver):
            md = tag.read_tags(self.archiver)
            md.apply_default_page_list(self.get_page_name_list())
        return md

    def read_raw_tags(self, tag_id: str) -> str:
        if not tags[tag_id].enabled:
            return ""
        return tags[tag_id].read_raw_tags(self.archiver)

    def write_tags(self, metadata: GenericMetadata, tag_id: str) -> None:
        if tag_id in self.md:
            del self.md[tag_id]
        if not tags[tag_id].enabled:
            logger.warning("%s tags not enabled", tags[tag_id].name())
            return

        self.apply_archive_info_to_metadata(metadata, True, True, hash_archive=self.hash_archive)
        tags[tag_id].write_tags(metadata, self.archiver)

    def has_tags(self, tag_id: str) -> bool:
        if tag_id in self.md:
            return True
        if not tags[tag_id].enabled:
            return False
        return tags[tag_id].has_tags(self.archiver)

    def remove_tags(self, tag_id: str) -> None:
        if tag_id in self.md:
            del self.md[tag_id]
        if not tags[tag_id].enabled:
            return
        tags[tag_id].remove_tags(self.archiver)

    def get_page(self, index: int) -> bytes:
        image_data = b""

        filename = self.get_page_name(index)

        if filename:
            try:
                image_data = self.archiver.read_file(filename) or b""
            except Exception:
                logger.exception("Error reading in page %d. Substituting logo page.", index)
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

    def get_page_name_list(self) -> list[str]:
        if not self.page_list:
            self.__import_pil__()  # Import pillow for list of supported extensions
            self.page_list = utils.get_page_name_list(self.archiver.get_filename_list())

        return self.page_list

    def get_number_of_pages(self) -> int:
        if self.page_count is None:
            self.page_count = len(self.get_page_name_list())
        return self.page_count

    def __import_pil__(self) -> bool:
        if self.pil_available is not None:
            return self.pil_available

        try:
            from PIL import Image

            Image.init()
            utils.KNOWN_IMAGE_EXTENSIONS.update([ext for ext, typ in Image.EXTENSION.items() if typ in Image.OPEN])
            self.pil_available = True
        except Exception:
            self.pil_available = False
            logger.exception("Failed to load Pillow")
            return False
        return True

    def apply_archive_info_to_metadata(
        self,
        md: GenericMetadata,
        calc_page_sizes: bool = False,
        detect_double_page: bool = False,
        *,
        hash_archive: str = "",
    ) -> None:
        hash_archive = hash_archive
        md.page_count = self.get_number_of_pages()
        md.apply_default_page_list(self.get_page_name_list())
        if not self.seems_to_be_a_comic_archive():
            return

        if hash_archive in hashlib.algorithms_available and not md.original_hash:
            hasher = getattr(hashlib, hash_archive, hash_archive)
            try:
                with self.archiver.path.open("b+r") as archive:
                    digest = utils.file_digest(archive, hasher)
                if len(inspect.signature(digest.hexdigest).parameters) > 0:
                    length = digest.name.rpartition("_")[2]
                    if not length.isdigit():
                        length = "128"
                    md.original_hash = FileHash(digest.name, digest.hexdigest(int(length) // 8))  # type: ignore[call-arg]
                else:
                    md.original_hash = FileHash(digest.name, digest.hexdigest())
            except Exception:
                logger.exception("Failed to calculate original hash for '%s'", self.archiver.path)
        if not calc_page_sizes:
            return
        for p in md.pages:
            if p.byte_size is None or p.height is None or p.width is None or p.double_page is None:
                try:
                    data = self.get_page(p.archive_index)
                    p.byte_size = len(data)
                    if not data or not self.__import_pil__():
                        continue

                    from PIL import Image

                    im = Image.open(io.BytesIO(data))
                    w, h = im.size

                    p.height = h
                    p.width = w
                    if detect_double_page:
                        p.double_page = p.is_double_page()
                except Exception as e:
                    logger.exception("Error decoding image [%s] %s :: image %s", e, self.path, p.archive_index)

    def metadata_from_filename(
        self,
        parser: utils.Parser = utils.Parser.ORIGINAL,
        remove_c2c: bool = False,
        remove_fcbd: bool = False,
        remove_publisher: bool = False,
        split_words: bool = False,
        allow_issue_start_with_letter: bool = False,
        protofolius_issue_number_scheme: bool = False,
    ) -> GenericMetadata:
        metadata = GenericMetadata()

        filename_info = utils.parse_filename(
            self.path.name,
            parser=parser,
            remove_c2c=remove_c2c,
            remove_fcbd=remove_fcbd,
            remove_publisher=remove_publisher,
            split_words=split_words,
            allow_issue_start_with_letter=allow_issue_start_with_letter,
            protofolius_issue_number_scheme=protofolius_issue_number_scheme,
        )
        metadata.alternate_number = utils.xlate(filename_info.get("alternate", None))
        metadata.issue = utils.xlate(filename_info.get("issue", None))
        metadata.issue_count = utils.xlate_int(filename_info.get("issue_count", None))
        metadata.publisher = utils.xlate(filename_info.get("publisher", None))
        metadata.series = utils.xlate(filename_info.get("series", None))
        metadata.title = utils.xlate(filename_info.get("title", None))
        metadata.volume = utils.xlate_int(filename_info.get("volume", None))
        metadata.volume_count = utils.xlate_int(filename_info.get("volume_count", None))
        metadata.year = utils.xlate_int(filename_info.get("year", None))

        metadata.scan_info = utils.xlate(filename_info.get("remainder", None))

        if filename_info.get("fcbd", None):
            metadata.format = "FCBD"
            metadata.tags.add("FCBD")

        if filename_info.get("c2c", None):
            metadata.tags.add("c2c")

        if filename_info.get("annual", None):
            metadata.format = "Annual"

        if filename_info.get("format", None):
            metadata.format = filename_info["format"]

        metadata.is_empty = False
        return metadata

    def export_as(self, new_filename: pathlib.Path, extension: str = ".zip") -> None:
        """
        Unconditionally creates a new file. Does not check the current archive.

        If extension cannot be find reverts to .zip
        """
        zip_archiver = UnknownArchiver.open(new_filename)
        for archiver in archivers:
            if extension in archiver.supported_extensions:
                zip_archiver = archiver.open(new_filename)
        if isinstance(zip_archiver, UnknownArchiver):
            zip_archiver = ZipArchiver.open(new_filename)

        zip_archiver.copy_from_archive(self.archiver)
