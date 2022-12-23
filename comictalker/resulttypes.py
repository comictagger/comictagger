from __future__ import annotations

import copy
import dataclasses


@dataclasses.dataclass
class Credit:
    name: str
    role: str


@dataclasses.dataclass
class ComicSeries:
    aliases: list[str]
    count_of_issues: int | None
    description: str
    id: str
    image_url: str
    name: str
    publisher: str
    start_year: int | None

    def copy(self) -> ComicSeries:
        return copy.deepcopy(self)


@dataclasses.dataclass
class ComicIssue:
    series: ComicSeries
    credits: list[Credit]

    aliases: list[str] = dataclasses.field(default_factory=list)
    cover_date: str = ""
    description: str = ""
    id: str = ""
    image_url: str = ""
    issue_number: str = ""
    rating: float = 0
    manga: str = ""
    genres: list[str] = dataclasses.field(default_factory=list)
    tags: list[str] = dataclasses.field(default_factory=list)
    name: str = ""
    site_detail_url: str = ""
    alt_image_urls: list[str] = dataclasses.field(default_factory=list)
    characters: list[str] = dataclasses.field(default_factory=list)
    locations: list[str] = dataclasses.field(default_factory=list)
    teams: list[str] = dataclasses.field(default_factory=list)
    story_arcs: list[str] = dataclasses.field(default_factory=list)
    complete: bool = False  # Is this a complete ComicIssue? or is there more data to fetch

    def copy(self) -> ComicIssue:
        return copy.deepcopy(self)
