from __future__ import annotations

import dataclasses
import pathlib
from enum import auto

from comicapi import utils
from comicapi.genericmetadata import GenericMetadata


@dataclasses.dataclass
class IssueResult:
    series: str
    distance: int
    issue_number: str
    issue_count: int | None
    url_image_hash: int
    issue_title: str
    issue_id: str
    series_id: str
    month: int | None
    year: int | None
    publisher: str | None
    image_url: str
    alt_image_urls: list[str]
    description: str

    def __str__(self) -> str:
        return f"series: {self.series}; series id: {self.series_id}; issue number: {self.issue_number}; issue id: {self.issue_id}; published: {self.month} {self.year}"


class Action(utils.StrEnum):
    print = auto()
    delete = auto()
    copy = auto()
    save = auto()
    rename = auto()
    export = auto()
    save_config = auto()
    list_plugins = auto()


class MatchStatus(utils.StrEnum):
    good_match = auto()
    no_match = auto()
    multiple_match = auto()
    low_confidence_match = auto()


class Status(utils.StrEnum):
    success = auto()
    match_failure = auto()
    write_failure = auto()
    fetch_data_failure = auto()
    existing_tags = auto()
    read_failure = auto()
    write_permission_failure = auto()
    rename_failure = auto()


@dataclasses.dataclass
class OnlineMatchResults:
    good_matches: list[Result] = dataclasses.field(default_factory=list)
    no_matches: list[Result] = dataclasses.field(default_factory=list)
    multiple_matches: list[Result] = dataclasses.field(default_factory=list)
    low_confidence_matches: list[Result] = dataclasses.field(default_factory=list)
    write_failures: list[Result] = dataclasses.field(default_factory=list)
    fetch_data_failures: list[Result] = dataclasses.field(default_factory=list)


@dataclasses.dataclass
class Result:
    action: Action
    status: Status | None

    original_path: pathlib.Path
    renamed_path: pathlib.Path | None = None

    online_results: list[IssueResult] = dataclasses.field(default_factory=list)
    match_status: MatchStatus | None = None

    md: GenericMetadata | None = None

    tags_deleted: list[str] = dataclasses.field(default_factory=list)
    tags_written: list[str] = dataclasses.field(default_factory=list)

    def __str__(self) -> str:
        if len(self.online_results) == 0:
            matches = None
        elif len(self.online_results) == 1:
            matches = str(self.online_results[0])
        else:
            matches = "\n" + "".join([f" -  {x}" for x in self.online_results])
        path_str = utils.path_to_short_str(self.original_path, self.renamed_path)
        return f"{path_str}: {matches}"
