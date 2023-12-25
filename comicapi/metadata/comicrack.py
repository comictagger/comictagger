"""A class to encapsulate ComicRack's ComicInfo.xml data"""
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
import xml.etree.ElementTree as ET
from collections import OrderedDict
from typing import Any

from comicapi import utils
from comicapi.archivers import Archiver
from comicapi.genericmetadata import GenericMetadata, ImageMetadata
from comicapi.metadata import Metadata

logger = logging.getLogger(__name__)


class ComicRack(Metadata):
    _writer_synonyms = ("writer", "plotter", "scripter")
    _penciller_synonyms = ("artist", "penciller", "penciler", "breakdowns")
    _inker_synonyms = ("inker", "artist", "finishes")
    _colorist_synonyms = ("colorist", "colourist", "colorer", "colourer")
    _letterer_synonyms = ("letterer",)
    _cover_synonyms = ("cover", "covers", "coverartist", "cover artist")
    _editor_synonyms = ("editor",)

    enabled = True

    short_name = "cr"

    def __init__(self, version: str) -> None:
        super().__init__(version)

        self.file = "ComicInfo.xml"
        self.supported_attributes = {
            "series",
            "issue",
            "issue_count",
            "title",
            "volume",
            "genres",
            "description",
            "notes",
            "alternate_series",
            "alternate_number",
            "alternate_count",
            "story_arcs",
            "series_groups",
            "publisher",
            "imprint",
            "day",
            "month",
            "year",
            "language",
            "web_link",
            "format",
            "manga",
            "black_and_white",
            "maturity_rating",
            "critical_rating",
            "scan_info",
            "pages",
            "pages.bookmark",
            "pages.double_page",
            "pages.height",
            "pages.image_index",
            "pages.size",
            "pages.type",
            "pages.width",
            "page_count",
            "characters",
            "teams",
            "locations",
            "credits",
            "credits.person",
            "credits.role",
        }

    def supports_credit_role(self, role: str) -> bool:
        return role.casefold() in self._get_parseable_credits()

    def supports_metadata(self, archive: Archiver) -> bool:
        return archive.supports_files()

    def has_metadata(self, archive: Archiver) -> bool:
        return (
            self.supports_metadata(archive)
            and self.file in archive.get_filename_list()
            and self._validate_bytes(archive.read_file(self.file))
        )

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
            xml = b""
            if self.has_metadata(archive):
                xml = archive.read_file(self.file)
            return archive.write_file(self.file, self._bytes_from_metadata(metadata, xml))
        else:
            logger.warning(f"Archive ({archive.name()}) does not support {self.name()} metadata")
        return False

    def name(self) -> str:
        return "Comic Rack"

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
        root = ET.fromstring(string)
        return self._convert_xml_to_metadata(root)

    def _bytes_from_metadata(self, metadata: GenericMetadata, xml: bytes = b"") -> bytes:
        root = self._convert_metadata_to_xml(metadata, xml)
        return ET.tostring(root, encoding="utf-8", xml_declaration=True)

    def _convert_metadata_to_xml(self, metadata: GenericMetadata, xml: bytes = b"") -> ET.Element:
        # shorthand for the metadata
        md = metadata

        if xml:
            root = ET.fromstring(xml)
        else:
            # build a tree structure
            root = ET.Element("ComicInfo")
            root.attrib["xmlns:xsi"] = "http://www.w3.org/2001/XMLSchema-instance"
            root.attrib["xmlns:xsd"] = "http://www.w3.org/2001/XMLSchema"
        # helper func

        def assign(cr_entry: str, md_entry: Any) -> None:
            if md_entry:
                text = ""
                if isinstance(md_entry, str):
                    text = md_entry
                elif isinstance(md_entry, (list, set)):
                    text = ",".join(md_entry)
                else:
                    text = str(md_entry)
                et_entry = root.find(cr_entry)
                if et_entry is not None:
                    et_entry.text = text
                else:
                    ET.SubElement(root, cr_entry).text = text
            else:
                et_entry = root.find(cr_entry)
                if et_entry is not None:
                    root.remove(et_entry)

        # need to specially process the credits, since they are structured
        # differently than CIX
        credit_writer_list = []
        credit_penciller_list = []
        credit_inker_list = []
        credit_colorist_list = []
        credit_letterer_list = []
        credit_cover_list = []
        credit_editor_list = []

        # first, loop thru credits, and build a list for each role that CIX
        # supports
        for credit in metadata.credits:
            if credit["role"].casefold() in set(self._writer_synonyms):
                credit_writer_list.append(credit["person"].replace(",", ""))

            if credit["role"].casefold() in set(self._penciller_synonyms):
                credit_penciller_list.append(credit["person"].replace(",", ""))

            if credit["role"].casefold() in set(self._inker_synonyms):
                credit_inker_list.append(credit["person"].replace(",", ""))

            if credit["role"].casefold() in set(self._colorist_synonyms):
                credit_colorist_list.append(credit["person"].replace(",", ""))

            if credit["role"].casefold() in set(self._letterer_synonyms):
                credit_letterer_list.append(credit["person"].replace(",", ""))

            if credit["role"].casefold() in set(self._cover_synonyms):
                credit_cover_list.append(credit["person"].replace(",", ""))

            if credit["role"].casefold() in set(self._editor_synonyms):
                credit_editor_list.append(credit["person"].replace(",", ""))

        assign("Series", md.series)
        assign("Number", md.issue)
        assign("Count", md.issue_count)
        assign("Title", md.title)
        assign("Volume", md.volume)
        assign("Genre", md.genres)
        assign("Summary", md.description)
        assign("Notes", md.notes)

        assign("AlternateSeries", md.alternate_series)
        assign("AlternateNumber", md.alternate_number)
        assign("AlternateCount", md.alternate_count)
        assign("StoryArc", md.story_arcs)
        assign("SeriesGroup", md.series_groups)

        assign("Publisher", md.publisher)
        assign("Imprint", md.imprint)
        assign("Day", md.day)
        assign("Month", md.month)
        assign("Year", md.year)
        assign("LanguageISO", md.language)
        assign("Web", md.web_link)
        assign("Format", md.format)
        assign("Manga", md.manga)
        assign("BlackAndWhite", "Yes" if md.black_and_white else None)
        assign("AgeRating", md.maturity_rating)
        assign("CommunityRating", md.critical_rating)
        assign("ScanInformation", md.scan_info)

        assign("PageCount", md.page_count)

        assign("Characters", md.characters)
        assign("Teams", md.teams)
        assign("Locations", md.locations)
        assign("Writer", ", ".join(credit_writer_list))
        assign("Penciller", ", ".join(credit_penciller_list))
        assign("Inker", ", ".join(credit_inker_list))
        assign("Colorist", ", ".join(credit_colorist_list))
        assign("Letterer", ", ".join(credit_letterer_list))
        assign("CoverArtist", ", ".join(credit_cover_list))
        assign("Editor", ", ".join(credit_editor_list))

        #  loop and add the page entries under pages node
        pages_node = root.find("Pages")
        if pages_node is not None:
            pages_node.clear()
        else:
            pages_node = ET.SubElement(root, "Pages")

        for page_dict in md.pages:
            page_node = ET.SubElement(pages_node, "Page")
            page_node.attrib = {}
            if "bookmark" in page_dict:
                page_node.attrib["Bookmark"] = str(page_dict["bookmark"])
            if "double_page" in page_dict:
                page_node.attrib["DoublePage"] = str(page_dict["double_page"])
            if "image_index" in page_dict:
                page_node.attrib["Image"] = str(page_dict["image_index"])
            if "height" in page_dict:
                page_node.attrib["ImageHeight"] = str(page_dict["height"])
            if "size" in page_dict:
                page_node.attrib["ImageSize"] = str(page_dict["size"])
            if "width" in page_dict:
                page_node.attrib["ImageWidth"] = str(page_dict["width"])
            if "type" in page_dict:
                page_node.attrib["Type"] = str(page_dict["type"])
            page_node.attrib = OrderedDict(sorted(page_node.attrib.items()))

        ET.indent(root)

        return root

    def _convert_xml_to_metadata(self, root: ET.Element) -> GenericMetadata:
        if root.tag != "ComicInfo":
            raise Exception("Not a ComicInfo file")

        def get(name: str) -> str | None:
            tag = root.find(name)
            if tag is None:
                return None
            return tag.text

        md = GenericMetadata()

        md.series = utils.xlate(get("Series"))
        md.issue = utils.xlate(get("Number"))
        md.issue_count = utils.xlate_int(get("Count"))
        md.title = utils.xlate(get("Title"))
        md.volume = utils.xlate_int(get("Volume"))
        md.genres = set(utils.split(get("Genre"), ","))
        md.description = utils.xlate(get("Summary"))
        md.notes = utils.xlate(get("Notes"))

        md.alternate_series = utils.xlate(get("AlternateSeries"))
        md.alternate_number = utils.xlate(get("AlternateNumber"))
        md.alternate_count = utils.xlate_int(get("AlternateCount"))
        md.story_arcs = utils.split(get("StoryArc"), ",")
        md.series_groups = utils.split(get("SeriesGroup"), ",")

        md.publisher = utils.xlate(get("Publisher"))
        md.imprint = utils.xlate(get("Imprint"))
        md.day = utils.xlate_int(get("Day"))
        md.month = utils.xlate_int(get("Month"))
        md.year = utils.xlate_int(get("Year"))
        md.language = utils.xlate(get("LanguageISO"))
        md.web_link = utils.xlate(get("Web"))
        md.format = utils.xlate(get("Format"))
        md.manga = utils.xlate(get("Manga"))
        md.maturity_rating = utils.xlate(get("AgeRating"))
        md.critical_rating = utils.xlate_float(get("CommunityRating"))
        md.scan_info = utils.xlate(get("ScanInformation"))

        md.page_count = utils.xlate_int(get("PageCount"))

        md.characters = set(utils.split(get("Characters"), ","))
        md.teams = set(utils.split(get("Teams"), ","))
        md.locations = set(utils.split(get("Locations"), ","))

        tmp = utils.xlate(get("BlackAndWhite"))
        if tmp is not None:
            md.black_and_white = tmp.casefold() in ["yes", "true", "1"]

        # Now extract the credit info
        for n in root:
            if any(
                [
                    n.tag == "Writer",
                    n.tag == "Penciller",
                    n.tag == "Inker",
                    n.tag == "Colorist",
                    n.tag == "Letterer",
                    n.tag == "Editor",
                ]
            ):
                if n.text is not None:
                    for name in utils.split(n.text, ","):
                        md.add_credit(name.strip(), n.tag)

            if n.tag == "CoverArtist":
                if n.text is not None:
                    for name in utils.split(n.text, ","):
                        md.add_credit(name.strip(), "Cover")

        # parse page data now
        pages_node = root.find("Pages")
        if pages_node is not None:
            for i, page in enumerate(pages_node):
                p: dict[str, Any] = page.attrib
                md_page = ImageMetadata(image_index=int(p.get("Image", i)))

                if "Bookmark" in p:
                    md_page["bookmark"] = p["Bookmark"]
                if "DoublePage" in p:
                    md_page["double_page"] = True if p["DoublePage"].casefold() in ("yes", "true", "1") else False
                if "ImageHeight" in p:
                    md_page["height"] = p["ImageHeight"]
                if "ImageSize" in p:
                    md_page["size"] = p["ImageSize"]
                if "ImageWidth" in p:
                    md_page["width"] = p["ImageWidth"]
                if "Type" in p:
                    md_page["type"] = p["Type"]

                md.pages.append(md_page)

        md.is_empty = False

        return md

    def _validate_bytes(self, string: bytes) -> bool:
        """verify that the string actually contains CIX data in XML format"""
        try:
            root = ET.fromstring(string)
            if root.tag != "ComicInfo":
                return False
        except ET.ParseError:
            return False

        return True
