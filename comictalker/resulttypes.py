from __future__ import annotations

from typing_extensions import Required, TypedDict


class Credits(TypedDict):
    name: str
    role: str


class ComicSeries(TypedDict, total=False):
    aliases: list[str]
    count_of_issues: int
    description: str
    id: Required[str]
    image_url: str
    name: Required[str]
    publisher: str
    start_year: int | None


class ComicIssue(TypedDict, total=False):
    aliases: list[str]
    cover_date: str
    description: str
    id: str
    image_url: str
    image_thumb_url: str
    issue_number: Required[str]
    name: Required[str]
    site_detail_url: str
    series: ComicSeries
    alt_image_urls: list[str]
    characters: list[str]
    locations: list[str]
    credits: list[Credits]
    teams: list[str]
    story_arcs: list[str]
    complete: bool  # Is this a complete ComicIssue? or is there more data to fetch
