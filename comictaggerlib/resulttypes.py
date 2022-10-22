from __future__ import annotations

from typing_extensions import TypedDict

from comicapi.comicarchive import ComicArchive


class IssueResult(TypedDict):
    series: str
    distance: int
    issue_number: str
    cv_issue_count: int
    url_image_hash: int
    issue_title: str
    issue_id: int  # int?
    volume_id: int  # int?
    month: int | None
    year: int | None
    publisher: str | None
    image_url: str
    thumb_url: str
    page_url: str
    description: str


class OnlineMatchResults:
    def __init__(self) -> None:
        self.good_matches: list[str] = []
        self.no_matches: list[str] = []
        self.multiple_matches: list[MultipleMatch] = []
        self.low_confidence_matches: list[MultipleMatch] = []
        self.write_failures: list[str] = []
        self.fetch_data_failures: list[str] = []


class MultipleMatch:
    def __init__(self, ca: ComicArchive, match_list: list[IssueResult]) -> None:
        self.ca: ComicArchive = ca
        self.matches: list[IssueResult] = match_list
