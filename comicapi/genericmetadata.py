"""A class for internal metadata storage

The goal of this class is to handle ALL the data that might come from various
tagging schemes and databases, such as ComicVine or GCD.  This makes conversion
possible, however lossy it might be

"""

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

import logging
from enum import Enum
from typing import List, TypedDict

from comicapi import utils

logger = logging.getLogger(__name__)


class PageType(Enum):

    """
    These page info classes are exactly the same as the CIX scheme, since
    it's unique
    """

    FrontCover = "FrontCover"
    InnerCover = "InnerCover"
    Roundup = "Roundup"
    Story = "Story"
    Advertisement = "Advertisement"
    Editorial = "Editorial"
    Letters = "Letters"
    Preview = "Preview"
    BackCover = "BackCover"
    Other = "Other"
    Deleted = "Deleted"


class ImageMetadata(TypedDict, total=False):
    Type: PageType
    Bookmark: str
    DoublePage: bool
    Image: int
    ImageSize: str
    ImageHeight: str
    ImageWidth: str


class CreditMetadata(TypedDict):
    person: str
    role: str
    primary: bool


class GenericMetadata:
    writer_synonyms = ["writer", "plotter", "scripter"]
    penciller_synonyms = ["artist", "penciller", "penciler", "breakdowns"]
    inker_synonyms = ["inker", "artist", "finishes"]
    colorist_synonyms = ["colorist", "colourist", "colorer", "colourer"]
    letterer_synonyms = ["letterer"]
    cover_synonyms = ["cover", "covers", "coverartist", "cover artist"]
    editor_synonyms = ["editor"]

    def __init__(self):

        self.is_empty = True
        self.tag_origin = None

        self.series = None
        self.issue = None
        self.title = None
        self.publisher = None
        self.month = None
        self.year = None
        self.day = None
        self.issue_count = None
        self.volume = None
        self.genre = None
        self.language = None  # 2 letter iso code
        self.comments = None  # use same way as Summary in CIX

        self.volume_count = None
        self.critical_rating = None
        self.country = None

        self.alternate_series = None
        self.alternate_number = None
        self.alternate_count = None
        self.imprint = None
        self.notes = None
        self.web_link = None
        self.format = None
        self.manga = None
        self.black_and_white = None
        self.page_count = None
        self.maturity_rating = None

        self.story_arc = None
        self.series_group = None
        self.scan_info = None

        self.characters = None
        self.teams = None
        self.locations = None

        self.credits: List[CreditMetadata] = []
        self.tags: List[str] = []
        self.pages: List[ImageMetadata] = []

        # Some CoMet-only items
        self.price = None
        self.is_version_of = None
        self.rights = None
        self.identifier = None
        self.last_mark = None
        self.cover_image = None

    def overlay(self, new_md):
        """Overlay a metadata object on this one

        That is, when the new object has non-None values, over-write them
        to this one.
        """

        def assign(cur, new):
            if new is not None:
                if isinstance(new, str) and len(new) == 0:
                    setattr(self, cur, None)
                else:
                    setattr(self, cur, new)

        new_md: GenericMetadata
        if not new_md.is_empty:
            self.is_empty = False

        assign("series", new_md.series)
        assign("issue", new_md.issue)
        assign("issue_count", new_md.issue_count)
        assign("title", new_md.title)
        assign("publisher", new_md.publisher)
        assign("day", new_md.day)
        assign("month", new_md.month)
        assign("year", new_md.year)
        assign("volume", new_md.volume)
        assign("volume_count", new_md.volume_count)
        assign("genre", new_md.genre)
        assign("language", new_md.language)
        assign("country", new_md.country)
        assign("critical_rating", new_md.critical_rating)
        assign("alternate_series", new_md.alternate_series)
        assign("alternate_number", new_md.alternate_number)
        assign("alternate_count", new_md.alternate_count)
        assign("imprint", new_md.imprint)
        assign("web_link", new_md.web_link)
        assign("format", new_md.format)
        assign("manga", new_md.manga)
        assign("black_and_white", new_md.black_and_white)
        assign("maturity_rating", new_md.maturity_rating)
        assign("story_arc", new_md.story_arc)
        assign("series_group", new_md.series_group)
        assign("scan_info", new_md.scan_info)
        assign("characters", new_md.characters)
        assign("teams", new_md.teams)
        assign("locations", new_md.locations)
        assign("comments", new_md.comments)
        assign("notes", new_md.notes)

        assign("price", new_md.price)
        assign("is_version_of", new_md.is_version_of)
        assign("rights", new_md.rights)
        assign("identifier", new_md.identifier)
        assign("last_mark", new_md.last_mark)

        self.overlay_credits(new_md.credits)
        # TODO

        # not sure if the tags and pages should broken down, or treated
        # as whole lists....

        # For now, go the easy route, where any overlay
        # value wipes out the whole list
        if len(new_md.tags) > 0:
            assign("tags", new_md.tags)

        if len(new_md.pages) > 0:
            assign("pages", new_md.pages)

    def overlay_credits(self, new_credits):
        for c in new_credits:
            primary = bool("primary" in c and c["primary"])

            # Remove credit role if person is blank
            if c["person"] == "":
                for r in reversed(self.credits):
                    if r["role"].lower() == c["role"].lower():
                        self.credits.remove(r)
            # otherwise, add it!
            else:
                self.add_credit(c["person"], c["role"], primary)

    def set_default_page_list(self, count):
        # generate a default page list, with the first page marked as the cover
        for i in range(count):
            page_dict = ImageMetadata(Image=i)
            if i == 0:
                page_dict["Type"] = PageType.FrontCover
            self.pages.append(page_dict)

    def get_archive_page_index(self, pagenum):
        # convert the displayed page number to the page index of the file in
        # the archive
        if pagenum < len(self.pages):
            return int(self.pages[pagenum]["Image"])

        return 0

    def get_cover_page_index_list(self):
        # return a list of archive page indices of cover pages
        coverlist = []
        for p in self.pages:
            if "Type" in p and p["Type"] == PageType.FrontCover:
                coverlist.append(int(p["Image"]))

        if len(coverlist) == 0:
            coverlist.append(0)

        return coverlist

    def add_credit(self, person, role, primary=False):

        credit: CreditMetadata = {"person": person, "role": role, "primary": primary}

        # look to see if it's not already there...
        found = False
        for c in self.credits:
            if c["person"].lower() == person.lower() and c["role"].lower() == role.lower():
                # no need to add it. just adjust the "primary" flag as needed
                c["primary"] = primary
                found = True
                break

        if not found:
            self.credits.append(credit)

    def get_primary_credit(self, role):
        primary = ""
        for credit in self.credits:
            if (primary == "" and credit["role"].lower() == role.lower()) or (
                credit["role"].lower() == role.lower() and credit["primary"]
            ):
                primary = credit["person"]
        return primary

    def __str__(self):
        vals = []
        if self.is_empty:
            return "No metadata"

        def add_string(tag, val):
            if val is not None and str(val) != "":
                vals.append((tag, val))

        def add_attr_string(tag):
            add_string(tag, getattr(self, tag))

        add_attr_string("series")
        add_attr_string("issue")
        add_attr_string("issue_count")
        add_attr_string("title")
        add_attr_string("publisher")
        add_attr_string("year")
        add_attr_string("month")
        add_attr_string("day")
        add_attr_string("volume")
        add_attr_string("volume_count")
        add_attr_string("genre")
        add_attr_string("language")
        add_attr_string("country")
        add_attr_string("critical_rating")
        add_attr_string("alternate_series")
        add_attr_string("alternate_number")
        add_attr_string("alternate_count")
        add_attr_string("imprint")
        add_attr_string("web_link")
        add_attr_string("format")
        add_attr_string("manga")

        add_attr_string("price")
        add_attr_string("is_version_of")
        add_attr_string("rights")
        add_attr_string("identifier")
        add_attr_string("last_mark")

        if self.black_and_white:
            add_attr_string("black_and_white")
        add_attr_string("maturity_rating")
        add_attr_string("story_arc")
        add_attr_string("series_group")
        add_attr_string("scan_info")
        add_attr_string("characters")
        add_attr_string("teams")
        add_attr_string("locations")
        add_attr_string("comments")
        add_attr_string("notes")

        add_string("tags", utils.list_to_string(self.tags))

        for c in self.credits:
            primary = ""
            if "primary" in c and c["primary"]:
                primary = " [P]"
            add_string("credit", c["role"] + ": " + c["person"] + primary)

        # find the longest field name
        flen = 0
        for i in vals:
            flen = max(flen, len(i[0]))
        flen += 1

        # format the data nicely
        outstr = ""
        fmt_str = "{0: <" + str(flen) + "} {1}\n"
        for i in vals:
            outstr += fmt_str.format(i[0] + ":", i[1])

        return outstr


md_test = GenericMetadata()

md_test.is_empty = False
md_test.tag_origin = None
md_test.series = "Cory Doctorow's Futuristic Tales of the Here and Now"
md_test.issue = "1"
md_test.title = "Anda's Game"
md_test.publisher = "IDW Publishing"
md_test.month = 10
md_test.year = 2007
md_test.day = 1
md_test.issue_count = 6
md_test.volume = 1
md_test.genre = "Sci-Fi"
md_test.language = "en"
md_test.comments = (
    "For 12-year-old Anda, getting paid real money to kill the characters of players who were cheating in her favorite online "
    "computer game was a win-win situation. Until she found out who was paying her, and what those characters meant to the "
    "livelihood of children around the world."
)
md_test.volume_count = None
md_test.critical_rating = None
md_test.country = None
md_test.alternate_series = "Tales"
md_test.alternate_number = "2"
md_test.alternate_count = 7
md_test.imprint = "craphound.com"
md_test.notes = "Tagged with ComicTagger 1.3.2a5 using info from Comic Vine on 2022-04-16 15:52:26. [Issue ID 140529]"
md_test.web_link = "https://comicvine.gamespot.com/cory-doctorows-futuristic-tales-of-the-here-and-no/4000-140529/"
md_test.format = "Series"
md_test.manga = "No"
md_test.black_and_white = None
md_test.page_count = 24
md_test.maturity_rating = "Everyone 10+"
md_test.story_arc = "Here and Now"
md_test.series_group = "Futuristic Tales"
md_test.scan_info = "(CC BY-NC-SA 3.0)"
md_test.characters = "Anda"
md_test.teams = "Fahrenheit"
md_test.locations = "lonely  cottage "
md_test.credits = [
    {"person": "Dara Naraghi", "role": "Writer"},
    {"person": "Esteve Polls", "role": "Penciller"},
    {"person": "Esteve Polls", "role": "Inker"},
    {"person": "Neil Uyetake", "role": "Letterer"},
    {"person": "Sam Kieth", "role": "Cover"},
    {"person": "Ted Adams", "role": "Editor"},
]
md_test.tags = []
md_test.pages = [
    {"Image": "0", "ImageHeight": "1280", "ImageSize": "195977", "ImageWidth": "800", "Type": "FrontCover"},
    {"Image": "1", "ImageHeight": "2039", "ImageSize": "611993", "ImageWidth": "1327"},
    {"Image": "2", "ImageHeight": "2039", "ImageSize": "783726", "ImageWidth": "1327"},
    {"Image": "3", "ImageHeight": "2039", "ImageSize": "679584", "ImageWidth": "1327"},
    {"Image": "4", "ImageHeight": "2039", "ImageSize": "788179", "ImageWidth": "1327"},
    {"Image": "5", "ImageHeight": "2039", "ImageSize": "864433", "ImageWidth": "1327"},
    {"Image": "6", "ImageHeight": "2039", "ImageSize": "765606", "ImageWidth": "1327"},
    {"Image": "7", "ImageHeight": "2039", "ImageSize": "876427", "ImageWidth": "1327"},
    {"Image": "8", "ImageHeight": "2039", "ImageSize": "852622", "ImageWidth": "1327"},
    {"Image": "9", "ImageHeight": "2039", "ImageSize": "800205", "ImageWidth": "1327"},
    {"Image": "10", "ImageHeight": "2039", "ImageSize": "746243", "ImageWidth": "1326"},
    {"Image": "11", "ImageHeight": "2039", "ImageSize": "718062", "ImageWidth": "1327"},
    {"Image": "12", "ImageHeight": "2039", "ImageSize": "532179", "ImageWidth": "1326"},
    {"Image": "13", "ImageHeight": "2039", "ImageSize": "686708", "ImageWidth": "1327"},
    {"Image": "14", "ImageHeight": "2039", "ImageSize": "641907", "ImageWidth": "1327"},
    {"Image": "15", "ImageHeight": "2039", "ImageSize": "805388", "ImageWidth": "1327"},
    {"Image": "16", "ImageHeight": "2039", "ImageSize": "668927", "ImageWidth": "1326"},
    {"Image": "17", "ImageHeight": "2039", "ImageSize": "710605", "ImageWidth": "1327"},
    {"Image": "18", "ImageHeight": "2039", "ImageSize": "761398", "ImageWidth": "1326"},
    {"Image": "19", "ImageHeight": "2039", "ImageSize": "743807", "ImageWidth": "1327"},
    {"Image": "20", "ImageHeight": "2039", "ImageSize": "552911", "ImageWidth": "1326"},
    {"Image": "21", "ImageHeight": "2039", "ImageSize": "556827", "ImageWidth": "1327"},
    {"Image": "22", "ImageHeight": "2039", "ImageSize": "675078", "ImageWidth": "1326"},
    {
        "Bookmark": "Interview",
        "Image": "23",
        "ImageHeight": "2032",
        "ImageSize": "800965",
        "ImageWidth": "1338",
        "Type": "Letters",
    },
]
md_test.price = None
md_test.is_version_of = None
md_test.rights = None
md_test.identifier = None
md_test.last_mark = None
md_test.cover_image = None
