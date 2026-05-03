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
from collections.abc import Collection, Iterable
from typing import ClassVar, cast

from comictaggerlib.ctversion import version

from . import utils
from .comic import ComicFile, UnknownArchiver, WrongType, ZipComic
from .genericmetadata import FileHash, GenericMetadata
from .tags import Tag, TagLocation

logger = logging.getLogger(__name__)

archivers: list[type[ComicFile]] = []
loaded_tags: dict[str, Tag] = {}


def load_archive_plugins(local_plugins: Iterable[type[ComicFile]] = tuple()) -> None:
    if archivers:
        return
    from importlib.metadata import entry_points

    builtin: list[type[ComicFile]] = []
    archive_plugins: list[type[ComicFile]] = []
    # A list is used first matching plugin wins

    for ep in itertools.chain(entry_points(group="comicapi.archiver")):
        try:
            spec = importlib.util.find_spec(ep.module)
        except ValueError:
            spec = None
        try:
            archiver: type[ComicFile] = ep.load()
            if not archiver.enabled:
                logger.info("Archiver %r (%s) is disabled. Refusing to load archiver plugin", archiver.name, ep.name)
                continue
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


__custom_tags: dict[str, Tag] = {}


def custom_tag(comic_file: type[ComicFile]) -> Tag:
    tag_id = f"custom_{comic_file.__name__.lower()}"
    if tag_id in __custom_tags:
        return __custom_tags[tag_id]

    class ClassName:
        id: ClassVar[str] = tag_id
        name: ClassVar[str] = comic_file.name
        enabled: ClassVar[bool] = comic_file.enabled

        location: ClassVar[TagLocation] = TagLocation.CUSTOM

        supported_attributes: ClassVar[frozenset[str]] = comic_file.supported_attributes
        _comic_file: ClassVar[type[ComicFile]] = comic_file

    ClassName.__name__ = comic_file.__name__ + "Tag"
    if isinstance(ClassName, Tag):
        return __custom_tags.setdefault(tag_id, ClassName)
    raise SystemError("Unable to create custom tags")


def load_tag_plugins(version: str = f"ComicAPI/{version}", local_plugins: Iterable[Tag] = tuple()) -> None:
    if loaded_tags:
        return
    from importlib.metadata import entry_points

    builtin: dict[str, Tag] = {}
    tag_plugins: dict[str, tuple[Tag, str]] = {}
    custom_tag_plugins: dict[str, Tag] = {}
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
            tag: Tag = ep.load()
            if not tag.enabled:
                logger.info("Tag %r (%s) is disabled. Refusing to load tag plugin", tag.name, ep.name)
                continue
            if ep.module.startswith("comicapi"):
                builtin[tag.id] = tag
            else:
                if tag.id in tag_plugins:
                    logger.warning(
                        "Plugin %s from %s is overriding the existing plugin for %s tags",
                        ep.module,
                        location,
                        tag.id,
                    )
                tag_plugins[tag.id] = (tag, location)
        except Exception:
            logger.exception("Failed to load tag plugin: %s from %s", ep.name, location)
    # A dict is used, last plugin wins
    for tag in local_plugins:
        if not tag.enabled:
            logger.info("Local Tag %r (%s) is disabled. Refusing to load tag plugin", tag.name, tag.id)
            continue
        tag_plugins[tag.id] = (tag, "Local")

    for archive in archivers:
        if TagLocation.CUSTOM in archive.tag_locations:
            tag = custom_tag(archive)
            custom_tag_plugins[tag.id] = tag

    for tag_id in set(builtin.keys()).intersection(tag_plugins):
        location = tag_plugins[tag_id][1]
        logger.warning("Builtin plugin for %s tags are being overridden by a plugin from %s", tag_id, location)

    loaded_tags.clear()
    loaded_tags.update(builtin)
    loaded_tags.update({s[0]: s[1][0] for s in tag_plugins.items()})
    loaded_tags.update(custom_tag_plugins)


class ComicArchive:

    logo_data = b""

    def __init__(
        self,
        path: pathlib.Path | ComicFile,
        default_image_path: pathlib.Path | None = None,
        hash_archive: str = "",
    ) -> None:
        self.md: dict[str, GenericMetadata] = {}
        self.page_count: int | None = None
        self.page_list: list[str] = []
        self.hash_archive = hash_archive
        self.Archiver: type[ComicFile] = UnknownArchiver
        self.archiver: ComicFile | None = None

        self.reset_cache()
        self.default_image_path = default_image_path

        if isinstance(path, pathlib.Path):
            self.path = pathlib.Path(path).absolute()

            load_archive_plugins()
            load_tag_plugins()

            tried_archivers = []
            for archiver in archivers:
                if self.path.suffix not in archiver.supported_extensions:
                    continue
                tried_archivers.append(archiver)
                try:
                    archiver.check_path(self.path)
                    self.Archiver = archiver
                    break
                except WrongType:
                    continue

            if self.Archiver == UnknownArchiver:
                for archiver in archivers:
                    if archiver in tried_archivers:
                        continue
                    try:
                        archiver.check_path(self.path)
                        self.Archiver = archiver
                        break
                    except WrongType:
                        continue
        else:
            self.path = path.path
            self.archiver = path
            self.Archiver = type(path)

        if not ComicArchive.logo_data and self.default_image_path:
            with self.default_image_path.open(mode="rb") as fd:
                ComicArchive.logo_data = fd.read()

    def reset_cache(self) -> None:
        """Clears the cached data"""

        self.page_count = None
        self.page_list.clear()
        self.md.clear()

    def _open_archive(self) -> ComicFile:
        if self.Archiver is UnknownArchiver:
            raise Exception("Archive not opened")
        if self.archiver is None:
            self.archiver = self.Archiver(self.path)
        return self.archiver

    def get_supported_tags(self, tags: Collection[Tag] = loaded_tags.values()) -> list[Tag]:
        allowed_locations = self.Archiver.tag_locations - {TagLocation.CUSTOM}
        allowed_tags = [tag for tag in tags if tag.location in allowed_locations]
        if TagLocation.CUSTOM in self.Archiver.tag_locations:
            allowed_tags.append(custom_tag(self.Archiver))
        return allowed_tags

    def _supported_tag(self, tag: Tag) -> None:
        if tag.location not in self.Archiver.tag_locations:
            raise Exception(f"{tag.name} tags Not Supported for Comic {self.Archiver.name}")
        if tag.location == TagLocation.CUSTOM:
            if tag._comic_file != self.Archiver:
                raise Exception(
                    f"{tag.name} tags are only supported on {tag._comic_file.name} not {self.Archiver.name}"
                )

    def rename(self, path: pathlib.Path) -> None:
        if self.archiver is not None:
            # self.archiver.close()
            self.archiver = None

        new_path = path.absolute()
        if new_path == self.path:
            return
        os.makedirs(new_path.parent, 0o777, True)
        shutil.move(self.path, new_path)
        self.path = new_path

    def is_writable(self, check_archive_status: bool = True) -> bool:
        if not (os.access(self.path, os.W_OK) and os.access(self.path.parent, os.W_OK)):
            return False

        if check_archive_status:
            self.archiver = self._open_archive()
            if not self.archiver.is_writable():
                return False

        return True

    def is_zip(self) -> bool:
        return self.Archiver.extension == ".cbz"

    def seems_to_be_a_comic_archive(self) -> bool:
        if self.Archiver is UnknownArchiver:
            return False

        try:
            # self.Archiver.check_path(self.path) # This check isn't needed as check_path is ran during __init__
            return self.get_number_of_pages() > 0
        except Exception:
            ...

        return False

    def extension(self) -> str:
        return self.Archiver.extension

    def read_tags(self, tag: Tag) -> GenericMetadata:
        try:
            self._supported_tag(tag)
        except Exception as e:
            return GenericMetadata()
        if tag.id in self.md:
            return self.md[tag.id]
        md = GenericMetadata()

        if tag.location == TagLocation.COMMENT:
            a = self._open_archive()
            comment = a.read_comment()
            if not tag.validate_tags(comment.encode(encoding="utf-8")):
                return md
            md = tag.load_tags(comment.encode(encoding="utf-8"))
        if tag.location == TagLocation.FILE:
            filename = self._find_file(tag)
            if filename == "":
                return md

            a = self._open_archive()
            file_content = a.read_file(filename)
            if not tag.validate_tags(file_content):
                return md
            md = tag.load_tags(file_content)
        if tag.location == TagLocation.CUSTOM:
            a = self._open_archive()
            if not a.has_tags():
                return md
            md = a.load_tags()
        md.apply_default_page_list(self.get_page_name_list())
        return md

    def _find_file(self, tag: Tag) -> str:
        a = self._open_archive()
        filenames = a.get_filename_list()
        if not filenames:
            return ""
        if tag.filename_match[0] == "*":
            for name in filenames:
                if name.endswith(tag.filename_match[1:]):
                    return name
            return ""
        for name in filenames:
            if name == tag.filename_match:
                return name
        return ""

    def read_raw_tags(self, tag: Tag) -> str:
        self._supported_tag(tag)
        if tag.location == TagLocation.COMMENT:
            a = self._open_archive()
            content = a.read_comment()
            return tag.display_tags(content.encode(encoding="utf-8"))
        if tag.location == TagLocation.FILE:
            filename = self._find_file(tag)
            if filename == "":
                return ""

            a = self._open_archive()
            file_content = a.read_file(filename)
            return tag.display_tags(file_content)
        if tag.location == TagLocation.CUSTOM:
            a = self._open_archive()
            return a.display_tags()
        return ""

    def write_tags(self, version: str, metadata: GenericMetadata, tag: Tag) -> None:
        self._supported_tag(tag)
        if tag.id in self.md:
            del self.md[tag.id]

        self.apply_archive_info_to_metadata(metadata, True, True, hash_archive=self.hash_archive)
        if tag.location == TagLocation.COMMENT:
            a = self._open_archive()
            content = a.read_comment()
            return a.write_comment(tag.create_tags(version, metadata, content.encode(encoding="utf-8")).decode("utf-8"))
        if tag.location == TagLocation.FILE:
            filename = self._find_file(tag)
            file_content = b""
            a = self._open_archive()
            if filename:
                file_content = a.read_file(filename)
            else:
                filename = tag.filename

            return a.write_file(filename, tag.create_tags(version, metadata, file_content))
        if tag.location == TagLocation.CUSTOM:
            a = self._open_archive()
            return a.write_tags(version, metadata)

    def has_tags(self, tag: Tag) -> bool:
        if tag.location not in self.Archiver.tag_locations:
            return False
        if tag.location == TagLocation.CUSTOM:
            if tag._comic_file != self.Archiver:
                return False

        if tag.location == TagLocation.COMMENT:
            a = self._open_archive()
            comment = a.read_comment()
            return tag.validate_tags(comment.encode(encoding="utf-8"))
        if tag.location == TagLocation.FILE:
            filename = self._find_file(tag)
            if filename == "":
                return False

            a = self._open_archive()
            file_content = a.read_file(filename)
            return tag.validate_tags(file_content)
        if tag.location == TagLocation.CUSTOM:
            a = self._open_archive()
            return a.has_tags()
        return False

    def remove_tags(self, tag: Tag) -> None:
        self._supported_tag(tag)
        if tag.id in self.md:
            del self.md[tag.id]
        if tag.location == TagLocation.COMMENT:
            a = self._open_archive()
            return a.write_comment("")
        if tag.location == TagLocation.FILE:
            filename = self._find_file(tag)
            if filename == "":
                return

            a = self._open_archive()
            return a.remove_files([filename])
        if tag.location == TagLocation.CUSTOM:
            a = self._open_archive()
            return a.remove_tags()

    def load_cache(self, loaded_tags: Iterable[Tag]) -> None:
        for tag in loaded_tags:
            try:
                md = self.read_tags(tag)
                if not md.is_empty:
                    self.md[tag.id] = md
            except Exception:
                ...

    def get_page(self, index: int) -> bytes:
        image_data = b""

        filename = self.get_page_name(index)

        if filename:
            try:
                a = self._open_archive()
                image_data = a.read_file(filename)
            except Exception:
                logger.exception("Error reading in page %d. Substituting logo page.", index)
                image_data = ComicArchive.logo_data

        return image_data

    def get_page_name(self, index: int) -> str:
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
            utils.initialize_pil()
            a = self._open_archive()
            self.page_list = utils.get_page_name_list(a.get_filename_list())

        return self.page_list

    def get_number_of_pages(self) -> int:
        if self.page_count is None:
            self.page_count = len(self.get_page_name_list())
        return self.page_count

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
            if self.path.is_dir():
                return
            hasher = getattr(hashlib, hash_archive, hash_archive)
            try:
                with self.path.open("b+r") as archive:
                    digest = utils.file_digest(archive, hasher)
                if len(inspect.signature(digest.hexdigest).parameters) > 0:
                    length = digest.name.rpartition("_")[2]
                    if not length.isdigit():
                        length = "128"
                    md.original_hash = FileHash(digest.name, digest.hexdigest(int(length) // 8))  # type: ignore[call-arg]
                else:
                    md.original_hash = FileHash(digest.name, digest.hexdigest())
            except Exception:
                logger.exception("Failed to calculate original hash for '%s'", self.path)
        if not calc_page_sizes:
            return
        for p in md.pages:
            if p.byte_size is None or p.height is None or p.width is None or p.double_page is None:
                try:
                    data = self.get_page(p.archive_index)
                    p.byte_size = len(data)
                    if not data or not utils.initialize_pil():
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

    def export_as(self, export_type: type[ComicFile], new_filename: pathlib.Path) -> None:
        """
        Copies all content from the current archive to
        """
        if export_type == UnknownArchiver:
            export_type = cast(type[ComicFile], ZipComic)
        export_comic = export_type(new_filename)
        a = self._open_archive()
        export_comic.write_files(files=a.read_files(a.get_filename_list()), filenames=a.get_filename_list())

        if TagLocation.COMMENT in export_comic.tag_locations and TagLocation.COMMENT in a.tag_locations:
            export_comic.write_comment(a.read_comment())
