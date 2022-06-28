from __future__ import annotations

from typing_extensions import Required, TypedDict


class SelectDetails(TypedDict):
    image_url: str | None
    thumb_image_url: str | None
    cover_date: str | None
    site_detail_url: str | None


class ComicVolume(TypedDict, total=False):
    count_of_issues: int
    description: str
    id: Required[int]
    image: str
    name: Required[str]
    publisher: str
    start_year: str


class ComicIssue(TypedDict, total=False):
    cover_date: str
    description: str
    id: int
    image: str
    image_thumb: str
    issue_number: Required[str]
    name: Required[str]
    site_detail_url: str
    volume: ComicVolume
