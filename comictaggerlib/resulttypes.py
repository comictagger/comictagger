from __future__ import annotations

import dataclasses
import pathlib
import sys
from enum import Enum, auto
from typing import Any

from comicapi import utils
from comicapi.genericmetadata import GenericMetadata

if sys.version_info < (3, 11):

    class StrEnum(str, Enum):
        """
        Enum where members are also (and must be) strings
        """

        def __new__(cls, *values: Any) -> Any:
            "values must already be of type `str`"
            if len(values) > 3:
                raise TypeError(f"too many arguments for str(): {values!r}")
            if len(values) == 1:
                # it must be a string
                if not isinstance(values[0], str):
                    raise TypeError(f"{values[0]!r} is not a string")
            if len(values) >= 2:
                # check that encoding argument is a string
                if not isinstance(values[1], str):
                    raise TypeError(f"encoding must be a string, not {values[1]!r}")
            if len(values) == 3:
                # check that errors argument is a string
                if not isinstance(values[2], str):
                    raise TypeError("errors must be a string, not %r" % (values[2]))
            value = str(*values)
            member = str.__new__(cls, value)
            member._value_ = value
            return member

        @staticmethod
        def _generate_next_value_(name: str, start: int, count: int, last_values: Any) -> str:
            """
            Return the lower-cased version of the member name.
            """
            return name.lower()

else:
    from enum import StrEnum


@dataclasses.dataclass
class IssueResult:
    series: str
    distance: int
    issue_number: str
    cv_issue_count: int | None
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


class Action(StrEnum):
    print = auto()
    delete = auto()
    copy = auto()
    save = auto()
    rename = auto()
    export = auto()
    save_config = auto()
    list_plugins = auto()


class MatchStatus(StrEnum):
    good_match = auto()
    no_match = auto()
    multiple_match = auto()
    low_confidence_match = auto()


class Status(StrEnum):
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

    tags_deleted: list[int] = dataclasses.field(default_factory=list)
    tags_written: list[int] = dataclasses.field(default_factory=list)

    def __str__(self) -> str:
        if len(self.online_results) == 0:
            matches = None
        elif len(self.online_results) == 1:
            matches = str(self.online_results[0])
        else:
            matches = "\n" + "".join([f" -  {x}" for x in self.online_results])
        path_str = utils.path_to_short_str(self.original_path, self.renamed_path)
        return f"{path_str}: {matches}"
