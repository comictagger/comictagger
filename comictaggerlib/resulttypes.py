from __future__ import annotations

from typing_extensions import NotRequired, Required, TypedDict

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


class SelectDetails(TypedDict):
    image_url: str | None
    thumb_image_url: str | None
    cover_date: str | None
    site_detail_url: str | None


class CVResult(TypedDict):
    error: str
    limit: int
    offset: int
    number_of_page_results: int
    number_of_total_results: int
    status_code: int
    results: (
        CVIssuesResults
        | CVIssueDetailResults
        | CVVolumeResults
        | list[CVIssuesResults]
        | list[CVVolumeResults]
        | list[CVIssueDetailResults]
    )
    version: str


class CVImage(TypedDict, total=False):
    icon_url: str
    medium_url: str
    screen_url: str
    screen_large_url: str
    small_url: str
    super_url: Required[str]
    thumb_url: str
    tiny_url: str
    original_url: str
    image_tags: str


class CVVolume(TypedDict):
    api_detail_url: str
    id: int
    name: str
    site_detail_url: str


class CVIssuesResults(TypedDict):
    cover_date: str
    description: str
    id: int
    image: CVImage
    issue_number: str
    name: str
    site_detail_url: str
    volume: NotRequired[CVVolume]


class CVPublisher(TypedDict, total=False):
    api_detail_url: str
    id: int
    name: Required[str]


class CVVolumeResults(TypedDict):
    count_of_issues: int
    description: NotRequired[str]
    id: int
    image: NotRequired[CVImage]
    name: str
    publisher: CVPublisher
    start_year: str
    resource_type: NotRequired[str]


class CVCredits(TypedDict):
    api_detail_url: str
    id: int
    name: str
    site_detail_url: str


class CVPersonCredits(TypedDict):
    api_detail_url: str
    id: int
    name: str
    site_detail_url: str
    role: str


class CVIssueDetailResults(TypedDict):
    aliases: None
    api_detail_url: str
    character_credits: list[CVCredits]
    character_died_in: None
    concept_credits: list[CVCredits]
    cover_date: str
    date_added: str
    date_last_updated: str
    deck: None
    description: str
    first_appearance_characters: None
    first_appearance_concepts: None
    first_appearance_locations: None
    first_appearance_objects: None
    first_appearance_storyarcs: None
    first_appearance_teams: None
    has_staff_review: bool
    id: int
    image: CVImage
    issue_number: str
    location_credits: list[CVCredits]
    name: str
    object_credits: list[CVCredits]
    person_credits: list[CVPersonCredits]
    site_detail_url: str
    store_date: str
    story_arc_credits: list[CVCredits]
    team_credits: list[CVCredits]
    team_disbanded_in: None
    volume: CVVolume
