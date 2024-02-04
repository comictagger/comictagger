"""A class for internal metadata storage

The goal of this class is to handle ALL the data that might come from various
tagging schemes and databases, such as ComicVine or GCD.  This makes conversion
possible, however lossy it might be

"""

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

import copy
import dataclasses
import logging
import sys
from collections.abc import Sequence
from enum import Enum, auto
from typing import TYPE_CHECKING, Any, TypedDict, Union

from typing_extensions import NamedTuple, Required

from comicapi import utils
from comicapi._url import Url, parse_url
from comicapi.utils import norm_fold

if TYPE_CHECKING:
    Union

logger = logging.getLogger(__name__)


class __remove(Enum):
    REMOVE = auto()


REMOVE = __remove.REMOVE


if sys.version_info < (3, 11):

    class StrEnum(str, Enum):
        """
        Enum where members are also (and must be) strings
        """

        def __new__(cls, *values: Any) -> Any:
            "values must already be of type `str`"
            if len(values) > 3:
                raise TypeError(f"too many arguments for str(): {values!r}")
            if len(values) == 1:
                # it must be a string
                if not isinstance(values[0], str):
                    raise TypeError(f"{values[0]!r} is not a string")
            if len(values) >= 2:
                # check that encoding argument is a string
                if not isinstance(values[1], str):
                    raise TypeError(f"encoding must be a string, not {values[1]!r}")
            if len(values) == 3:
                # check that errors argument is a string
                if not isinstance(values[2], str):
                    raise TypeError("errors must be a string, not %r" % (values[2]))
            value = str(*values)
            member = str.__new__(cls, value)
            member._value_ = value
            return member

        @staticmethod
        def _generate_next_value_(name: str, start: int, count: int, last_values: Any) -> str:
            """
            Return the lower-cased version of the member name.
            """
            return name.lower()

else:
    from enum import StrEnum


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
    filename: str
    type: str
    bookmark: str
    double_page: bool
    image_index: Required[int]
    size: str
    height: str
    width: str


class Credit(TypedDict):
    person: str
    role: str
    primary: bool


@dataclasses.dataclass
class ComicSeries:
    id: str
    name: str
    aliases: set[str]
    count_of_issues: int | None
    count_of_volumes: int | None
    description: str
    image_url: str
    publisher: str
    start_year: int | None
    format: str | None

    def copy(self) -> ComicSeries:
        return copy.deepcopy(self)


class TagOrigin(NamedTuple):
    id: str
    name: str


class OverlayMode(StrEnum):
    overlay = auto()
    add_missing = auto()
    combine = auto()


@dataclasses.dataclass
class GenericMetadata:
    writer_synonyms = ("writer", "plotter", "scripter", "script")
    penciller_synonyms = ("artist", "penciller", "penciler", "breakdowns", "pencils", "painting")
    inker_synonyms = ("inker", "artist", "finishes", "inks", "painting")
    colorist_synonyms = ("colorist", "colourist", "colorer", "colourer", "colors", "painting")
    letterer_synonyms = ("letterer", "letters")
    cover_synonyms = ("cover", "covers", "coverartist", "cover artist")
    editor_synonyms = ("editor", "edits", "editing")
    translator_synonyms = ("translator", "translation")

    is_empty: bool = True
    tag_origin: TagOrigin | None = None
    issue_id: str | None = None
    series_id: str | None = None

    series: str | None = None
    series_aliases: set[str] = dataclasses.field(default_factory=set)
    issue: str | None = None
    issue_count: int | None = None
    title: str | None = None
    title_aliases: set[str] = dataclasses.field(default_factory=set)
    volume: int | None = None
    volume_count: int | None = None
    genres: set[str] = dataclasses.field(default_factory=set)
    description: str | None = None  # use same way as Summary in CIX
    notes: str | None = None

    alternate_series: str | None = None
    alternate_number: str | None = None
    alternate_count: int | None = None
    story_arcs: list[str] = dataclasses.field(default_factory=list)
    series_groups: list[str] = dataclasses.field(default_factory=list)

    publisher: str | None = None
    imprint: str | None = None
    day: int | None = None
    month: int | None = None
    year: int | None = None
    language: str | None = None  # 2 letter iso code
    country: str | None = None
    web_links: list[Url] = dataclasses.field(default_factory=list)
    format: str | None = None
    manga: str | None = None
    black_and_white: bool | None = None
    maturity_rating: str | None = None
    critical_rating: float | None = None  # rating in CBL; CommunityRating in CIX
    scan_info: str | None = None

    tags: set[str] = dataclasses.field(default_factory=set)
    pages: list[ImageMetadata] = dataclasses.field(default_factory=list)
    page_count: int | None = None

    characters: set[str] = dataclasses.field(default_factory=set)
    teams: set[str] = dataclasses.field(default_factory=set)
    locations: set[str] = dataclasses.field(default_factory=set)
    credits: list[Credit] = dataclasses.field(default_factory=list)

    # Some CoMet-only items
    price: float | None = None
    is_version_of: str | None = None
    rights: str | None = None
    identifier: str | None = None
    last_mark: str | None = None

    # urls to cover image, not generally part of the metadata
    _cover_image: str | None = None
    _alternate_images: list[str] = dataclasses.field(default_factory=list)

    def __post_init__(self) -> None:
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

    def get_clean_metadata(self, *attributes: str) -> GenericMetadata:
        new_md = GenericMetadata()
        for attr in sorted(attributes):
            if "." in attr:
                lst, _, name = attr.partition(".")
                old_value = getattr(self, lst)
                new_value = getattr(new_md, lst)
                if old_value:
                    if not new_value:
                        for x in old_value:
                            new_value.append(x.__class__())
                    for i, x in enumerate(old_value):
                        if isinstance(x, dict):
                            if name in x:
                                new_value[i][name] = x[name]
                        else:
                            setattr(new_value[i], name, getattr(x, name))

            else:
                old_value = getattr(self, attr)
                if isinstance(old_value, list):
                    continue
                setattr(new_md, attr, old_value)

        new_md.__post_init__()
        return new_md

    def credit_dedupe(self, cur: list[Credit], new: list[Credit]) -> list[Credit]:
        if len(new) == 0:
            return cur
        if len(cur) == 0:
            return new

        # Create dict for deduplication
        new_dict: dict[str, Credit] = {f"{norm_fold(n['person'])}_{n['role'].casefold()}": n for n in new}
        cur_dict: dict[str, Credit] = {f"{norm_fold(c['person'])}_{c['role'].casefold()}": c for c in cur}

        # Any duplicates use the 'new' value
        cur_dict.update(new_dict)
        return list(cur_dict.values())

    def assign_dedupe(self, new: list[str] | set[str], cur: list[str] | set[str]) -> list[str] | set[str]:
        """Dedupes normalised (NFKD), casefolded values using 'new' values on collisions"""
        if len(new) == 0:
            return cur
        if len(cur) == 0:
            return new

        # Create dict values for deduplication
        new_dict: dict[str, str] = {norm_fold(n): n for n in new}
        cur_dict: dict[str, str] = {norm_fold(c): c for c in cur}

        if isinstance(cur, list):
            cur_dict.update(new_dict)
            return list(cur_dict.values())

        if isinstance(cur, set):
            cur_dict.update(new_dict)
            return set(cur_dict.values())

        # All else fails
        return cur

    def assign_overlay(self, cur: Any, new: Any) -> Any:
        """Overlay - When the 'new' object has non-None values, overwrite 'cur'(rent) with 'new'."""
        if new is None:
            return cur
        if isinstance(new, (list, set)) and len(new) == 0:
            return cur
        else:
            return new

    def assign_add_missing(self, cur: Any, new: Any) -> Any:
        """Add Missing - Any 'cur(rent)' values that are None or an empty list/set, add 'new' non-None values"""
        if new is None:
            return cur
        if cur is None:
            return new
        elif isinstance(cur, (list, set)) and len(cur) == 0:
            return new
        else:
            return cur

    def assign_combine(self, cur: Any, new: Any) -> Any:
        """Combine - Combine lists and sets (checking for dupes). All non-None values from new replace cur(rent)"""
        if new is None:
            return cur
        if isinstance(new, (list, set)) and isinstance(cur, (list, set)):
            # Check for weblinks (Url is a tuple)
            if len(new) > 0 and isinstance(new, list) and isinstance(new[0], Url):
                return list(set(new).union(cur))
            return self.assign_dedupe(new, cur)
        else:
            return new

    def overlay(self, new_md: GenericMetadata, mode: OverlayMode = OverlayMode.overlay) -> None:
        """Overlay a new metadata object on this one"""

        assign_funcs = {
            OverlayMode.overlay: self.assign_overlay,
            OverlayMode.add_missing: self.assign_add_missing,
            OverlayMode.combine: self.assign_combine,
        }

        def assign(cur: Any, new: Any) -> Any:
            if new is REMOVE:
                if isinstance(cur, (list, set)):
                    cur.clear()
                    return cur
                else:
                    return None

            assign_func = assign_funcs.get(mode, self.assign_overlay)
            return assign_func(cur, new)

        if not new_md.is_empty:
            self.is_empty = False

        self.tag_origin = assign(self.tag_origin, new_md.tag_origin)  # TODO use and purpose now?
        self.issue_id = assign(self.issue_id, new_md.issue_id)
        self.series_id = assign(self.series_id, new_md.series_id)

        self.series = assign(self.series, new_md.series)
        self.series_aliases = assign(self.series_aliases, new_md.series_aliases)
        self.issue = assign(self.issue, new_md.issue)
        self.issue_count = assign(self.issue_count, new_md.issue_count)
        self.title = assign(self.title, new_md.title)
        self.title_aliases = assign(self.title_aliases, new_md.title_aliases)
        self.volume = assign(self.volume, new_md.volume)
        self.volume_count = assign(self.volume_count, new_md.volume_count)
        self.genres = assign(self.genres, new_md.genres)
        self.description = assign(self.description, new_md.description)
        self.notes = assign(self.notes, new_md.notes)

        self.alternate_series = assign(self.alternate_series, new_md.alternate_series)
        self.alternate_number = assign(self.alternate_number, new_md.alternate_number)
        self.alternate_count = assign(self.alternate_count, new_md.alternate_count)
        self.story_arcs = assign(self.story_arcs, new_md.story_arcs)
        self.series_groups = assign(self.series_groups, new_md.series_groups)

        self.publisher = assign(self.publisher, new_md.publisher)
        self.imprint = assign(self.imprint, new_md.imprint)
        self.day = assign(self.day, new_md.day)
        self.month = assign(self.month, new_md.month)
        self.year = assign(self.year, new_md.year)
        self.language = assign(self.language, new_md.language)
        self.country = assign(self.country, new_md.country)
        self.web_links = assign(self.web_links, new_md.web_links)
        self.format = assign(self.format, new_md.format)
        self.manga = assign(self.manga, new_md.manga)
        self.black_and_white = assign(self.black_and_white, new_md.black_and_white)
        self.maturity_rating = assign(self.maturity_rating, new_md.maturity_rating)
        self.critical_rating = assign(self.critical_rating, new_md.critical_rating)
        self.scan_info = assign(self.scan_info, new_md.scan_info)

        self.tags = assign(self.tags, new_md.tags)
        self.pages = assign(self.pages, new_md.pages)
        self.page_count = assign(self.page_count, new_md.page_count)

        self.characters = assign(self.characters, new_md.characters)
        self.teams = assign(self.teams, new_md.teams)
        self.locations = assign(self.locations, new_md.locations)
        self.credits = self.assign_credits(self.credits, new_md.credits)

        self.price = assign(self.price, new_md.price)
        self.is_version_of = assign(self.is_version_of, new_md.is_version_of)
        self.rights = assign(self.rights, new_md.rights)
        self.identifier = assign(self.identifier, new_md.identifier)
        self.last_mark = assign(self.last_mark, new_md.last_mark)
        self._cover_image = assign(self._cover_image, new_md._cover_image)
        self._alternate_images = assign(self._alternate_images, new_md._alternate_images)

    def assign_credits_overlay(self, cur_credits: list[Credit], new_credits: list[Credit]) -> list[Credit]:
        return self.credit_dedupe(cur_credits, new_credits)

    def assign_credits_add_missing(self, cur_credits: list[Credit], new_credits: list[Credit]) -> list[Credit]:
        # Send new_credits as cur_credits and vis-versa to keep cur_credit on duplication
        return self.credit_dedupe(new_credits, cur_credits)

    def assign_credits(
        self, cur_credits: list[Credit], new_credits: list[Credit], mode: OverlayMode = OverlayMode.overlay
    ) -> list[Credit]:
        if new_credits is REMOVE:
            return []

        assign_credit_funcs = {
            OverlayMode.overlay: self.assign_credits_overlay,
            OverlayMode.add_missing: self.assign_credits_add_missing,
            OverlayMode.combine: self.assign_credits_overlay,
        }

        assign_credit_func = assign_credit_funcs.get(mode, self.assign_credits_overlay)
        return assign_credit_func(cur_credits, new_credits)

    def apply_default_page_list(self, page_list: Sequence[str]) -> None:
        # generate a default page list, with the first page marked as the cover

        # Create a dictionary of all pages in the metadata
        pages = {p["image_index"]: p for p in self.pages}
        cover_set = False
        # Go through each page in the archive
        # The indexes should always match up
        # It might be a good idea to validate that each page in `pages` is found
        for i, filename in enumerate(page_list):
            if i not in pages:
                pages[i] = ImageMetadata(image_index=i, filename=filename)
            else:
                pages[i]["filename"] = filename

            # Check if we know what the cover is
            cover_set = pages[i].get("type", None) == PageType.FrontCover or cover_set

        self.pages = [p[1] for p in sorted(pages.items())]

        # Set the cover to the first image if we don't know what the cover is
        if not cover_set:
            self.pages[0]["type"] = PageType.FrontCover

    def get_archive_page_index(self, pagenum: int) -> int:
        # convert the displayed page number to the page index of the file in the archive
        if pagenum < len(self.pages):
            return int(self.pages[pagenum]["image_index"])

        return 0

    def get_cover_page_index_list(self) -> list[int]:
        # return a list of archive page indices of cover pages
        coverlist = []
        for p in self.pages:
            if "type" in p and p["type"] == PageType.FrontCover:
                coverlist.append(int(p["image_index"]))

        if len(coverlist) == 0:
            coverlist.append(0)

        return coverlist

    def add_credit(self, person: str, role: str, primary: bool = False) -> None:
        if person == "":
            return

        credit = Credit(person=person, role=role, primary=primary)

        # look to see if it's not already there...
        found = False
        for c in self.credits:
            if norm_fold(c["person"]) == norm_fold(person) and norm_fold(c["role"]) == norm_fold(role):
                # no need to add it. just adjust the "primary" flag as needed
                c["primary"] = primary
                found = True
                break

        if not found:
            self.credits.append(credit)

    def get_primary_credit(self, role: str) -> str:
        primary = ""
        for credit in self.credits:
            if "role" not in credit or "person" not in credit:
                continue
            if (primary == "" and credit["role"].casefold() == role.casefold()) or (
                credit["role"].casefold() == role.casefold() and "primary" in credit and credit["primary"]
            ):
                primary = credit["person"]
        return primary

    def __str__(self) -> str:
        vals: list[tuple[str, Any]] = []
        if self.is_empty:
            return "No metadata"

        def add_string(tag: str, val: Any) -> None:
            if isinstance(val, Sequence):
                if val:
                    vals.append((tag, val))
            elif val is not None:
                vals.append((tag, val))

        add_string("series", self.series)
        add_string("issue", self.issue)
        add_string("issue_count", self.issue_count)
        add_string("title", self.title)
        add_string("publisher", self.publisher)
        add_string("year", self.year)
        add_string("month", self.month)
        add_string("day", self.day)
        add_string("volume", self.volume)
        add_string("volume_count", self.volume_count)
        add_string("genres", ", ".join(self.genres))
        add_string("language", self.language)
        add_string("country", self.country)
        add_string("critical_rating", self.critical_rating)
        add_string("alternate_series", self.alternate_series)
        add_string("alternate_number", self.alternate_number)
        add_string("alternate_count", self.alternate_count)
        add_string("imprint", self.imprint)
        add_string("web_links", [str(x) for x in self.web_links])
        add_string("format", self.format)
        add_string("manga", self.manga)

        add_string("price", self.price)
        add_string("is_version_of", self.is_version_of)
        add_string("rights", self.rights)
        add_string("identifier", self.identifier)
        add_string("last_mark", self.last_mark)

        if self.black_and_white:
            add_string("black_and_white", self.black_and_white)
        add_string("maturity_rating", self.maturity_rating)
        add_string("story_arcs", self.story_arcs)
        add_string("series_groups", self.series_groups)
        add_string("scan_info", self.scan_info)
        add_string("characters", ", ".join(self.characters))
        add_string("teams", ", ".join(self.teams))
        add_string("locations", ", ".join(self.locations))
        add_string("description", self.description)
        add_string("notes", self.notes)

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
    tag_origin=TagOrigin("comicvine", "Comic Vine"),
    series="Cory Doctorow's Futuristic Tales of the Here and Now",
    series_id="23437",
    issue="1",
    issue_id="140529",
    title="Anda's Game",
    publisher="IDW Publishing",
    month=10,
    year=2007,
    day=1,
    issue_count=6,
    volume=1,
    genres={"Sci-Fi"},
    language="en",
    description=(
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
    web_links=[
        parse_url("https://comicvine.gamespot.com/cory-doctorows-futuristic-tales-of-the-here-and-no/4000-140529/")
    ],
    format="Series",
    manga="No",
    black_and_white=None,
    page_count=24,
    maturity_rating="Everyone 10+",
    story_arcs=["Here and Now"],
    series_groups=["Futuristic Tales"],
    scan_info="(CC BY-NC-SA 3.0)",
    characters={"Anda"},
    teams={"Fahrenheit"},
    locations=set(utils.split("lonely  cottage ", ",")),
    credits=[
        Credit(primary=False, person="Dara Naraghi", role="Writer"),
        Credit(primary=False, person="Esteve Polls", role="Penciller"),
        Credit(primary=False, person="Esteve Polls", role="Inker"),
        Credit(primary=False, person="Neil Uyetake", role="Letterer"),
        Credit(primary=False, person="Sam Kieth", role="Cover"),
        Credit(primary=False, person="Ted Adams", role="Editor"),
    ],
    tags=set(),
    pages=[
        ImageMetadata(
            image_index=0, height="1280", size="195977", width="800", type=PageType.FrontCover, filename="!cover.jpg"
        ),
        ImageMetadata(image_index=1, height="2039", size="611993", width="1327", filename="01.jpg"),
        ImageMetadata(image_index=2, height="2039", size="783726", width="1327", filename="02.jpg"),
        ImageMetadata(image_index=3, height="2039", size="679584", width="1327", filename="03.jpg"),
        ImageMetadata(image_index=4, height="2039", size="788179", width="1327", filename="04.jpg"),
        ImageMetadata(image_index=5, height="2039", size="864433", width="1327", filename="05.jpg"),
        ImageMetadata(image_index=6, height="2039", size="765606", width="1327", filename="06.jpg"),
        ImageMetadata(image_index=7, height="2039", size="876427", width="1327", filename="07.jpg"),
        ImageMetadata(image_index=8, height="2039", size="852622", width="1327", filename="08.jpg"),
        ImageMetadata(image_index=9, height="2039", size="800205", width="1327", filename="09.jpg"),
        ImageMetadata(image_index=10, height="2039", size="746243", width="1326", filename="10.jpg"),
        ImageMetadata(image_index=11, height="2039", size="718062", width="1327", filename="11.jpg"),
        ImageMetadata(image_index=12, height="2039", size="532179", width="1326", filename="12.jpg"),
        ImageMetadata(image_index=13, height="2039", size="686708", width="1327", filename="13.jpg"),
        ImageMetadata(image_index=14, height="2039", size="641907", width="1327", filename="14.jpg"),
        ImageMetadata(image_index=15, height="2039", size="805388", width="1327", filename="15.jpg"),
        ImageMetadata(image_index=16, height="2039", size="668927", width="1326", filename="16.jpg"),
        ImageMetadata(image_index=17, height="2039", size="710605", width="1327", filename="17.jpg"),
        ImageMetadata(image_index=18, height="2039", size="761398", width="1326", filename="18.jpg"),
        ImageMetadata(image_index=19, height="2039", size="743807", width="1327", filename="19.jpg"),
        ImageMetadata(image_index=20, height="2039", size="552911", width="1326", filename="20.jpg"),
        ImageMetadata(image_index=21, height="2039", size="556827", width="1327", filename="21.jpg"),
        ImageMetadata(image_index=22, height="2039", size="675078", width="1326", filename="22.jpg"),
        ImageMetadata(
            bookmark="Interview",
            image_index=23,
            height="2032",
            size="800965",
            width="1338",
            type=PageType.Letters,
            filename="23.jpg",
        ),
    ],
    price=None,
    is_version_of=None,
    rights=None,
    identifier=None,
    last_mark=None,
    _cover_image=None,
)


__all__ = (
    "Url",
    "parse_url",
    "PageType",
    "ImageMetadata",
    "Credit",
    "ComicSeries",
    "TagOrigin",
    "GenericMetadata",
)
