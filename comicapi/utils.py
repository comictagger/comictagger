"""Some generic utilities"""
# Copyright 2012-2014 Anthony Beville
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

import glob
import json
import logging
import os
import pathlib
import re
import unicodedata
from collections import defaultdict
from shutil import which  # noqa: F401
from typing import Any, Mapping

import pycountry
import thefuzz.fuzz

logger = logging.getLogger(__name__)


class UtilsVars:
    already_fixed_encoding = False


def get_recursive_filelist(pathlist: list[str]) -> list[str]:
    """Get a recursive list of of all files under all path items in the list"""

    filelist: list[str] = []
    for p in pathlist:

        if os.path.isdir(p):
            filelist.extend(x for x in glob.glob(f"{p}{os.sep}/**", recursive=True) if not os.path.isdir(x))
        else:
            filelist.append(p)

    return filelist


def add_to_path(dirname: str) -> None:
    if dirname is not None and dirname != "":

        # verify that path doesn't already contain the given dirname
        tmpdirname = re.escape(dirname)
        pattern = r"(^|{sep}){dir}({sep}|$)".format(dir=tmpdirname, sep=os.pathsep)

        match = re.search(pattern, os.environ["PATH"])
        if not match:
            os.environ["PATH"] = dirname + os.pathsep + os.environ["PATH"]


def xlate(data: Any, is_int: bool = False, is_float: bool = False) -> Any:
    if data is None or data == "":
        return None
    if is_int or is_float:
        i: str | int | float
        if isinstance(data, (int, float)):
            i = data
        else:
            i = str(data).translate(defaultdict(lambda: None, zip((ord(c) for c in "1234567890."), "1234567890.")))
        if i == "":
            return None
        try:
            if is_float:
                return float(i)
            return int(float(i))
        except ValueError:
            return None

    return str(data)


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
        "ms",
        "mrs",
        "mr",
        "dr",
    ]
    new_text = ""
    for word in text.split(" "):
        if word not in articles:
            new_text += word + " "

    new_text = new_text[:-1]

    return new_text


def sanitize_title(text: str, basic: bool = False) -> str:
    # normalize unicode and convert to ascii. Does not work for everything eg ½ to 1⁄2 not 1/2
    text = unicodedata.normalize("NFKD", text).casefold()
    if basic:
        # comicvine keeps apostrophes a part of the word
        text = text.replace("'", "")
        text = text.replace('"', "")
    else:
        # comicvine ignores punctuation and accents
        # remove all characters that are not a letter, separator (space) or number
        # replace any "dash punctuation" with a space
        # makes sure that batman-superman and self-proclaimed stay separate words
        text = "".join(
            c if not unicodedata.category(c) in ("Pd",) else " "
            for c in text
            if unicodedata.category(c)[0] in "LZN" or unicodedata.category(c) in ("Pd",)
        )
        # remove extra space and articles and all lower case
        text = remove_articles(text).strip()

    return text


def titles_match(search_title: str, record_title: str, threshold: int = 90) -> int:
    sanitized_search = sanitize_title(search_title)
    sanitized_record = sanitize_title(record_title)
    ratio = thefuzz.fuzz.ratio(sanitized_search, sanitized_record)
    logger.debug(
        "search title: %s ; record title: %s ; ratio: %d ; match threshold: %d",
        search_title,
        record_title,
        ratio,
        threshold,
    )
    return ratio >= threshold


def unique_file(file_name: pathlib.Path) -> pathlib.Path:
    name = file_name.name
    counter = 1
    while True:
        if not file_name.exists():
            return file_name
        file_name = file_name.with_name(name + " (" + str(counter) + ")")
        counter += 1


languages: dict[str | None, str | None] = defaultdict(lambda: None)

countries: dict[str | None, str | None] = defaultdict(lambda: None)

for c in pycountry.countries:
    if "alpha_2" in c._fields:
        countries[c.alpha_2] = c.name

for lng in pycountry.languages:
    if "alpha_2" in lng._fields:
        languages[lng.alpha_2] = lng.name


def get_language_from_iso(iso: str | None) -> str | None:
    return languages[iso]


def get_language(string: str | None) -> str | None:
    if string is None:
        return None

    lang = get_language_from_iso(string)

    if lang is None:
        try:
            return str(pycountry.languages.lookup(string).name)
        except LookupError:
            return None
    return lang


def get_publisher(publisher: str) -> tuple[str, str]:
    if publisher is None:
        return ("", "")
    imprint = ""

    for pub in publishers.values():
        imprint, publisher, ok = pub[publisher]
        if ok:
            break

    return (imprint, publisher)


def update_publishers(new_publishers: Mapping[str, Mapping[str, str]]) -> None:
    for publisher in new_publishers:
        if publisher in publishers:
            publishers[publisher].update(new_publishers[publisher])
        else:
            publishers[publisher] = ImprintDict(publisher, new_publishers[publisher])


class ImprintDict(dict):
    """
    ImprintDict takes a publisher and a dict or mapping of lowercased
    imprint names to the proper imprint name. Retrieving a value from an
    ImprintDict returns a tuple of (imprint, publisher, keyExists).
    if the key does not exist the key is returned as the publisher unchanged
    """

    def __init__(self, publisher: str, mapping: tuple | Mapping = (), **kwargs: dict) -> None:
        super().__init__(mapping, **kwargs)
        self.publisher = publisher

    def __missing__(self, key: str) -> None:
        return None

    def __getitem__(self, k: str) -> tuple[str, str, bool]:
        item = super().__getitem__(k.casefold())
        if k.casefold() == self.publisher.casefold():
            return ("", self.publisher, True)
        if item is None:
            return ("", k, False)
        else:
            return (item, self.publisher, True)

    def copy(self) -> ImprintDict:
        return ImprintDict(self.publisher, super().copy())


publishers: dict[str, ImprintDict] = {}


def load_publishers() -> None:
    try:
        update_publishers(json.loads((pathlib.Path(__file__).parent / "data" / "publishers.json").read_text("utf-8")))
    except Exception:
        logger.exception("Failed to load publishers.json; The are no publishers or imprints loaded")
