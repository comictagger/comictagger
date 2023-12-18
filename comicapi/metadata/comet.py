"""A class to encapsulate CoMet data"""
#
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

import logging
import os
import xml.etree.ElementTree as ET
from typing import Any

from comicapi import utils
from comicapi.archivers import Archiver
from comicapi.genericmetadata import GenericMetadata
from comicapi.metadata import Metadata

logger = logging.getLogger(__name__)


class CoMet(Metadata):
    _writer_synonyms = ("writer", "plotter", "scripter")
    _penciller_synonyms = ("artist", "penciller", "penciler", "breakdowns")
    _inker_synonyms = ("inker", "artist", "finishes")
    _colorist_synonyms = ("colorist", "colourist", "colorer", "colourer")
    _letterer_synonyms = ("letterer",)
    _cover_synonyms = ("cover", "covers", "coverartist", "cover artist")
    _editor_synonyms = ("editor",)

    enabled = True

    short_name = "comet"

    def __init__(self, version: str) -> None:
        super().__init__(version)

        self.comet_filename = "CoMet.xml"
        self.file = "CoMet.xml"
        self.supported_attributes = {
            "series",
            "issue",
            "title",
            "volume",
            "genres",
            "description",
            "publisher",
            "language",
            "format",
            "maturity_rating",
            "month",
            "year",
            "page_count",
            "characters",
            "credits",
            "credits.person",
            "credits.primary",
            "credits.role",
            "price",
            "is_version_of",
            "rights",
            "identifier",
            "last_mark",
            "pages.type",  # This is required for setting the cover image none of the other types will be saved
            "pages",
        }

    def supports_credit_role(self, role: str) -> bool:
        return role.casefold() in self._get_parseable_credits()

    def supports_metadata(self, archive: Archiver) -> bool:
        return archive.supports_files()

    def has_metadata(self, archive: Archiver) -> bool:
        if not self.supports_metadata(archive):
            return False
        has_metadata = False
        # look at all xml files in root, and search for CoMet data, get first
        for n in archive.get_filename_list():
            if os.path.dirname(n) == "" and os.path.splitext(n)[1].casefold() == ".xml":
                # read in XML file, and validate it
                data = b""
                try:
                    data = archive.read_file(n)
                except Exception as e:
                    logger.warning("Error reading in Comet XML for validation! from %s: %s", archive.path, e)
                if self._validate_bytes(data):
                    # since we found it, save it!
                    self.file = n
                    has_metadata = True
                    break
        return has_metadata

    def remove_metadata(self, archive: Archiver) -> bool:
        return self.has_metadata(archive) and archive.remove_file(self.file)

    def get_metadata(self, archive: Archiver) -> GenericMetadata:
        if self.has_metadata(archive):
            metadata = archive.read_file(self.file) or b""
            if self._validate_bytes(metadata):
                return self._metadata_from_bytes(metadata)
        return GenericMetadata()

    def get_metadata_string(self, archive: Archiver) -> str:
        if self.has_metadata(archive):
            return ET.tostring(ET.fromstring(archive.read_file(self.file)), encoding="unicode", xml_declaration=True)
        return ""

    def set_metadata(self, metadata: GenericMetadata, archive: Archiver) -> bool:
        if self.supports_metadata(archive):
            success = True
            if self.file != self.comet_filename:
                success = self.remove_metadata(archive)
            return archive.write_file(self.comet_filename, self._bytes_from_metadata(metadata)) and success
        else:
            logger.warning(f"Archive ({archive.name()}) does not support {self.name()} metadata")
        return False

    def name(self) -> str:
        return "Comic Metadata (CoMet)"

    @classmethod
    def _get_parseable_credits(cls) -> list[str]:
        parsable_credits: list[str] = []
        parsable_credits.extend(cls._writer_synonyms)
        parsable_credits.extend(cls._penciller_synonyms)
        parsable_credits.extend(cls._inker_synonyms)
        parsable_credits.extend(cls._colorist_synonyms)
        parsable_credits.extend(cls._letterer_synonyms)
        parsable_credits.extend(cls._cover_synonyms)
        parsable_credits.extend(cls._editor_synonyms)
        return parsable_credits

    def _metadata_from_bytes(self, string: bytes) -> GenericMetadata:
        tree = ET.ElementTree(ET.fromstring(string))
        return self._convert_xml_to_metadata(tree)

    def _bytes_from_metadata(self, metadata: GenericMetadata) -> bytes:
        tree = self._convert_metadata_to_xml(metadata)
        return ET.tostring(tree.getroot(), encoding="utf-8", xml_declaration=True)

    def _convert_metadata_to_xml(self, metadata: GenericMetadata) -> ET.ElementTree:
        # shorthand for the metadata
        md = metadata

        # build a tree structure
        root = ET.Element("comet")
        root.attrib["xmlns:comet"] = "http://www.denvog.com/comet/"
        root.attrib["xmlns:xsi"] = "http://www.w3.org/2001/XMLSchema-instance"
        root.attrib["xsi:schemaLocation"] = "http://www.denvog.com http://www.denvog.com/comet/comet.xsd"

        # helper func
        def assign(comet_entry: str, md_entry: Any) -> None:
            if md_entry is not None:
                ET.SubElement(root, comet_entry).text = str(md_entry)

        # title is manditory
        if md.title is None:
            md.title = ""
        assign("title", md.title)
        assign("series", md.series)
        assign("issue", md.issue)  # must be int??
        assign("volume", md.volume)
        assign("description", md.description)
        assign("publisher", md.publisher)
        assign("pages", md.page_count)
        assign("format", md.format)
        assign("language", md.language)
        assign("rating", md.maturity_rating)
        assign("price", md.price)
        assign("isVersionOf", md.is_version_of)
        assign("rights", md.rights)
        assign("identifier", md.identifier)
        assign("lastMark", md.last_mark)
        assign("genre", ",".join(md.genres))  # TODO repeatable

        if md.characters is not None:
            char_list = [c.strip() for c in md.characters]
            for c in char_list:
                assign("character", c)

        if md.manga is not None and md.manga == "YesAndRightToLeft":
            assign("readingDirection", "rtl")

        if md.year is not None:
            date_str = f"{md.year:04}"
            if md.month is not None:
                date_str += f"-{md.month:02}"
            assign("date", date_str)

        assign("coverImage", md._cover_image)

        # loop thru credits, and build a list for each role that CoMet supports
        for credit in metadata.credits:
            if credit["role"].casefold() in set(self._writer_synonyms):
                ET.SubElement(root, "writer").text = str(credit["person"])

            if credit["role"].casefold() in set(self._penciller_synonyms):
                ET.SubElement(root, "penciller").text = str(credit["person"])

            if credit["role"].casefold() in set(self._inker_synonyms):
                ET.SubElement(root, "inker").text = str(credit["person"])

            if credit["role"].casefold() in set(self._colorist_synonyms):
                ET.SubElement(root, "colorist").text = str(credit["person"])

            if credit["role"].casefold() in set(self._letterer_synonyms):
                ET.SubElement(root, "letterer").text = str(credit["person"])

            if credit["role"].casefold() in set(self._cover_synonyms):
                ET.SubElement(root, "coverDesigner").text = str(credit["person"])

            if credit["role"].casefold() in set(self._editor_synonyms):
                ET.SubElement(root, "editor").text = str(credit["person"])

        ET.indent(root)

        # wrap it in an ElementTree instance, and save as XML
        tree = ET.ElementTree(root)
        return tree

    def _convert_xml_to_metadata(self, tree: ET.ElementTree) -> GenericMetadata:
        root = tree.getroot()

        if root.tag != "comet":
            raise Exception("Not a CoMet file")

        metadata = GenericMetadata()
        md = metadata

        # Helper function
        def get(tag: str) -> Any:
            node = root.find(tag)
            if node is not None:
                return node.text
            return None

        md.series = utils.xlate(get("series"))
        md.title = utils.xlate(get("title"))
        md.issue = utils.xlate(get("issue"))
        md.volume = utils.xlate_int(get("volume"))
        md.description = utils.xlate(get("description"))
        md.publisher = utils.xlate(get("publisher"))
        md.language = utils.xlate(get("language"))
        md.format = utils.xlate(get("format"))
        md.page_count = utils.xlate_int(get("pages"))
        md.maturity_rating = utils.xlate(get("rating"))
        md.price = utils.xlate_float(get("price"))
        md.is_version_of = utils.xlate(get("isVersionOf"))
        md.rights = utils.xlate(get("rights"))
        md.identifier = utils.xlate(get("identifier"))
        md.last_mark = utils.xlate(get("lastMark"))

        _, md.month, md.year = utils.parse_date_str(utils.xlate(get("date")))

        md._cover_image = utils.xlate(get("coverImage"))

        reading_direction = utils.xlate(get("readingDirection"))
        if reading_direction is not None and reading_direction == "rtl":
            md.manga = "YesAndRightToLeft"

        # loop for genre tags
        for n in root:
            if n.tag == "genre":
                md.genres.add((n.text or "").strip())

        # loop for character tags
        for n in root:
            if n.tag == "character":
                md.characters.add((n.text or "").strip())

        # Now extract the credit info
        for n in root:
            if any(
                [
                    n.tag == "writer",
                    n.tag == "penciller",
                    n.tag == "inker",
                    n.tag == "colorist",
                    n.tag == "letterer",
                    n.tag == "editor",
                ]
            ):
                metadata.add_credit((n.text or "").strip(), n.tag.title())

            if n.tag == "coverDesigner":
                metadata.add_credit((n.text or "").strip(), "Cover")

        metadata.is_empty = False

        return metadata

    # verify that the string actually contains CoMet data in XML format
    def _validate_bytes(self, string: bytes) -> bool:
        try:
            tree = ET.ElementTree(ET.fromstring(string))
            root = tree.getroot()
            if root.tag != "comet":
                return False
        except ET.ParseError:
            return False

        return True
