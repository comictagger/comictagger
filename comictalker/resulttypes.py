from __future__ import annotations

from typing_extensions import Required, TypedDict


class ComicVolume(TypedDict, total=False):
    aliases: str  # Newline separated
    count_of_issues: int
    description: str
    id: Required[int]
    image_url: str
    name: Required[str]
    publisher: str
    start_year: int


class ComicIssue(TypedDict, total=False):
    aliases: str  # Newline separated
    cover_date: str
    description: str
    id: int
    image_url: str
    image_thumb_url: str
    issue_number: Required[str]
    name: Required[str]
    site_detail_url: str
    volume: ComicVolume
