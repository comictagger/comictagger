"""Some generic utilities"""

# Copyright 2012-2014 ComicTagger Authors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
from __future__ import annotations

import json
import logging
import os
import pathlib
import platform
import sys
import unicodedata
from collections import defaultdict
from collections.abc import Iterable, Mapping
from enum import Enum, auto
from shutil import which  # noqa: F401
from typing import Any, TypeVar, cast

from comicfn2dict import comicfn2dict

import comicapi.data
from comicapi import filenamelexer, filenameparser

from ._url import LocationParseError as LocationParseError  # noqa: F401
from ._url import Url as Url
from ._url import parse_url as parse_url

try:
    import icu

    del icu
    icu_available = True
except ImportError:
    icu_available = False


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


logger = logging.getLogger(__name__)


class Parser(StrEnum):
    ORIGINAL = auto()
    COMPLICATED = auto()
    COMICFN2DICT = auto()


def _custom_key(tup: Any) -> Any:
    import natsort

    lst = []
    for x in natsort.os_sort_keygen()(tup):
        ret = x
        if len(x) > 1 and isinstance(x[1], int) and isinstance(x[0], str) and x[0] == "":
            ret = ("a", *x[1:])

        lst.append(ret)
    return tuple(lst)


T = TypeVar("T")


def os_sorted(lst: Iterable[T]) -> Iterable[T]:
    import natsort

    key = _custom_key
    if icu_available or platform.system() == "Windows":
        key = natsort.os_sort_keygen()
    return sorted(lst, key=key)


def parse_filename(
    filename: str,
    parser: Parser = Parser.ORIGINAL,
    remove_c2c: bool = False,
    remove_fcbd: bool = False,
    remove_publisher: bool = False,
    split_words: bool = False,
    allow_issue_start_with_letter: bool = False,
    protofolius_issue_number_scheme: bool = False,
) -> filenameparser.FilenameInfo:
    if not filename:
        return filenameparser.FilenameInfo(
            alternate="",
            annual=False,
            archive="",
            c2c=False,
            fcbd=False,
            issue="",
            issue_count="",
            publisher="",
            remainder="",
            series="",
            title="",
            volume="",
            volume_count="",
            year="",
            format="",
        )
    if split_words:
        import wordninja

        filename, ext = os.path.splitext(filename)
        filename = " ".join(wordninja.split(filename)) + ext

    fni = filenameparser.FilenameInfo(
        alternate="",
        annual=False,
        archive="",
        c2c=False,
        fcbd=False,
        format="",
        issue="",
        issue_count="",
        publisher="",
        remainder="",
        series="",
        title="",
        volume="",
        volume_count="",
        year="",
    )

    if parser == Parser.COMPLICATED:
        lex = filenamelexer.Lex(filename, allow_issue_start_with_letter)
        p = filenameparser.Parse(
            lex.items,
            remove_c2c=remove_c2c,
            remove_fcbd=remove_fcbd,
            remove_publisher=remove_publisher,
            protofolius_issue_number_scheme=protofolius_issue_number_scheme,
        )
        fni = p.filename_info
    elif parser == Parser.COMICFN2DICT:
        fn2d = comicfn2dict(filename)
        fni = filenameparser.FilenameInfo(
            alternate="",
            annual=False,
            archive=fn2d.get("ext", ""),
            c2c=False,
            fcbd=False,
            issue=fn2d.get("issue", ""),
            issue_count=fn2d.get("issue_count", ""),
            publisher=fn2d.get("publisher", ""),
            remainder=fn2d.get("scan_info", ""),
            series=fn2d.get("series", ""),
            title=fn2d.get("title", ""),
            volume=fn2d.get("volume", ""),
            volume_count=fn2d.get("volume_count", ""),
            year=fn2d.get("year", ""),
            format=fn2d.get("original_format", ""),
        )
    else:
        fnp = filenameparser.FileNameParser()
        fnp.parse_filename(filename)
        fni = filenameparser.FilenameInfo(
            alternate="",
            annual=False,
            archive="",
            c2c=False,
            fcbd=False,
            issue=fnp.issue,
            issue_count=fnp.issue_count,
            publisher="",
            remainder=fnp.remainder,
            series=fnp.series,
            title="",
            volume=fnp.volume,
            volume_count="",
            year=fnp.year,
            format="",
        )
    return fni


def combine_notes(existing_notes: str | None, new_notes: str | None, split: str) -> str:
    split_notes, split_str, untouched_notes = (existing_notes or "").rpartition(split)
    if split_notes or split_str:
        return (split_notes + (new_notes or "")).strip()
    else:
        return (untouched_notes + "\n" + (new_notes or "")).strip()


def parse_date_str(date_str: str | None) -> tuple[int | None, int | None, int | None]:
    day = None
    month = None
    year = None
    if date_str:
        parts = date_str.split("-")
        year = xlate_int(parts[0])
        if len(parts) > 1:
            month = xlate_int(parts[1])
            if len(parts) > 2:
                day = xlate_int(parts[2])
    return day, month, year


def shorten_path(path: pathlib.Path, path2: pathlib.Path | None = None) -> tuple[pathlib.Path, pathlib.Path]:
    if path2:
        path2 = path2.absolute()

    path = path.absolute()
    shortened_path: pathlib.Path = path
    relative_path = pathlib.Path(path.anchor)

    if path.is_relative_to(path.home()):
        relative_path = path.home()
        shortened_path = path.relative_to(path.home())
    if path.is_relative_to(path.cwd()):
        relative_path = path.cwd()
        shortened_path = path.relative_to(path.cwd())

    if path2 and shortened_path.is_relative_to(path2.parent):
        relative_path = path2
        shortened_path = shortened_path.relative_to(path2)

    return relative_path, shortened_path


def path_to_short_str(original_path: pathlib.Path, renamed_path: pathlib.Path | None = None) -> str:
    rel, _original_path = shorten_path(original_path)
    path_str = str(_original_path)
    if rel.samefile(rel.cwd()):
        path_str = f"./{_original_path}"
    elif rel.samefile(rel.home()):
        path_str = f"~/{_original_path}"

    if renamed_path:
        rel, path = shorten_path(renamed_path, original_path.parent)
        rename_str = f" -> {path}"
        if rel.samefile(rel.cwd()):
            rename_str = f" -> ./{_original_path}"
        elif rel.samefile(rel.home()):
            rename_str = f" -> ~/{_original_path}"
        path_str += rename_str

    return path_str


def get_page_name_list(files: list[str]) -> list[str]:
    # get the list file names in the archive, and sort
    files = cast(list[str], os_sorted(files))

    # make a sub-list of image files
    page_list = []
    for name in files:
        if (
            os.path.splitext(name)[1].casefold() in [".jpg", ".jpeg", ".png", ".gif", ".webp", ".avif"]
            and os.path.basename(name)[0] != "."
        ):
            page_list.append(name)
    return page_list


def get_recursive_filelist(pathlist: list[str]) -> list[str]:
    """Get a recursive list of of all files under all path items in the list"""

    filelist: list[str] = []
    for p in pathlist:
        if os.path.isdir(p):
            for root, _, files in os.walk(p):
                for f in files:
                    filelist.append(os.path.join(root, f))
        elif os.path.exists(p):
            filelist.append(p)

    return filelist


def add_to_path(dirname: str) -> None:
    if dirname:
        dirname = os.path.abspath(dirname)
        paths = [os.path.normpath(x) for x in split(os.environ["PATH"], os.pathsep)]

        if dirname not in paths:
            paths.insert(0, dirname)
            os.environ["PATH"] = os.pathsep.join(paths)


def remove_from_path(dirname: str) -> None:
    if dirname:
        dirname = os.path.abspath(dirname)
        paths = [os.path.normpath(x) for x in split(os.environ["PATH"], os.pathsep) if dirname != os.path.normpath(x)]

        os.environ["PATH"] = os.pathsep.join(paths)


def xlate_int(data: Any) -> int | None:
    data = xlate_float(data)
    if data is None:
        return None
    return int(data)


def xlate_float(data: Any) -> float | None:
    if isinstance(data, str):
        data = data.strip()
    if data is None or data == "":
        return None
    i: str | int | float
    if isinstance(data, (int, float)):
        i = data
    else:
        i = str(data).translate(defaultdict(lambda: None, zip((ord(c) for c in "1234567890."), "1234567890.")))
    if i == "":
        return None
    try:
        return float(i)
    except ValueError:
        return None


def xlate(data: Any) -> str | None:
    if data is None or isinstance(data, str) and data.strip() == "":
        return None

    return str(data).strip()


def split(s: str | None, c: str) -> list[str]:
    s = xlate(s)
    if s:
        return [x.strip() for x in s.strip().split(c) if x.strip()]
    return []


def split_urls(s: str | None) -> list[Url]:
    if s is None:
        return []
    # Find occurences of ' http'
    if s.count("http") > 1 and s.count(" http") >= 1:
        urls = []
        # Split urls out
        url_strings = split(s, " http")
        # Return the scheme 'http' and parse the url
        for i, url_string in enumerate(url_strings):
            if not url_string.startswith("http"):
                url_string = "http" + url_string
            urls.append(parse_url(url_string))
        return urls
    else:
        return [parse_url(s)]


def remove_articles(text: str) -> str:
    text = text.casefold()
    articles = [
        "&",
        "a",
        "am",
        "an",
        "and",
        "as",
        "at",
        "be",
        "but",
        "by",
        "for",
        "if",
        "is",
        "issue",
        "it",
        "it's",
        "its",
        "itself",
        "of",
        "or",
        "so",
        "the",
        "the",
        "with",
    ]
    new_text = ""
    for word in text.split():
        if word not in articles:
            new_text += word + " "

    new_text = new_text[:-1]

    return new_text


def sanitize_title(text: str, basic: bool = False) -> str:
    # normalize unicode and convert to ascii. Does not work for everything eg ½ to 1⁄2 not 1/2
    text = unicodedata.normalize("NFKD", text).casefold()
    # comicvine keeps apostrophes a part of the word
    text = text.replace("'", "")
    text = text.replace('"', "")
    if not basic:
        # comicvine ignores punctuation and accents
        # remove all characters that are not a letter, separator (space) or number
        # replace any "dash punctuation" with a space
        # makes sure that batman-superman and self-proclaimed stay separate words
        text = "".join(
            c if unicodedata.category(c)[0] not in "P" else " " for c in text if unicodedata.category(c)[0] in "LZNP"
        )
        # remove extra space and articles and all lower case
        text = remove_articles(text).strip()

    return text


def titles_match(search_title: str, record_title: str, threshold: int = 90) -> bool:
    import rapidfuzz.fuzz

    sanitized_search = sanitize_title(search_title)
    sanitized_record = sanitize_title(record_title)
    ratio = int(rapidfuzz.fuzz.ratio(sanitized_search, sanitized_record))
    logger.debug(
        "search title: %s ; record title: %s ; ratio: %d ; match threshold: %d",
        search_title,
        record_title,
        ratio,
        threshold,
    )
    return ratio >= threshold


def unique_file(file_name: pathlib.Path) -> pathlib.Path:
    name = file_name.stem
    counter = 1
    while True:
        if not file_name.exists():
            return file_name
        file_name = file_name.with_stem(name + " (" + str(counter) + ")")
        counter += 1


def parse_version(s: str) -> tuple[int, int, int]:
    str_parts = s.split(".")[:3]
    parts = [int(x) if x.isdigit() else 0 for x in str_parts]
    parts.extend([0] * (3 - len(parts)))  # Ensure exactly three elements in the resulting list

    return (parts[0], parts[1], parts[2])


_languages: dict[str | None, str | None] = defaultdict(lambda: None)

_countries: dict[str | None, str | None] = defaultdict(lambda: None)


def countries() -> dict[str | None, str | None]:
    if not _countries:
        import isocodes

        for alpha_2, c in isocodes.countries.by_alpha_2:
            _countries[alpha_2] = c["name"]
    return _countries


def languages() -> dict[str | None, str | None]:
    if not _languages:
        import isocodes

        for alpha_2, lng in isocodes.extendend_languages._sorted_by_index(index="alpha_2"):
            _languages[alpha_2] = lng["name"]
    return _languages


def get_language_from_iso(iso: str | None) -> str | None:
    return languages()[iso]


def get_language_iso(string: str | None) -> str | None:
    if string is None:
        return None
    import isocodes

    # Return current string if all else fails
    lang = string.casefold()

    found = None
    for lng in isocodes.extendend_languages.items:
        for x in ("alpha_2", "alpha_3", "bibliographic", "common_name", "name"):
            if x in lng and lng[x].casefold() == lang:
                found = lng
        if found:
            break

    if found:
        return found.get("alpha_2", None)
    return lang


def get_country_from_iso(iso: str | None) -> str | None:
    return countries()[iso]


def get_publisher(publisher: str) -> tuple[str, str]:
    imprint = ""

    for pub in publishers.values():
        imprint, publisher, ok = pub[publisher]
        if ok:
            break

    return imprint, publisher


def update_publishers(new_publishers: Mapping[str, Mapping[str, str]]) -> None:
    for publisher in new_publishers:
        if publisher in publishers:
            publishers[publisher].update(new_publishers[publisher])
        else:
            publishers[publisher] = ImprintDict(publisher, new_publishers[publisher])


class ImprintDict(dict):  # type: ignore
    """
    ImprintDict takes a publisher and a dict or mapping of lowercased
    imprint names to the proper imprint name. Retrieving a value from an
    ImprintDict returns a tuple of (imprint, publisher, keyExists).
    if the key does not exist the key is returned as the publisher unchanged
    """

    def __init__(self, publisher: str, mapping: tuple | Mapping = (), **kwargs: dict) -> None:  # type: ignore
        super().__init__(mapping, **kwargs)
        self.publisher = publisher

    def __missing__(self, key: str) -> None:
        return None

    def __getitem__(self, k: str) -> tuple[str, str, bool]:
        item = super().__getitem__(k.casefold())
        if k.casefold() == self.publisher.casefold():
            return "", self.publisher, True
        if item is None:
            return "", k, False
        else:
            return item, self.publisher, True

    def copy(self) -> ImprintDict:
        return ImprintDict(self.publisher, super().copy())


publishers: dict[str, ImprintDict] = {}


def load_publishers() -> None:
    try:
        update_publishers(json.loads((comicapi.data.data_path / "publishers.json").read_text("utf-8")))
    except Exception:
        logger.exception("Failed to load publishers.json; The are no publishers or imprints loaded")
