"""A class for internal metadata storage

The goal of this class is to handle ALL the data that might come from various
tagging schemes and databases, such as ComicVine or GCD.  This makes conversion
possible, however lossy it might be

"""
# Copyright 2012-2014 Anthony Beville
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

import copy
import dataclasses
import logging
from typing import Any, TypedDict

from comicapi import utils

logger = logging.getLogger(__name__)


class PageType:

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
    Type: str
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


@dataclasses.dataclass
class GenericMetadata:
    writer_synonyms = ["writer", "plotter", "scripter"]
    penciller_synonyms = ["artist", "penciller", "penciler", "breakdowns"]
    inker_synonyms = ["inker", "artist", "finishes"]
    colorist_synonyms = ["colorist", "colourist", "colorer", "colourer"]
    letterer_synonyms = ["letterer"]
    cover_synonyms = ["cover", "covers", "coverartist", "cover artist"]
    editor_synonyms = ["editor"]

    is_empty: bool = True
    tag_origin: str | None = None

    series: str | None = None
    issue: str | None = None
    title: str | None = None
    publisher: str | None = None
    month: int | None = None
    year: int | None = None
    day: int | None = None
    issue_count: int | None = None
    volume: int | None = None
    genre: str | None = None
    language: str | None = None  # 2 letter iso code
    comments: str | None = None  # use same way as Summary in CIX

    volume_count: int | None = None
    critical_rating: float | None = None  # rating in cbl; CommunityRating in CIX
    country: str | None = None

    alternate_series: str | None = None
    alternate_number: str | None = None
    alternate_count: int | None = None
    imprint: str | None = None
    notes: str | None = None
    web_link: str | None = None
    format: str | None = None
    manga: str | None = None
    black_and_white: bool | None = None
    page_count: int | None = None
    maturity_rating: str | None = None

    story_arc: str | None = None
    series_group: str | None = None
    scan_info: str | None = None

    characters: str | None = None
    teams: str | None = None
    locations: str | None = None

    credits: list[CreditMetadata] = dataclasses.field(default_factory=list)
    tags: set[str] = dataclasses.field(default_factory=set)
    pages: list[ImageMetadata] = dataclasses.field(default_factory=list)

    # Some CoMet-only items
    price: str | None = None
    is_version_of: str | None = None
    rights: str | None = None
    identifier: str | None = None
    last_mark: str | None = None
    cover_image: str | None = None

    def __post_init__(self):
        for key, value in self.__dict__.items():
            if value and key != "is_empty":
                self.is_empty = False
                break

    def copy(self) -> GenericMetadata:
        return copy.deepcopy(self)

    def replace(self, /, **kwargs: Any) -> GenericMetadata:
        tmp = self.copy()
        tmp.__dict__.update(kwargs)
        return tmp

    def overlay(self, new_md: GenericMetadata) -> None:
        """Overlay a metadata object on this one

        That is, when the new object has non-None values, over-write them
        to this one.
        """

        def assign(cur: str, new: Any) -> None:
            if new is not None:
                if isinstance(new, str) and len(new) == 0:
                    setattr(self, cur, None)
                else:
                    setattr(self, cur, new)

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

    def overlay_credits(self, new_credits: list[CreditMetadata]) -> None:
        for c in new_credits:
            primary = bool("primary" in c and c["primary"])

            # Remove credit role if person is blank
            if c["person"] == "":
                for r in reversed(self.credits):
                    if r["role"].casefold() == c["role"].casefold():
                        self.credits.remove(r)
            # otherwise, add it!
            else:
                self.add_credit(c["person"], c["role"], primary)

    def set_default_page_list(self, count: int) -> None:
        # generate a default page list, with the first page marked as the cover
        for i in range(count):
            page_dict = ImageMetadata(Image=i)
            if i == 0:
                page_dict["Type"] = PageType.FrontCover
            self.pages.append(page_dict)

    def get_archive_page_index(self, pagenum: int) -> int:
        # convert the displayed page number to the page index of the file in the archive
        if pagenum < len(self.pages):
            return int(self.pages[pagenum]["Image"])

        return 0

    def get_cover_page_index_list(self) -> list[int]:
        # return a list of archive page indices of cover pages
        coverlist = []
        for p in self.pages:
            if "Type" in p and p["Type"] == PageType.FrontCover:
                coverlist.append(int(p["Image"]))

        if len(coverlist) == 0:
            coverlist.append(0)

        return coverlist

    def add_credit(self, person: str, role: str, primary: bool = False) -> None:

        credit = CreditMetadata(person=person, role=role, primary=primary)

        # look to see if it's not already there...
        found = False
        for c in self.credits:
            if c["person"].casefold() == person.casefold() and c["role"].casefold() == role.casefold():
                # no need to add it. just adjust the "primary" flag as needed
                c["primary"] = primary
                found = True
                break

        if not found:
            self.credits.append(credit)

    def get_primary_credit(self, role: str) -> str:
        primary = ""
        for credit in self.credits:
            if (primary == "" and credit["role"].casefold() == role.casefold()) or (
                credit["role"].casefold() == role.casefold() and credit["primary"]
            ):
                primary = credit["person"]
        return primary

    def __str__(self) -> str:
        vals: list[tuple[str, Any]] = []
        if self.is_empty:
            return "No metadata"

        def add_string(tag: str, val: Any) -> None:
            if val is not None and str(val) != "":
                vals.append((tag, val))

        def add_attr_string(tag: str) -> None:
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

        add_string("tags", ", ".join(self.tags))

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

    def fix_publisher(self) -> None:
        if self.publisher is None:
            return
        if self.imprint is None:
            self.imprint = ""

        imprint, publisher = utils.get_publisher(self.publisher)

        self.publisher = publisher

        if self.imprint.casefold() in publisher.casefold():
            self.imprint = None

        if self.imprint is None or self.imprint == "":
            self.imprint = imprint
        elif self.imprint.casefold() in imprint.casefold():
            self.imprint = imprint


md_test: GenericMetadata = GenericMetadata(
    is_empty=False,
    tag_origin=None,
    series="Cory Doctorow's Futuristic Tales of the Here and Now",
    issue="1",
    title="Anda's Game",
    publisher="IDW Publishing",
    month=10,
    year=2007,
    day=1,
    issue_count=6,
    volume=1,
    genre="Sci-Fi",
    language="en",
    comments=(
        "For 12-year-old Anda, getting paid real money to kill the characters of players who were cheating"
        " in her favorite online computer game was a win-win situation. Until she found out who was paying her,"
        " and what those characters meant to the livelihood of children around the world."
    ),
    volume_count=None,
    critical_rating=3.0,
    country=None,
    alternate_series="Tales",
    alternate_number="2",
    alternate_count=7,
    imprint="craphound.com",
    notes="Tagged with ComicTagger 1.3.2a5 using info from Comic Vine on 2022-04-16 15:52:26. [Issue ID 140529]",
    web_link="https://comicvine.gamespot.com/cory-doctorows-futuristic-tales-of-the-here-and-no/4000-140529/",
    format="Series",
    manga="No",
    black_and_white=None,
    page_count=24,
    maturity_rating="Everyone 10+",
    story_arc="Here and Now",
    series_group="Futuristic Tales",
    scan_info="(CC BY-NC-SA 3.0)",
    characters="Anda",
    teams="Fahrenheit",
    locations="lonely  cottage ",
    credits=[
        CreditMetadata(primary=False, person="Dara Naraghi", role="Writer"),
        CreditMetadata(primary=False, person="Esteve Polls", role="Penciller"),
        CreditMetadata(primary=False, person="Esteve Polls", role="Inker"),
        CreditMetadata(primary=False, person="Neil Uyetake", role="Letterer"),
        CreditMetadata(primary=False, person="Sam Kieth", role="Cover"),
        CreditMetadata(primary=False, person="Ted Adams", role="Editor"),
    ],
    tags=set(),
    pages=[
        ImageMetadata(Image=0, ImageHeight="1280", ImageSize="195977", ImageWidth="800", Type=PageType.FrontCover),
        ImageMetadata(Image=1, ImageHeight="2039", ImageSize="611993", ImageWidth="1327"),
        ImageMetadata(Image=2, ImageHeight="2039", ImageSize="783726", ImageWidth="1327"),
        ImageMetadata(Image=3, ImageHeight="2039", ImageSize="679584", ImageWidth="1327"),
        ImageMetadata(Image=4, ImageHeight="2039", ImageSize="788179", ImageWidth="1327"),
        ImageMetadata(Image=5, ImageHeight="2039", ImageSize="864433", ImageWidth="1327"),
        ImageMetadata(Image=6, ImageHeight="2039", ImageSize="765606", ImageWidth="1327"),
        ImageMetadata(Image=7, ImageHeight="2039", ImageSize="876427", ImageWidth="1327"),
        ImageMetadata(Image=8, ImageHeight="2039", ImageSize="852622", ImageWidth="1327"),
        ImageMetadata(Image=9, ImageHeight="2039", ImageSize="800205", ImageWidth="1327"),
        ImageMetadata(Image=10, ImageHeight="2039", ImageSize="746243", ImageWidth="1326"),
        ImageMetadata(Image=11, ImageHeight="2039", ImageSize="718062", ImageWidth="1327"),
        ImageMetadata(Image=12, ImageHeight="2039", ImageSize="532179", ImageWidth="1326"),
        ImageMetadata(Image=13, ImageHeight="2039", ImageSize="686708", ImageWidth="1327"),
        ImageMetadata(Image=14, ImageHeight="2039", ImageSize="641907", ImageWidth="1327"),
        ImageMetadata(Image=15, ImageHeight="2039", ImageSize="805388", ImageWidth="1327"),
        ImageMetadata(Image=16, ImageHeight="2039", ImageSize="668927", ImageWidth="1326"),
        ImageMetadata(Image=17, ImageHeight="2039", ImageSize="710605", ImageWidth="1327"),
        ImageMetadata(Image=18, ImageHeight="2039", ImageSize="761398", ImageWidth="1326"),
        ImageMetadata(Image=19, ImageHeight="2039", ImageSize="743807", ImageWidth="1327"),
        ImageMetadata(Image=20, ImageHeight="2039", ImageSize="552911", ImageWidth="1326"),
        ImageMetadata(Image=21, ImageHeight="2039", ImageSize="556827", ImageWidth="1327"),
        ImageMetadata(Image=22, ImageHeight="2039", ImageSize="675078", ImageWidth="1326"),
        ImageMetadata(
            Bookmark="Interview",
            Image=23,
            ImageHeight="2032",
            ImageSize="800965",
            ImageWidth="1338",
            Type=PageType.Letters,
        ),
    ],
    price=None,
    is_version_of=None,
    rights=None,
    identifier=None,
    last_mark=None,
    cover_image=None,
)
