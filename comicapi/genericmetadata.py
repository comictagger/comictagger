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
from collections.abc import Sequence
from typing import TYPE_CHECKING, Any, Union, overload

from typing_extensions import NamedTuple

from comicapi import merge, utils
from comicapi._url import Url, parse_url
from comicapi.utils import norm_fold

# needed for runtime type guessing
if TYPE_CHECKING:
    Union

logger = logging.getLogger(__name__)


REMOVE = object()


class PageType(merge.StrEnum):
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


@dataclasses.dataclass
class PageMetadata:
    filename: str
    type: str
    bookmark: str
    display_index: int
    archive_index: int
    # These are optional because getting this info requires reading in each page
    double_page: bool | None = None
    byte_size: int | None = None
    height: int | None = None
    width: int | None = None

    def set_type(self, value: str) -> None:
        values = {x.casefold(): x for x in PageType}
        self.type = values.get(value.casefold(), value)

    def is_double_page(self) -> bool:
        w = self.width or 0
        h = self.height or 0
        return self.double_page or (w >= h and w > 0 and h > 0)

    def __lt__(self, other: Any) -> bool:
        if not isinstance(other, PageMetadata):
            return False
        return self.archive_index < other.archive_index

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, PageMetadata):
            return False
        return self.archive_index == other.archive_index

    def _get_clean_metadata(self, *attributes: str) -> PageMetadata:
        return PageMetadata(
            filename=self.filename if "filename" in attributes else "",
            type=self.type if "type" in attributes else "",
            bookmark=self.bookmark if "bookmark" in attributes else "",
            display_index=self.display_index if "display_index" in attributes else 0,
            archive_index=self.archive_index if "archive_index" in attributes else 0,
            double_page=self.double_page if "double_page" in attributes else None,
            byte_size=self.byte_size if "byte_size" in attributes else None,
            height=self.height if "height" in attributes else None,
            width=self.width if "width" in attributes else None,
        )


Credit = merge.Credit


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


class MetadataOrigin(NamedTuple):
    id: str
    name: str

    def __str__(self) -> str:
        return self.name


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
    data_origin: MetadataOrigin | None = None
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
    pages: list[PageMetadata] = dataclasses.field(default_factory=list)
    page_count: int | None = None

    characters: set[str] = dataclasses.field(default_factory=set)
    teams: set[str] = dataclasses.field(default_factory=set)
    locations: set[str] = dataclasses.field(default_factory=set)
    credits: list[merge.Credit] = dataclasses.field(default_factory=list)

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

    def _get_clean_metadata(self, *attributes: str) -> GenericMetadata:
        new_md = GenericMetadata()
        list_handled = []
        for attr in sorted(attributes):
            if "." in attr:
                lst, _, name = attr.partition(".")
                if lst in list_handled:
                    continue
                old_value = getattr(self, lst)
                new_value = getattr(new_md, lst)
                if old_value:
                    if hasattr(old_value[0], "_get_clean_metadata"):
                        list_attributes = [x.removeprefix(lst + ".") for x in attributes if x.startswith(lst)]
                        for x in old_value:
                            new_value.append(x._get_clean_metadata(*list_attributes))
                        list_handled.append(lst)
                        continue
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

    def overlay(
        self, new_md: GenericMetadata, mode: merge.Mode = merge.Mode.OVERLAY, merge_lists: bool = False
    ) -> None:
        """Overlay a new metadata object on this one"""

        attribute_merge = merge.attribute[mode]
        list_merge = merge.lists[mode]

        def assign(old: Any, new: Any, attribute_merge: Any = attribute_merge) -> Any:
            if new is REMOVE:
                return None

            return attribute_merge(old, new)

        def assign_list(old: list[Any] | set[Any], new: list[Any] | set[Any], list_merge: Any = list_merge) -> Any:
            if new is REMOVE:
                old.clear()
                return old
            if merge_lists:
                return list_merge(old, new)
            else:
                return assign(old, new)

        if not new_md.is_empty:
            self.is_empty = False

        self.data_origin = assign(self.data_origin, new_md.data_origin)  # TODO use and purpose now?
        self.issue_id = assign(self.issue_id, new_md.issue_id)
        self.series_id = assign(self.series_id, new_md.series_id)

        self.series = assign(self.series, new_md.series)

        self.series_aliases = assign_list(self.series_aliases, new_md.series_aliases)
        self.issue = assign(self.issue, new_md.issue)
        self.issue_count = assign(self.issue_count, new_md.issue_count)
        self.title = assign(self.title, new_md.title)
        self.title_aliases = assign_list(self.title_aliases, new_md.title_aliases)
        self.volume = assign(self.volume, new_md.volume)
        self.volume_count = assign(self.volume_count, new_md.volume_count)
        self.genres = assign_list(self.genres, new_md.genres)
        self.description = assign(self.description, new_md.description)
        self.notes = assign(self.notes, new_md.notes)

        self.alternate_series = assign(self.alternate_series, new_md.alternate_series)
        self.alternate_number = assign(self.alternate_number, new_md.alternate_number)
        self.alternate_count = assign(self.alternate_count, new_md.alternate_count)
        self.story_arcs = assign_list(self.story_arcs, new_md.story_arcs)
        self.series_groups = assign_list(self.series_groups, new_md.series_groups)

        self.publisher = assign(self.publisher, new_md.publisher)
        self.imprint = assign(self.imprint, new_md.imprint)
        self.day = assign(self.day, new_md.day)
        self.month = assign(self.month, new_md.month)
        self.year = assign(self.year, new_md.year)
        self.language = assign(self.language, new_md.language)
        self.country = assign(self.country, new_md.country)
        self.web_links = assign_list(self.web_links, new_md.web_links)
        self.format = assign(self.format, new_md.format)
        self.manga = assign(self.manga, new_md.manga)
        self.black_and_white = assign(self.black_and_white, new_md.black_and_white)
        self.maturity_rating = assign(self.maturity_rating, new_md.maturity_rating)
        self.critical_rating = assign(self.critical_rating, new_md.critical_rating)
        self.scan_info = assign(self.scan_info, new_md.scan_info)

        self.tags = assign_list(self.tags, new_md.tags)

        self.characters = assign_list(self.characters, new_md.characters)
        self.teams = assign_list(self.teams, new_md.teams)
        self.locations = assign_list(self.locations, new_md.locations)

        # credits are added through add_credit so that some standard checks are observed
        # which means that we needs self.credits to be empty
        tmp_credits = self.credits
        self.credits = []
        for c in assign_list(tmp_credits, new_md.credits):
            self.add_credit(c)

        self.price = assign(self.price, new_md.price)
        self.is_version_of = assign(self.is_version_of, new_md.is_version_of)
        self.rights = assign(self.rights, new_md.rights)
        self.identifier = assign(self.identifier, new_md.identifier)
        self.last_mark = assign(self.last_mark, new_md.last_mark)
        self._cover_image = assign(self._cover_image, new_md._cover_image)
        self._alternate_images = assign_list(self._alternate_images, new_md._alternate_images)

        # pages doesn't get merged, if we did merge we would end up with duplicate pages
        self.pages = assign(self.pages, new_md.pages)
        self.page_count = assign(self.page_count, new_md.page_count)

    def apply_default_page_list(self, page_list: Sequence[str]) -> None:
        """apply a default page list, with the first page marked as the cover"""

        # Create a dictionary in the weird case that the metadata doesn't match the archive
        pages = {p.archive_index: p for p in self.pages}
        cover_set = False

        # It might be a good idea to validate that each page in `pages` is found in page_list
        for i, filename in enumerate(page_list):
            page = pages.get(i, PageMetadata(archive_index=i, display_index=i, filename="", type="", bookmark=""))
            page.filename = filename
            pages[i] = page

            # Check if we know what the cover is
            cover_set = page.type == PageType.FrontCover or cover_set
        self.pages = sorted(pages.values())

        self.page_count = len(self.pages)
        if self.page_count != len(page_list):
            logger.warning("Wrong count of pages: expected %d got %d", len(self.pages), len(page_list))
        # Set the cover to the first image acording to hte display index if we don't know what the cover is
        if not cover_set:
            first_page = self.get_archive_page_index(0)
            self.pages[first_page].type = PageType.FrontCover

    def get_archive_page_index(self, pagenum: int) -> int:
        """convert the displayed page number to the page index of the file in the archive"""
        if pagenum < len(self.pages):
            return int(sorted(self.pages, key=lambda p: p.display_index)[pagenum].archive_index)

        return 0

    def get_cover_page_index_list(self) -> list[int]:
        # return a list of archive page indices of cover pages
        if not self.pages:
            return [0]
        coverlist = []
        for p in self.pages:
            if p.type == PageType.FrontCover:
                coverlist.append(p.archive_index)

        if len(coverlist) == 0:
            coverlist.append(self.get_archive_page_index(0))

        return coverlist

    @overload
    def add_credit(self, person: merge.Credit) -> None: ...

    @overload
    def add_credit(self, person: str, role: str, primary: bool = False) -> None: ...

    def add_credit(self, person: str | merge.Credit, role: str | None = None, primary: bool = False) -> None:

        credit: merge.Credit
        if isinstance(person, merge.Credit):
            credit = person
        else:
            assert role is not None
            credit = merge.Credit(person=person, role=role, primary=primary)

        if credit.role is None:
            raise TypeError("GenericMetadata.add_credit takes either a Credit object or a person name and role")
        if credit.person == "":
            return

        person = norm_fold(credit.person)
        role = norm_fold(credit.role)

        # look to see if it's not already there...
        found = False
        for c in self.credits:
            if norm_fold(c.person) == person and norm_fold(c.role) == role:
                # no need to add it. just adjust the "primary" flag as needed
                c.primary = c.primary or primary
                found = True
                break

        if not found:
            self.credits.append(credit)

    def get_primary_credit(self, role: str) -> str:
        primary = ""
        for credit in self.credits:
            if (primary == "" and credit.role.casefold() == role.casefold()) or (
                credit.role.casefold() == role.casefold() and credit.primary
            ):
                primary = credit.person
        return primary

    def __str__(self) -> str:
        vals: list[tuple[str, Any]] = []
        if self.is_empty:
            return "No metadata"

        def add_string(tag: str, val: Any) -> None:
            if isinstance(val, (Sequence, set)):
                if val:
                    vals.append((tag, val))
            elif val is not None:
                vals.append((tag, val))

        add_string("data_origin", self.data_origin)
        add_string("series", self.series)
        add_string("series_aliases", ",".join(self.series_aliases))
        add_string("issue", self.issue)
        add_string("issue_count", self.issue_count)
        add_string("title", self.title)
        add_string("title_aliases", ",".join(self.title_aliases))
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
            if c.primary:
                primary = " [P]"
            add_string("credit", f"{c}{primary}")

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
    data_origin=MetadataOrigin("comicvine", "Comic Vine"),
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
        merge.Credit(primary=False, person="Dara Naraghi", role="Writer"),
        merge.Credit(primary=False, person="Esteve Polls", role="Penciller"),
        merge.Credit(primary=False, person="Esteve Polls", role="Inker"),
        merge.Credit(primary=False, person="Neil Uyetake", role="Letterer"),
        merge.Credit(primary=False, person="Sam Kieth", role="Cover"),
        merge.Credit(primary=False, person="Ted Adams", role="Editor"),
    ],
    tags=set(),
    pages=[
        PageMetadata(
            archive_index=0,
            display_index=0,
            height=1280,
            byte_size=195977,
            width=800,
            type=PageType.FrontCover,
            filename="!cover.jpg",
            bookmark="",
        ),
        PageMetadata(
            archive_index=1,
            display_index=1,
            height=2039,
            byte_size=611993,
            width=1327,
            filename="01.jpg",
            bookmark="",
            type="",
        ),
        PageMetadata(
            archive_index=2,
            display_index=2,
            height=2039,
            byte_size=783726,
            width=1327,
            filename="02.jpg",
            bookmark="",
            type="",
        ),
        PageMetadata(
            archive_index=3,
            display_index=3,
            height=2039,
            byte_size=679584,
            width=1327,
            filename="03.jpg",
            bookmark="",
            type="",
        ),
        PageMetadata(
            archive_index=4,
            display_index=4,
            height=2039,
            byte_size=788179,
            width=1327,
            filename="04.jpg",
            bookmark="",
            type="",
        ),
        PageMetadata(
            archive_index=5,
            display_index=5,
            height=2039,
            byte_size=864433,
            width=1327,
            filename="05.jpg",
            bookmark="",
            type="",
        ),
        PageMetadata(
            archive_index=6,
            display_index=6,
            height=2039,
            byte_size=765606,
            width=1327,
            filename="06.jpg",
            bookmark="",
            type="",
        ),
        PageMetadata(
            archive_index=7,
            display_index=7,
            height=2039,
            byte_size=876427,
            width=1327,
            filename="07.jpg",
            bookmark="",
            type="",
        ),
        PageMetadata(
            archive_index=8,
            display_index=8,
            height=2039,
            byte_size=852622,
            width=1327,
            filename="08.jpg",
            bookmark="",
            type="",
        ),
        PageMetadata(
            archive_index=9,
            display_index=9,
            height=2039,
            byte_size=800205,
            width=1327,
            filename="09.jpg",
            bookmark="",
            type="",
        ),
        PageMetadata(
            archive_index=10,
            display_index=10,
            height=2039,
            byte_size=746243,
            width=1326,
            filename="10.jpg",
            bookmark="",
            type="",
        ),
        PageMetadata(
            archive_index=11,
            display_index=11,
            height=2039,
            byte_size=718062,
            width=1327,
            filename="11.jpg",
            bookmark="",
            type="",
        ),
        PageMetadata(
            archive_index=12,
            display_index=12,
            height=2039,
            byte_size=532179,
            width=1326,
            filename="12.jpg",
            bookmark="",
            type="",
        ),
        PageMetadata(
            archive_index=13,
            display_index=13,
            height=2039,
            byte_size=686708,
            width=1327,
            filename="13.jpg",
            bookmark="",
            type="",
        ),
        PageMetadata(
            archive_index=14,
            display_index=14,
            height=2039,
            byte_size=641907,
            width=1327,
            filename="14.jpg",
            bookmark="",
            type="",
        ),
        PageMetadata(
            archive_index=15,
            display_index=15,
            height=2039,
            byte_size=805388,
            width=1327,
            filename="15.jpg",
            bookmark="",
            type="",
        ),
        PageMetadata(
            archive_index=16,
            display_index=16,
            height=2039,
            byte_size=668927,
            width=1326,
            filename="16.jpg",
            bookmark="",
            type="",
        ),
        PageMetadata(
            archive_index=17,
            display_index=17,
            height=2039,
            byte_size=710605,
            width=1327,
            filename="17.jpg",
            bookmark="",
            type="",
        ),
        PageMetadata(
            archive_index=18,
            display_index=18,
            height=2039,
            byte_size=761398,
            width=1326,
            filename="18.jpg",
            bookmark="",
            type="",
        ),
        PageMetadata(
            archive_index=19,
            display_index=19,
            height=2039,
            byte_size=743807,
            width=1327,
            filename="19.jpg",
            bookmark="",
            type="",
        ),
        PageMetadata(
            archive_index=20,
            display_index=20,
            height=2039,
            byte_size=552911,
            width=1326,
            filename="20.jpg",
            bookmark="",
            type="",
        ),
        PageMetadata(
            archive_index=21,
            display_index=21,
            height=2039,
            byte_size=556827,
            width=1327,
            filename="21.jpg",
            bookmark="",
            type="",
        ),
        PageMetadata(
            archive_index=22,
            display_index=22,
            height=2039,
            byte_size=675078,
            width=1326,
            filename="22.jpg",
            bookmark="",
            type="",
        ),
        PageMetadata(
            bookmark="Interview",
            archive_index=23,
            display_index=23,
            height=2032,
            byte_size=800965,
            width=1338,
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
    "PageMetadata",
    "Credit",
    "ComicSeries",
    "MetadataOrigin",
    "GenericMetadata",
)
