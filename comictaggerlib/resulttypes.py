from typing import List, TypedDict

from comicapi.comicarchive import ComicArchive


class IssueResult(TypedDict):
    series: str
    distance: int
    issue_number: str
    cv_issue_count: int
    url_image_hash: str
    issue_title: str
    issue_id: str  # int?
    volume_id: str  # int?
    month: int
    year: int
    publisher: str
    image_url: str
    thumb_url: str
    page_url: str
    description: str


class OnlineMatchResults:
    def __init__(self):
        self.good_matches: List[str] = []
        self.no_matches: List[str] = []
        self.multiple_matches: List[MultipleMatch] = []
        self.low_confidence_matches: List[MultipleMatch] = []
        self.write_failures: List[str] = []
        self.fetch_data_failures: List[str] = []


class MultipleMatch:
    def __init__(self, ca: ComicArchive, match_list: List[IssueResult]):
        self.ca: ComicArchive = ca
        self.matches = match_list
