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
from typing import Any, cast
from xml.etree.ElementTree import ElementTree

from comicapi import utils
from comicapi.genericmetadata import GenericMetadata, ImageMetadata

logger = logging.getLogger(__name__)


class ComicInfoXml:
    writer_synonyms = ["writer", "plotter", "scripter"]
    penciller_synonyms = ["artist", "penciller", "penciler", "breakdowns"]
    inker_synonyms = ["inker", "artist", "finishes"]
    colorist_synonyms = ["colorist", "colourist", "colorer", "colourer"]
    letterer_synonyms = ["letterer"]
    cover_synonyms = ["cover", "covers", "coverartist", "cover artist"]
    editor_synonyms = ["editor"]

    def get_parseable_credits(self) -> list[str]:
        parsable_credits = []
        parsable_credits.extend(self.writer_synonyms)
        parsable_credits.extend(self.penciller_synonyms)
        parsable_credits.extend(self.inker_synonyms)
        parsable_credits.extend(self.colorist_synonyms)
        parsable_credits.extend(self.letterer_synonyms)
        parsable_credits.extend(self.cover_synonyms)
        parsable_credits.extend(self.editor_synonyms)
        return parsable_credits

    def metadata_from_string(self, string: bytes) -> GenericMetadata:
        tree = ET.ElementTree(ET.fromstring(string))
        return self.convert_xml_to_metadata(tree)

    def string_from_metadata(self, metadata: GenericMetadata, xml: bytes = b"") -> str:
        tree = self.convert_metadata_to_xml(metadata, xml)
        tree_str = ET.tostring(tree.getroot(), encoding="utf-8", xml_declaration=True).decode("utf-8")
        return str(tree_str)

    def convert_metadata_to_xml(self, metadata: GenericMetadata, xml: bytes = b"") -> ElementTree:
        # shorthand for the metadata
        md = metadata

        if xml:
            root = ET.ElementTree(ET.fromstring(xml)).getroot()
        else:
            # build a tree structure
            root = ET.Element("ComicInfo")
            root.attrib["xmlns:xsi"] = "http://www.w3.org/2001/XMLSchema-instance"
            root.attrib["xmlns:xsd"] = "http://www.w3.org/2001/XMLSchema"
        # helper func

        def assign(cix_entry: str, md_entry: Any) -> None:
            if md_entry:
                text = ""
                if isinstance(md_entry, str):
                    text = md_entry
                elif isinstance(md_entry, (list, set)):
                    text = ",".join(md_entry)
                else:
                    text = str(md_entry)
                et_entry = root.find(cix_entry)
                if et_entry is not None:
                    et_entry.text = text
                else:
                    ET.SubElement(root, cix_entry).text = text
            else:
                et_entry = root.find(cix_entry)
                if et_entry is not None:
                    root.remove(et_entry)

        assign("Title", md.title)
        assign("Series", md.series)
        assign("Number", md.issue)
        assign("Count", md.issue_count)
        assign("Volume", md.volume)
        assign("AlternateSeries", md.alternate_series)
        assign("AlternateNumber", md.alternate_number)
        assign("StoryArc", md.story_arcs)
        assign("SeriesGroup", md.series_groups)
        assign("AlternateCount", md.alternate_count)
        assign("Summary", md.description)
        assign("Notes", md.notes)
        assign("Year", md.year)
        assign("Month", md.month)
        assign("Day", md.day)

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
            if credit["role"].casefold() in set(self.writer_synonyms):
                credit_writer_list.append(credit["person"].replace(",", ""))

            if credit["role"].casefold() in set(self.penciller_synonyms):
                credit_penciller_list.append(credit["person"].replace(",", ""))

            if credit["role"].casefold() in set(self.inker_synonyms):
                credit_inker_list.append(credit["person"].replace(",", ""))

            if credit["role"].casefold() in set(self.colorist_synonyms):
                credit_colorist_list.append(credit["person"].replace(",", ""))

            if credit["role"].casefold() in set(self.letterer_synonyms):
                credit_letterer_list.append(credit["person"].replace(",", ""))

            if credit["role"].casefold() in set(self.cover_synonyms):
                credit_cover_list.append(credit["person"].replace(",", ""))

            if credit["role"].casefold() in set(self.editor_synonyms):
                credit_editor_list.append(credit["person"].replace(",", ""))

        # second, convert each list to string, and add to XML struct
        assign("Writer", ", ".join(credit_writer_list))
        assign("Penciller", ", ".join(credit_penciller_list))
        assign("Inker", ", ".join(credit_inker_list))
        assign("Colorist", ", ".join(credit_colorist_list))
        assign("Letterer", ", ".join(credit_letterer_list))
        assign("CoverArtist", ", ".join(credit_cover_list))
        assign("Editor", ", ".join(credit_editor_list))

        assign("Publisher", md.publisher)
        assign("Imprint", md.imprint)
        assign("Genre", md.genres)
        assign("Web", md.web_link)
        assign("PageCount", md.page_count)
        assign("LanguageISO", md.language)
        assign("Format", md.format)
        assign("AgeRating", md.maturity_rating)
        assign("CommunityRating", md.critical_rating)
        assign("BlackAndWhite", "Yes" if md.black_and_white else None)
        assign("Manga", md.manga)
        assign("Characters", md.characters)
        assign("Teams", md.teams)
        assign("Locations", md.locations)
        assign("ScanInformation", md.scan_info)

        #  loop and add the page entries under pages node
        pages_node = root.find("Pages")
        if pages_node is not None:
            pages_node.clear()
        else:
            pages_node = ET.SubElement(root, "Pages")

        for page_dict in md.pages:
            page_node = ET.SubElement(pages_node, "Page")
            page_node.attrib = OrderedDict(sorted((k, str(v)) for k, v in page_dict.items()))

        ET.indent(root)

        # wrap it in an ElementTree instance, and save as XML
        tree = ET.ElementTree(root)
        return tree

    def convert_xml_to_metadata(self, tree: ElementTree) -> GenericMetadata:
        root = tree.getroot()

        if root.tag != "ComicInfo":
            raise Exception("Not a ComicInfo file")

        def get(name: str) -> str | None:
            tag = root.find(name)
            if tag is None:
                return None
            return tag.text

        md = GenericMetadata()

        md.series = utils.xlate(get("Series"))
        md.title = utils.xlate(get("Title"))
        md.issue = utils.xlate(get("Number"))
        md.issue_count = utils.xlate_int(get("Count"))
        md.volume = utils.xlate_int(get("Volume"))
        md.alternate_series = utils.xlate(get("AlternateSeries"))
        md.alternate_number = utils.xlate(get("AlternateNumber"))
        md.alternate_count = utils.xlate_int(get("AlternateCount"))
        md.description = utils.xlate(get("Summary"))
        md.notes = utils.xlate(get("Notes"))
        md.year = utils.xlate_int(get("Year"))
        md.month = utils.xlate_int(get("Month"))
        md.day = utils.xlate_int(get("Day"))
        md.publisher = utils.xlate(get("Publisher"))
        md.imprint = utils.xlate(get("Imprint"))
        md.genres = set(utils.split(get("Genre"), ","))
        md.web_link = utils.xlate(get("Web"))
        md.language = utils.xlate(get("LanguageISO"))
        md.format = utils.xlate(get("Format"))
        md.manga = utils.xlate(get("Manga"))
        md.characters = set(utils.split(get("Characters"), ","))
        md.teams = set(utils.split(get("Teams"), ","))
        md.locations = set(utils.split(get("Locations"), ","))
        md.page_count = utils.xlate_int(get("PageCount"))
        md.scan_info = utils.xlate(get("ScanInformation"))
        md.story_arcs = utils.split(get("StoryArc"), ",")
        md.series_groups = utils.split(get("SeriesGroup"), ",")
        md.maturity_rating = utils.xlate(get("AgeRating"))
        md.critical_rating = utils.xlate_float(get("CommunityRating"))

        tmp = utils.xlate(get("BlackAndWhite"))
        if tmp is not None and tmp.casefold() in ["yes", "true", "1"]:
            md.black_and_white = True
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
            for page in pages_node:
                p: dict[str, Any] = page.attrib
                if "Image" in p:
                    p["Image"] = int(p["Image"])
                if "DoublePage" in p:
                    p["DoublePage"] = True if p["DoublePage"].casefold() in ("yes", "true", "1") else False
                md.pages.append(cast(ImageMetadata, p))

        md.is_empty = False

        return md

    def write_to_external_file(self, filename: str, metadata: GenericMetadata, xml: bytes = b"") -> None:
        tree = self.convert_metadata_to_xml(metadata, xml)
        tree.write(filename, encoding="utf-8", xml_declaration=True)

    def read_from_external_file(self, filename: str) -> GenericMetadata:
        tree = ET.parse(filename)
        return self.convert_xml_to_metadata(tree)
