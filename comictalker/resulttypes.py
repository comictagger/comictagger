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
    genres: list[str]

    def copy(self) -> ComicSeries:
        return copy.deepcopy(self)


@dataclasses.dataclass
class ComicIssue:
    aliases: list[str]
    cover_date: str
    description: str
    id: str
    image_url: str
    issue_number: str
    rating: float
    manga: str
    genres: list[str]
    tags: list[str]
    name: str
    site_detail_url: str
    series: ComicSeries
    alt_image_urls: list[str]
    characters: list[str]
    locations: list[str]
    credits: list[Credit]
    teams: list[str]
    story_arcs: list[str]
    complete: bool  # Is this a complete ComicIssue? or is there more data to fetch

    def copy(self) -> ComicIssue:
        return copy.deepcopy(self)
