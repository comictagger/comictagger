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
import xml.etree.ElementTree as ET
from typing import Any

from comicapi import utils
from comicapi.genericmetadata import GenericMetadata

logger = logging.getLogger(__name__)


class CoMet:
    writer_synonyms = ["writer", "plotter", "scripter"]
    penciller_synonyms = ["artist", "penciller", "penciler", "breakdowns"]
    inker_synonyms = ["inker", "artist", "finishes"]
    colorist_synonyms = ["colorist", "colourist", "colorer", "colourer"]
    letterer_synonyms = ["letterer"]
    cover_synonyms = ["cover", "covers", "coverartist", "cover artist"]
    editor_synonyms = ["editor"]

    def metadata_from_string(self, string: str) -> GenericMetadata:
        tree = ET.ElementTree(ET.fromstring(string))
        return self.convert_xml_to_metadata(tree)

    def string_from_metadata(self, metadata: GenericMetadata) -> str:
        tree = self.convert_metadata_to_xml(metadata)
        return str(ET.tostring(tree.getroot(), encoding="utf-8", xml_declaration=True).decode("utf-8"))

    def convert_metadata_to_xml(self, metadata: GenericMetadata) -> ET.ElementTree:
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
        assign("description", md.comments)
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
        assign("genre", md.genre)  # TODO repeatable

        if md.characters is not None:
            char_list = [c.strip() for c in md.characters.split(",")]
            for c in char_list:
                assign("character", c)

        if md.manga is not None and md.manga == "YesAndRightToLeft":
            assign("readingDirection", "rtl")

        if md.year is not None:
            date_str = f"{md.year:04}"
            if md.month is not None:
                date_str += f"-{md.month:02}"
            assign("date", date_str)

        assign("coverImage", md.cover_image)

        # loop thru credits, and build a list for each role that CoMet supports
        for credit in metadata.credits:
            if credit["role"].casefold() in set(self.writer_synonyms):
                ET.SubElement(root, "writer").text = str(credit["person"])

            if credit["role"].casefold() in set(self.penciller_synonyms):
                ET.SubElement(root, "penciller").text = str(credit["person"])

            if credit["role"].casefold() in set(self.inker_synonyms):
                ET.SubElement(root, "inker").text = str(credit["person"])

            if credit["role"].casefold() in set(self.colorist_synonyms):
                ET.SubElement(root, "colorist").text = str(credit["person"])

            if credit["role"].casefold() in set(self.letterer_synonyms):
                ET.SubElement(root, "letterer").text = str(credit["person"])

            if credit["role"].casefold() in set(self.cover_synonyms):
                ET.SubElement(root, "coverDesigner").text = str(credit["person"])

            if credit["role"].casefold() in set(self.editor_synonyms):
                ET.SubElement(root, "editor").text = str(credit["person"])

        ET.indent(root)

        # wrap it in an ElementTree instance, and save as XML
        tree = ET.ElementTree(root)
        return tree

    def convert_xml_to_metadata(self, tree: ET.ElementTree) -> GenericMetadata:
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
        md.volume = utils.xlate(get("volume"), True)
        md.comments = utils.xlate(get("description"))
        md.publisher = utils.xlate(get("publisher"))
        md.language = utils.xlate(get("language"))
        md.format = utils.xlate(get("format"))
        md.page_count = utils.xlate(get("pages"), True)
        md.maturity_rating = utils.xlate(get("rating"))
        md.price = utils.xlate(get("price"), is_float=True)
        md.is_version_of = utils.xlate(get("isVersionOf"))
        md.rights = utils.xlate(get("rights"))
        md.identifier = utils.xlate(get("identifier"))
        md.last_mark = utils.xlate(get("lastMark"))
        md.genre = utils.xlate(get("genre"))  # TODO - repeatable field

        _, md.month, md.year = utils.parse_date_str(utils.xlate(get("date")))

        md.cover_image = utils.xlate(get("coverImage"))

        reading_direction = utils.xlate(get("readingDirection"))
        if reading_direction is not None and reading_direction == "rtl":
            md.manga = "YesAndRightToLeft"

        # loop for character tags
        char_list = []
        for n in root:
            if n.tag == "character":
                char_list.append((n.text or "").strip())
        md.characters = ", ".join(char_list)

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
    def validate_string(self, string: str) -> bool:
        try:
            tree = ET.ElementTree(ET.fromstring(string))
            root = tree.getroot()
            if root.tag != "comet":
                return False
        except ET.ParseError:
            return False

        return True

    def write_to_external_file(self, filename: str, metadata: GenericMetadata) -> None:
        tree = self.convert_metadata_to_xml(metadata)
        tree.write(filename, encoding="utf-8")

    def read_from_external_file(self, filename: str) -> GenericMetadata:
        tree = ET.parse(filename)
        return self.convert_xml_to_metadata(tree)
