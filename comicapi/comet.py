"""A class to encapsulate CoMet data"""

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

import xml.etree.ElementTree as ET

from comicapi import utils
from comicapi.genericmetadata import GenericMetadata


class CoMet:

    writer_synonyms = ["writer", "plotter", "scripter"]
    penciller_synonyms = ["artist", "penciller", "penciler", "breakdowns"]
    inker_synonyms = ["inker", "artist", "finishes"]
    colorist_synonyms = ["colorist", "colourist", "colorer", "colourer"]
    letterer_synonyms = ["letterer"]
    cover_synonyms = ["cover", "covers", "coverartist", "cover artist"]
    editor_synonyms = ["editor"]

    def metadata_from_string(self, string):

        tree = ET.ElementTree(ET.fromstring(string))
        return self.convert_xml_to_metadata(tree)

    def string_from_metadata(self, metadata):

        header = '<?xml version="1.0" encoding="UTF-8"?>\n'

        tree = self.convert_metadata_to_xml(metadata)
        return header + ET.tostring(tree.getroot())

    def convert_metadata_to_xml(self, metadata):

        # shorthand for the metadata
        md = metadata

        # build a tree structure
        root = ET.Element("comet")
        root.attrib["xmlns:comet"] = "http://www.denvog.com/comet/"
        root.attrib["xmlns:xsi"] = "http://www.w3.org/2001/XMLSchema-instance"
        root.attrib["xsi:schemaLocation"] = "http://www.denvog.com http://www.denvog.com/comet/comet.xsd"

        # helper func
        def assign(comet_entry, md_entry):
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
            date_str = str(md.year).zfill(4)
            if md.month is not None:
                date_str += "-" + str(md.month).zfill(2)
            assign("date", date_str)

        assign("coverImage", md.cover_image)

        # loop thru credits, and build a list for each role that CoMet supports
        for credit in metadata.credits:

            if credit["role"].lower() in set(self.writer_synonyms):
                ET.SubElement(root, "writer").text = str(credit["person"])

            if credit["role"].lower() in set(self.penciller_synonyms):
                ET.SubElement(root, "penciller").text = str(credit["person"])

            if credit["role"].lower() in set(self.inker_synonyms):
                ET.SubElement(root, "inker").text = str(credit["person"])

            if credit["role"].lower() in set(self.colorist_synonyms):
                ET.SubElement(root, "colorist").text = str(credit["person"])

            if credit["role"].lower() in set(self.letterer_synonyms):
                ET.SubElement(root, "letterer").text = str(credit["person"])

            if credit["role"].lower() in set(self.cover_synonyms):
                ET.SubElement(root, "coverDesigner").text = str(credit["person"])

            if credit["role"].lower() in set(self.editor_synonyms):
                ET.SubElement(root, "editor").text = str(credit["person"])

        utils.indent(root)

        # wrap it in an ElementTree instance, and save as XML
        tree = ET.ElementTree(root)
        return tree

    def convert_xml_to_metadata(self, tree):

        root = tree.getroot()

        if root.tag != "comet":
            raise "1"

        metadata = GenericMetadata()
        md = metadata

        # Helper function
        def xlate(tag):
            node = root.find(tag)
            if node is not None:
                return node.text
            return None

        md.series = xlate("series")
        md.title = xlate("title")
        md.issue = xlate("issue")
        md.volume = xlate("volume")
        md.comments = xlate("description")
        md.publisher = xlate("publisher")
        md.language = xlate("language")
        md.format = xlate("format")
        md.page_count = xlate("pages")
        md.maturity_rating = xlate("rating")
        md.price = xlate("price")
        md.is_version_of = xlate("isVersionOf")
        md.rights = xlate("rights")
        md.identifier = xlate("identifier")
        md.last_mark = xlate("lastMark")
        md.genre = xlate("genre")  # TODO - repeatable field

        date = xlate("date")
        if date is not None:
            parts = date.split("-")
            if len(parts) > 0:
                md.year = parts[0]
            if len(parts) > 1:
                md.month = parts[1]

        md.cover_image = xlate("coverImage")

        reading_direction = xlate("readingDirection")
        if reading_direction is not None and reading_direction == "rtl":
            md.manga = "YesAndRightToLeft"

        # loop for character tags
        char_list = []
        for n in root:
            if n.tag == "character":
                char_list.append(n.text.strip())
        md.characters = utils.list_to_string(char_list)

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
                metadata.add_credit(n.text.strip(), n.tag.title())

            if n.tag == "coverDesigner":
                metadata.add_credit(n.text.strip(), "Cover")

        metadata.is_empty = False

        return metadata

    # verify that the string actually contains CoMet data in XML format
    def validate_string(self, string):
        try:
            tree = ET.ElementTree(ET.fromstring(string))
            root = tree.getroot()
            if root.tag != "comet":
                raise Exception
        except:
            return False

        return True

    def write_to_external_file(self, filename, metadata):

        tree = self.convert_metadata_to_xml(metadata)
        tree.write(filename, encoding="utf-8")

    def read_from_external_file(self, filename):

        tree = ET.parse(filename)
        return self.convert_xml_to_metadata(tree)
