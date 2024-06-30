"""Functions for parsing comic info from filename

This should probably be re-written, but, well, it mostly works!
"""

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
#
# Some portions of this code were modified from pyComicMetaThis project
# http://code.google.com/p/pycomicmetathis/
from __future__ import annotations

import functools
import itertools
import logging
import os
import re
from operator import itemgetter
from re import Match
from typing import Protocol, TypedDict
from urllib.parse import unquote

from text2digits import text2digits

from comicapi import filenamelexer, issuestring

logger = logging.getLogger(__name__)

t2d = text2digits.Text2Digits(add_ordinal_ending=False)
t2do = text2digits.Text2Digits(add_ordinal_ending=True)

placeholders_no_dashes = [re.compile(r"[-_]"), re.compile(r"  +")]
placeholders_allow_dashes = [re.compile(r"[_]"), re.compile(r"  +")]


class FileNameParser:
    volume_regex = r"v(?:|ol|olume)\.?\s?"

    def __init__(self) -> None:
        self.series = ""
        self.volume = ""
        self.year = ""
        self.issue_count = ""
        self.remainder = ""
        self.issue = ""

    def repl(self, m: Match[str]) -> str:
        return " " * len(m.group())

    def fix_spaces(self, string: str, remove_dashes: bool = True) -> str:
        if remove_dashes:
            placeholders = placeholders_no_dashes
        else:
            placeholders = placeholders_allow_dashes
        for ph in placeholders:
            string = re.sub(ph, self.repl, string)
        return string

    def get_issue_count(self, filename: str, issue_end: int) -> str:
        count = ""
        filename = filename[issue_end:]

        # replace any name separators with spaces
        tmpstr = self.fix_spaces(filename)

        match = re.search(r"\s\(?of\s(\d+)[ )]", tmpstr, re.IGNORECASE)
        if match:
            count = match.group(1)

        return count.lstrip("0")

    def get_issue_number(self, filename: str) -> tuple[str, int, int]:
        """Returns a tuple of issue number string, and start and end indexes in the filename
        (The indexes will be used to split the string up for further parsing)
        """

        found = False
        issue = ""
        start = 0
        end = 0

        # first, look for multiple "--", this means it's formatted differently
        # from most:
        if "--" in filename:
            # the pattern seems to be that anything to left of the first "--"
            # is the series name followed by issue
            filename = re.sub(r"--.*", self.repl, filename)

        elif "__" in filename and not re.search(r"\[__\d+__]", filename):
            # the pattern seems to be that anything to left of the first "__"
            # is the series name followed by issue
            filename = re.sub(r"__.*", self.repl, filename)

        filename = filename.replace("+", " ")

        # replace parenthetical phrases with spaces
        filename = re.sub(r"\(.*?\)", self.repl, filename)
        filename = re.sub(r"\[.*?]", self.repl, filename)

        # replace any name separators with spaces
        filename = self.fix_spaces(filename)

        # remove any "of NN" phrase with spaces (problem: this could break on
        # some titles)
        filename = re.sub(r"of \d+", self.repl, filename)

        # we should now have a cleaned up filename version with all the words in
        # the same positions as original filename

        # search for volume number
        match = re.search(self.volume_regex + r"(\d+)", filename, re.IGNORECASE)
        if match:
            self.volume = match.group(1)

        # make a list of each word and its position
        word_list = []
        for m in re.finditer(r"\S+", filename):
            word_list.append((m.group(0), m.start(), m.end()))

        # remove the first word, since it shouldn't be the issue number
        if len(word_list) > 1:
            word_list = word_list[1:]
        else:
            # only one word? Check to see if there is a digit, if so use it as the issue number and the series
            if any(char.isnumeric() for char in word_list[0][0]):
                issue = word_list[0][0].removeprefix("#")
            return issue, word_list[0][1], word_list[0][2]

        # Now try to search for the likely issue number word in the list

        # first look for a word with "#" followed by digits with optional suffix
        # this is almost certainly the issue number
        for w in reversed(word_list):
            if re.match(r"#-?((\d*\.\d+|\d+)(\w*))", w[0]):
                found = True
                break

        # same as above but w/o a '#', and only look at the last word in the
        # list
        if not found:
            w = word_list[-1]
            if re.match(r"-?((\d*\.\d+|\d+)(\w*))", w[0]):
                found = True

        # now try to look for a # followed by any characters
        if not found:
            for w in reversed(word_list):
                if re.match(r"#\S+", w[0]):
                    found = True
                    break

        if found:
            issue = w[0]
            start = w[1]
            end = w[2]
            if issue[0] == "#":
                issue = issue[1:]

        return issue, start, end

    def get_series_name(self, filename: str, issue_start: int) -> tuple[str, str]:
        """Use the issue number string index to split the filename string"""

        if issue_start != 0:
            filename = filename[:issue_start]
        else:
            filename = filename.lstrip("#")

        # in case there is no issue number, remove some obvious stuff
        if "--" in filename:
            # the pattern seems to be that anything to left of the first "--" is the series name followed by issue
            filename = re.sub(r"--.*", self.repl, filename)
            # never happens

        elif "__" in filename:
            # the pattern seems to be that anything to left of the first "__" is the series name followed by issue
            filename = re.sub(r"__.*", self.repl, filename)
            # never happens

        filename = filename.replace("+", " ")
        tmpstr = self.fix_spaces(filename, remove_dashes=False)

        series = tmpstr
        volume = ""

        # save the last word
        split = series.split()
        if split:
            last_word = split[-1]
        else:
            last_word = ""

        # remove any parenthetical phrases
        series = re.sub(r"\(.*?\)", "", series)

        # search for volume number
        match = re.search(r"(.+)" + self.volume_regex + r"(\d+)", series, re.IGNORECASE)
        if match:
            series = match.group(1)
            volume = match.group(2)
        if self.volume:
            volume = self.volume

        # if a volume wasn't found, see if the last word is a year in parentheses
        # since that's a common way to designate the volume
        if volume == "":
            # match either (YEAR), (YEAR-), or (YEAR-YEAR2)
            match = re.search(r"(\()(\d{4})(-(\d{4}|)|)(\))", last_word)
            if match:
                volume = match.group(2)

        series = series.strip()

        # if we don't have an issue number (issue_start==0), look
        # for hints i.e. "TPB", "one-shot", "OS", "OGN", etc that might
        # be removed to help search online
        if issue_start == 0:
            one_shot_words = ["tpb", "os", "one-shot", "ogn", "gn"]
            split = series.split()
            if split:
                last_word = split[-1]
                if last_word.casefold() in one_shot_words:
                    series, _, _ = series.rpartition(" ")

        if volume:
            series = re.sub(r"\s+v(|ol|olume)$", "", series)

        return series.strip().strip("-_.").strip(), volume.strip()

    def get_year(self, filename: str, issue_end: int) -> str:
        filename = filename[issue_end:]

        year = ""
        # look for four digit number with "(" ")" or "--" around it
        match = re.search(r"(\(\d{4}\))|(--\d{4}--)", filename)
        if match:
            year = match.group()
            # remove non-digits
            year = re.sub(r"\D", "", year)
        return year

    def get_remainder(self, filename: str, year: str, count: str, volume: str, issue_end: int) -> str:
        """Make a guess at where the the non-interesting stuff begins"""

        remainder = ""

        if "--" in filename:
            remainder = "--".join(filename.split("--", 1)[1:])
        elif "__" in filename:
            remainder = "__".join(filename.split("__", 1)[1:])
        elif issue_end != 0:
            remainder = filename[issue_end:]

        remainder = self.fix_spaces(remainder, remove_dashes=False)
        if volume != "":
            remainder = re.sub(r"(?i)(.+)(v(?:|ol|olume)\.?\s?)" + volume, "", remainder, count=1)
        if year != "":
            remainder = remainder.replace(year, "", 1)
        if count != "":
            remainder = remainder.replace("of " + count, "", 1)

        remainder = remainder.replace("()", "")
        remainder = remainder.replace("  ", " ")  # cleans some whitespace mess

        return remainder.strip()

    def parse_filename(self, filename: str) -> None:
        # remove the path
        filename = os.path.basename(filename)

        # remove the extension
        filename = os.path.splitext(filename)[0]

        # url decode, just in case
        filename = unquote(filename)

        # sometimes archives get messed up names from too many decodes
        # often url encodings will break and leave "_28" and "_29" in place
        # of "(" and ")"  see if there are a number of these, and replace them
        if filename.count("_28") > 1 and filename.count("_29") > 1:
            filename = filename.replace("_28", "(")
            filename = filename.replace("_29", ")")

        self.issue, issue_start, issue_end = self.get_issue_number(filename)
        self.series, self.volume = self.get_series_name(filename, issue_start)

        if self.issue == "":
            self.issue = self.volume

        # provides proper value when the filename doesn't have a issue number
        if issue_end == 0:
            issue_end = len(self.series)

        self.year = self.get_year(filename, issue_end)
        self.issue_count = self.get_issue_count(filename, issue_end)
        self.remainder = self.get_remainder(filename, self.year, self.issue_count, self.volume, issue_end)

        if self.volume != "":
            self.volume = issuestring.IssueString(self.volume).as_string()
        if self.issue != "":
            self.issue = issuestring.IssueString(self.issue).as_string()


class FilenameInfo(TypedDict):
    alternate: str
    annual: bool
    archive: str
    c2c: bool
    fcbd: bool
    issue: str
    issue_count: str
    publisher: str
    remainder: str
    series: str
    title: str
    volume: str
    volume_count: str
    year: str
    format: str


protofolius_issue_number_scheme = {
    "B": "biography/best of",
    "C": "compact edition",
    "E": "entertainment/puzzle edition",
    "F": "familiy book edition",
    "J": "jubileum (anniversary) edition",
    "P": "pocket edition",
    "N": "newly brought out/restyled edition",
    "O": "old editions (or oblong format)",
    "S": "special edition",
    "X": "X-rated edition",
}


class ParserFunc(Protocol):
    def __call__(self, __origin: Parser) -> ParserFunc | None: ...


eof = filenamelexer.Item(filenamelexer.ItemType.EOF, -1, "")


# Extracted and mutilated from https://github.com/lordwelch/wsfmt
# Which was extracted and mutilated from https://github.com/golang/go/tree/master/src/text/template/parse
class Parser:
    """docstring for FilenameParser"""

    def __init__(
        self,
        lexer_result: list[filenamelexer.Item],
        first_is_alt: bool = False,
        remove_c2c: bool = False,
        remove_fcbd: bool = False,
        remove_publisher: bool = False,
        protofolius_issue_number_scheme: bool = False,
    ) -> None:
        self.state: ParserFunc | None = None
        self.pos = -1

        self.firstItem = True
        self.skip = False
        self.alt = False
        self.filename_info = FilenameInfo(
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
        self.issue_number_at = None
        self.issue_number_marked = False
        self.issue_number_passed = False
        self.in_something = 0  # In some sort of brackets {}[]()
        self.in_brace = 0  # In {}
        self.in_s_brace = 0  # In []
        self.in_paren = 0  # In ()
        self.year_candidates: list[tuple[bool, bool, filenamelexer.Item]] = []
        self.series: list[list[filenamelexer.Item]] = []
        self.series_parts: list[filenamelexer.Item] = []
        self.title_parts: list[filenamelexer.Item] = []
        self.used_items: list[filenamelexer.Item] = []
        self.irrelevant: list[filenamelexer.Item] = []
        self.operator_rejected: list[filenamelexer.Item] = []
        self.publisher_removed: list[filenamelexer.Item] = []

        self.first_is_alt = first_is_alt
        self.remove_c2c = remove_c2c
        self.remove_fcbd = remove_fcbd
        self.remove_publisher = remove_publisher
        self.protofolius_issue_number_scheme = protofolius_issue_number_scheme

        self.remove_from_remainder = []
        if remove_c2c:
            self.remove_from_remainder.append(filenamelexer.ItemType.C2C)
        if remove_fcbd:
            self.remove_from_remainder.append(filenamelexer.ItemType.FCBD)

        self.input = lexer_result
        self.error = None
        for i, item in list(enumerate(self.input)):
            if item.typ == filenamelexer.ItemType.IssueNumber:
                self.issue_number_at = i
                self.issue_number_marked = True
            if item.typ == filenamelexer.ItemType.Error:
                self.error = item
                self.input.remove(self.error)

    # Get returns the next Item in the input.
    def get(self) -> filenamelexer.Item:
        if int(self.pos) >= len(self.input) - 1:
            self.pos += 1
            return eof

        self.pos += 1
        return self.input[self.pos]

    # Peek returns but does not consume the next Item in the input.
    def peek(self, length: int = 1) -> filenamelexer.Item:
        if int(self.pos) + length >= len(self.input):
            return eof

        return self.input[self.pos + length]

    # Peek_back returns but does not step back the previous Item in the input.
    def peek_back(self, length: int = 1) -> filenamelexer.Item:
        if int(self.pos) - length < 0:
            return eof

        return self.input[self.pos - length]

    # Backup steps back one Item.
    def backup(self) -> None:
        self.pos -= 1

    def run(self) -> None:
        self.state = parse
        while self.state is not None:
            self.state = self.state(self)


def parse(p: Parser) -> ParserFunc:
    item: filenamelexer.Item = p.get()
    # We're done, time to do final processing
    if item.typ == filenamelexer.ItemType.EOF:
        return parse_finish

    # Need to figure out if this is the issue number
    if item.typ == filenamelexer.ItemType.Number:
        likely_year = False
        likely_issue_number = True
        if p.firstItem and p.first_is_alt:
            p.alt = True
            p.firstItem = False
            return parse_issue_number

        # Issue number is not 4 digits e.g. a year
        # If this is still used in 7978 years, something is terribly wrong
        if len(item.val.lstrip("0")) < 4:
            # Assume that operators indicate a non-issue number e.g. IG-88 or 88-IG
            if filenamelexer.ItemType.Operator not in (p.peek().typ, p.peek_back().typ):
                # It is common to use '89 to refer to an annual reprint from 1989
                if item.val[0] != "'":
                    # An issue number starting with # Was not found and no previous number was found
                    if p.issue_number_at is None:
                        # Series has already been started/parsed,
                        # filters out leading alternate numbers leading alternate number
                        if len(p.series) > 0:
                            return parse_issue_number
            else:
                p.operator_rejected.append(item)
                # operator rejected used later to add back to the series/title
        # It is more likely to be a year if it is inside parentheses.
        if p.in_something > 0:
            likely_year = len(item.val.lstrip("0")) == 4
            likely_issue_number = not likely_year

        # If numbers are directly followed by text it most likely isn't a year e.g. 2048px
        if p.peek().typ == filenamelexer.ItemType.Text:
            likely_year = False
            likely_issue_number = p.in_something == 0

        # Is either a full year '2001' or a short year "'89"
        if len(item.val.lstrip("0")) == 4 or item.val[0] == "'":
            series = " ".join([x.val for x in (p.series[-1] if p.series else [])])
            if p.series and series.casefold().endswith("free comic book day"):
                likely_issue_number = False

            # Look for a full date as in 2022-04-22
            if p.peek().typ in [
                filenamelexer.ItemType.Symbol,
                filenamelexer.ItemType.Operator,
                filenamelexer.ItemType.Dot,
            ]:
                op = [p.get()]
                if p.peek().typ == filenamelexer.ItemType.Number:
                    month = p.get()
                    if p.peek().typ in [
                        filenamelexer.ItemType.Symbol,
                        filenamelexer.ItemType.Operator,
                        filenamelexer.ItemType.Dot,
                    ]:
                        op.append(p.get())
                        if p.peek().typ == filenamelexer.ItemType.Number:
                            likely_issue_number = False
                            day = p.get()
                            fulldate = [month, day, item]
                            p.used_items.extend(op)
                            p.used_items.extend(fulldate)
                        else:
                            p.backup()
                            p.backup()
                            p.backup()
                            # TODO never happens
                    else:
                        p.backup()
                        p.backup()
                        # TODO never happens
                else:
                    p.backup()
                    # TODO never happens

            likely_issue_number = likely_issue_number and item.val[0] != "'"
            p.year_candidates.append((likely_year, likely_issue_number, item))
            if p.in_something == 0:
                # Append to series in case it is a part of the title, but only if were not inside parenthesis
                if not p.series:
                    p.series.append([])
                p.series[-1].append(item)

                # We would use i=item but we want to force a split after year candidates
                return functools.partial(parse_series, i=None)
        # Ensures that IG-88 gets added back to the series/title
        else:
            if p.in_something == 0:
                #  We're not in something add it to the series
                return functools.partial(parse_series, i=item)

    # Number with a leading hash e.g. #003
    elif item.typ == filenamelexer.ItemType.IssueNumber:
        # Unset first item
        if p.firstItem:
            p.firstItem = False
        p.issue_number_passed = True
        return parse_issue_number

    # Matches FCBD. Not added to p.used_items so it will show in "remainder"
    elif item.typ == filenamelexer.ItemType.FCBD:
        p.filename_info["fcbd"] = True

    # Matches c2c. Not added to p.used_items so it will show in "remainder"
    elif item.typ == filenamelexer.ItemType.C2C:
        p.filename_info["c2c"] = True

    # Matches the extension if it is known to be an archive format e.g. cbt,cbz,zip,rar
    elif item.typ == filenamelexer.ItemType.ArchiveType:
        p.filename_info["archive"] = item.val.casefold()
        if p.peek_back().typ == filenamelexer.ItemType.Dot:
            p.used_items.append(p.peek_back())
        p.used_items.append(item)

    # Allows removing DC from 'Wonder Woman 49 DC Sep-Oct 1951'
    # dependent on publisher being in a static list in the lexer
    elif item.typ == filenamelexer.ItemType.Publisher:
        p.filename_info["publisher"] = item.val
        p.used_items.append(item)
        if p.firstItem:
            p.firstItem = False
            if p.in_something == 0:
                return functools.partial(parse_series, i=item)
        p.publisher_removed.append(item)
        if p.in_something == 0:
            return functools.partial(parse_series, i=item)

    # Attempts to identify the type e.g. annual
    elif item.typ == filenamelexer.ItemType.ComicType:
        series_append = True

        if p.peek().typ == filenamelexer.ItemType.Space:
            p.get()

        if p.peek().typ == filenamelexer.ItemType.Number or (
            p.peek().typ == filenamelexer.ItemType.Text and t2d.convert(p.peek().val).isnumeric()
        ):
            number = p.get()
            # Mark volume info. Text will be added to the title/series later
            if item.val.casefold() in ["tpb"]:
                # p.title_parts.extend([item, number])
                p.filename_info["volume"] = t2do.convert(number.val)
                p.filename_info["issue"] = t2do.convert(number.val)

                p.used_items.append(item)
                series_append = False

            # Annuals usually mean the year
            elif item.val.casefold() in ["annual"]:
                p.filename_info["annual"] = True
                num = t2d.convert(number.val)
                if num.isnumeric() and len(num) == 4:
                    p.year_candidates.append((True, False, number))
                else:
                    p.backup()

        elif item.val.casefold() in ["annual"]:
            p.filename_info["annual"] = True

        # If we don't have a reason to exclude it from the series go back to parsing the series immediately
        if series_append:
            p.used_items.append(item)
            if p.firstItem:
                p.firstItem = False
            return functools.partial(parse_series, i=item)

    # We found text, it's probably the title or series
    elif item.typ in [filenamelexer.ItemType.Text, filenamelexer.ItemType.Honorific]:
        # Unset first item
        if p.firstItem:
            p.firstItem = False
        if p.in_something == 0 and not p.skip:
            p.backup()
            return functools.partial(parse_series, i=None)

    # Usually the word 'of' eg 1 (of 6)
    elif item.typ == filenamelexer.ItemType.InfoSpecifier:
        if p.firstItem:
            p.firstItem = False
        return parse_info_specifier

    # Operator is a symbol that acts as some sort of separator eg - : ;
    elif item.typ == filenamelexer.ItemType.Operator:
        if p.in_something == 0:
            p.irrelevant.append(item)

    # Filter out Month and day names in filename
    elif item.typ == filenamelexer.ItemType.Calendar:
        # Month and day are currently irrelevant if they are inside parentheses e.g. (January 2002)
        if p.in_something > 0:
            p.irrelevant.append(item)

        # assume Sep-Oct is not useful in the series/title
        elif p.peek().typ in [filenamelexer.ItemType.Symbol, filenamelexer.ItemType.Operator]:
            p.get()
            if p.peek().typ == filenamelexer.ItemType.Calendar:
                p.irrelevant.extend([item, p.input[p.pos], p.get()])
            else:
                p.backup()
                if p.firstItem:
                    p.firstItem = False
                return functools.partial(parse_series, i=item)
        # This is text that just happens to also be a month/day
        else:
            p.get()
            if p.firstItem:
                p.firstItem = False
            return functools.partial(parse_series, i=item)

    # Specifically '__' or '--', no further title/series parsing is done to keep compatibility with wiki
    elif item.typ == filenamelexer.ItemType.Skip:
        p.skip = True

    # Keeping track of parentheses depth
    elif item.typ == filenamelexer.ItemType.LeftParen:
        p.in_paren += 1
        p.in_something += 1
    elif item.typ == filenamelexer.ItemType.LeftBrace:
        p.in_brace += 1
        p.in_something += 1
    elif item.typ == filenamelexer.ItemType.LeftSBrace:
        p.in_s_brace += 1
        p.in_something += 1

    elif item.typ == filenamelexer.ItemType.RightParen:
        p.in_paren -= 1
        p.in_something -= 1
    elif item.typ == filenamelexer.ItemType.RightBrace:
        p.in_brace -= 1
        p.in_something -= 1
    elif item.typ == filenamelexer.ItemType.RightSBrace:
        p.in_s_brace -= 1
        p.in_something -= 1

    # Unset first item
    if p.firstItem:
        p.firstItem = False

    # Brace management, I don't like negative numbers
    if p.in_paren < 0:
        p.in_something += p.in_paren * -1
    if p.in_brace < 0:
        p.in_something += p.in_brace * -1
    if p.in_s_brace < 0:
        p.in_something += p.in_s_brace * -1

    return parse


# TODO: What about more esoteric numbers???
def parse_issue_number(p: Parser) -> ParserFunc:
    item = p.input[p.pos]

    if p.filename_info["issue"]:
        if p.filename_info["alternate"]:
            p.filename_info["alternate"] += "," + item.val
        p.filename_info["alternate"] = item.val
    else:
        if p.alt:
            p.filename_info["alternate"] = item.val
        else:
            p.filename_info["issue"] = item.val
            p.issue_number_at = item.pos
        p.used_items.append(item)

        if p.peek().typ == filenamelexer.ItemType.Dot:
            p.used_items.append(p.get())  # Add the Dot to used items
            if p.peek().typ in [filenamelexer.ItemType.Text, filenamelexer.ItemType.Number]:
                item = p.get()
                if p.alt:
                    p.filename_info["alternate"] += "." + item.val
                else:
                    p.filename_info["issue"] += "." + item.val
                p.used_items.append(item)
            else:
                p.backup()  # We don't use the Dot so don't consume it
                p.used_items.pop()  # we also don't add it to used items

    p.alt = False
    return parse


# i=None is a split in the series
def parse_series(p: Parser, i: filenamelexer.Item | None) -> ParserFunc:
    current = []
    prev_space = False

    issue_marked_or_passed = (
        p.issue_number_marked and p.issue_number_passed or p.issue_number_at is not None and not p.issue_number_marked
    )

    if i:
        if not issue_marked_or_passed:
            if p.series:
                current = p.series.pop()
        current.append(i)
    else:
        # If we are splitting we don't want to sart with these
        while p.peek().typ in [
            filenamelexer.ItemType.Space,
            filenamelexer.ItemType.Operator,
            filenamelexer.ItemType.Symbol,
        ]:
            p.irrelevant.append(p.get())

    # Skip is only true if we have come across '--' or '__'
    while not p.skip:
        item = p.get()

        # Spaces are evil
        if item.typ == filenamelexer.ItemType.Space:
            prev_space = True
            continue
        if item.typ in [
            filenamelexer.ItemType.Text,
            filenamelexer.ItemType.Symbol,
            filenamelexer.ItemType.Publisher,
            filenamelexer.ItemType.Honorific,
        ]:
            current.append(item)
            if p.peek().typ == filenamelexer.ItemType.Dot:
                dot = p.get()
                if item.typ == filenamelexer.ItemType.Honorific or (
                    p.peek().typ == filenamelexer.ItemType.Space
                    and item.typ in (filenamelexer.ItemType.Text, filenamelexer.ItemType.Publisher)
                ):
                    current.append(dot)
                else:
                    p.backup()
            if item.typ == filenamelexer.ItemType.Publisher:
                p.filename_info["publisher"] = item.val

        # Handle Volume
        elif item.typ == filenamelexer.ItemType.InfoSpecifier:
            # Exception for 'of'
            if item.val.casefold() == "of":
                current.append(item)
            else:
                # This specifically lets 'X-Men-V1-067' parse correctly as Series: X-Men Volume: 1 Issue: 67
                while len(current) > 0 and current[-1].typ not in [
                    filenamelexer.ItemType.Text,
                    filenamelexer.ItemType.Symbol,
                ]:
                    p.irrelevant.append(current.pop())
                p.backup()
                break

        elif item.typ == filenamelexer.ItemType.Operator:
            peek = p.peek()
            # ': ' separates the title from the series, only the last section is considered the title
            if not prev_space and peek.typ in [filenamelexer.ItemType.Space]:
                current.append(item)
                break
            else:
                # Force space around '-' makes 'batman - superman' stay otherwise we get 'batman-superman'
                if prev_space and peek.typ in [filenamelexer.ItemType.Space]:
                    item.val = " " + item.val + " "
                current.append(item)

        # Stop processing series/title if a skip item is found
        elif item.typ == filenamelexer.ItemType.Skip:
            p.backup()
            break

        elif item.typ == filenamelexer.ItemType.Number:
            # Special case for the word 'book'
            if current and current[-1].val.casefold() == "book":
                # Mark the volume
                p.filename_info["volume"] = t2do.convert(item.val)

                # Add this section to the series EG [['bloodshot', 'book']]
                p.series.append(current)
                # Pop the last item and break to end this section EG [['bloodshot'], ['book', '3']]
                current = [current.pop(), item]
                break

            count = get_number(p, p.pos + 1)
            # this is an issue or volume number eg '1 of 2'
            if count is not None:
                p.backup()
                break

            if p.peek().typ == filenamelexer.ItemType.Space:
                p.get()
                # We have 2 numbers, add the first to the series and then go back to parse
                if p.peek().typ in [filenamelexer.ItemType.Number, filenamelexer.ItemType.IssueNumber]:
                    current.append(item)
                    break

                # the issue number has been marked and passed, keep it as a part of the series
                if issue_marked_or_passed:
                    # We already have an issue number, this should be a part of the series
                    current.append(item)
                else:
                    # We have 1 number break here, it's possible it's the issue
                    p.backup()  # Whitespace
                    p.backup()  # The number
                    break

            # We have 1 number break here, it's possible it's the issue
            else:
                # the issue number has been #marked or passed, keep it as a part of the series
                if issue_marked_or_passed:
                    # We already have an issue number, this should be a part of the series
                    current.append(item)
                else:
                    p.backup()  # The number
                    break

        else:
            # Ensure 'ms. marvel' parses 'ms.' correctly
            if item.typ == filenamelexer.ItemType.Dot:
                if p.peek_back().typ == filenamelexer.ItemType.Honorific:
                    current.append(item)
                elif (
                    p.peek().typ == filenamelexer.ItemType.Number
                    or p.peek_back().typ == filenamelexer.ItemType.Text
                    and len(p.peek_back().val) == 1
                ):
                    current.append(item)
                    item.no_space = True
                # Allows avengers.hulk to parse correctly
                elif p.peek().typ in (filenamelexer.ItemType.Text,):
                    # Marks the dot as used so that the remainder is clean
                    p.used_items.append(item)
            else:
                p.backup()
                break

        prev_space = False
    if (
        current
        and current[-1].typ == filenamelexer.ItemType.Dot
        and p.peek().typ in (filenamelexer.ItemType.ArchiveType,)
    ):
        current.pop()
    p.series.append(current)
    return parse


def resolve_year(p: Parser) -> None:
    if len(p.year_candidates) > 0:
        # Sort by likely_year boolean
        p.year_candidates.sort(key=itemgetter(0))

        if not p.filename_info["issue"]:
            year = p.year_candidates.pop(0)
            if year[1]:
                p.filename_info["issue"] = year[2].val
                p.used_items.append(year[2])
                # Remove year from series and title
                if year[2] in p.series_parts:
                    p.series_parts.remove(year[2])
                if year[2] in p.title_parts:
                    p.title_parts.remove(year[2])
                if not p.year_candidates:
                    return
            else:
                p.year_candidates.insert(0, year)

        # Take the last year e.g. (2007) 2099 (2008) becomes 2099 2007 2008 and takes 2008
        selected_year = p.year_candidates.pop()

        p.filename_info["year"] = selected_year[2].val
        p.used_items.append(selected_year[2])

        # (2008) Title (2009) is many times used to denote the series year if we don't have a volume we use it
        if not p.filename_info["volume"] and p.year_candidates and p.year_candidates[-1][0]:
            year = p.year_candidates[-1]
            if year[2] not in p.series_parts and year[2] not in p.title_parts:
                vol = p.year_candidates.pop()[2]
                p.filename_info["volume"] = vol.val
                p.used_items.append(vol)

                # Remove volume from series and title
                # note: this never happens
                if vol in p.series_parts:
                    p.series_parts.remove(vol)
                if vol in p.title_parts:
                    p.title_parts.remove(vol)

        # Remove year from series and title
        if selected_year[2] in p.series_parts:
            p.series_parts.remove(selected_year[2])
        if selected_year[2] in p.title_parts:
            p.title_parts.remove(selected_year[2])


def resolve_issue(p: Parser) -> None:
    # If we don't have an issue try to find it in the series
    if not p.filename_info["issue"] and p.series_parts and p.series_parts[-1].typ == filenamelexer.ItemType.Number:
        issue_num = p.series_parts.pop()

        # If the number we just popped is a year put it back on it's probably part of the series e.g. Spider-Man 2099
        if issue_num in [x[2] for x in p.year_candidates]:
            p.series_parts.append(issue_num)
        else:
            # If this number was rejected because of an operator and the operator is still there add it back
            # e.g. 'IG-88'
            if (
                issue_num in p.operator_rejected
                and p.series_parts
                and p.series_parts[-1].typ == filenamelexer.ItemType.Operator
            ):
                p.series_parts.append(issue_num)
            # We have no reason to not use this number as the issue number.
            # Specifically happens when parsing 'X-Men-V1-067.cbr'
            else:
                p.filename_info["issue"] = issue_num.val
                p.used_items.append(issue_num)
                p.issue_number_at = issue_num.pos

    if p.filename_info["issue"]:
        p.filename_info["issue"] = issuestring.IssueString(p.filename_info["issue"].lstrip("#")).as_string()

    if p.filename_info["volume"]:
        p.filename_info["volume"] = p.filename_info["volume"].lstrip("#").lstrip("0")

    if not p.filename_info["issue"]:
        # We have an alternate move it to the issue
        if p.filename_info["alternate"]:
            p.filename_info["issue"] = p.filename_info["alternate"]
            p.filename_info["alternate"] = ""

        if p.filename_info["volume"]:
            p.filename_info["issue"] = p.filename_info["volume"]

    if (
        p.filename_info["issue"]
        and p.protofolius_issue_number_scheme
        and len(p.filename_info["issue"]) > 1
        and p.filename_info["issue"][0].isalpha()
        and p.filename_info["issue"][0].upper() in protofolius_issue_number_scheme
        and p.filename_info["issue"][1].isnumeric()
    ):
        p.filename_info["format"] = protofolius_issue_number_scheme[p.filename_info["issue"][0].upper()]


def split_series(items: list[list[filenamelexer.Item]]) -> tuple[list[filenamelexer.Item], list[filenamelexer.Item]]:
    series_parts: list[list[filenamelexer.Item]] = []
    title_parts: list[list[filenamelexer.Item]] = []
    current = series_parts
    # We probably have a title
    if len(items) > 1:
        for i, s in enumerate(items):
            # Switch to title if we are on the last part
            if i == len(items) - 1:
                current = title_parts
            if s:
                current.append(s)
                if s[-1].typ == filenamelexer.ItemType.Operator:
                    s[-1].val += " "  # Ensures that when there are multiple separators that they display properly
                else:  # We don't have an operator separating the parts, it's probably an issue number
                    current = title_parts
    else:
        if items:
            series_parts.extend(items)

    series: list[filenamelexer.Item] = list(itertools.chain.from_iterable(series_parts))
    title: list[filenamelexer.Item] = list(itertools.chain.from_iterable(title_parts))
    if series and series[-1].typ == filenamelexer.ItemType.Operator:
        series.pop()
    return series, title


def parse_finish(p: Parser) -> None:
    for part in p.series:
        p.used_items.extend(part)
    p.series_parts, p.title_parts = split_series(p.series)

    resolve_year(p)
    resolve_issue(p)

    # Remove publishers, currently only marvel and dc are defined,
    # this is an option specifically because this can drastically screw up parsing
    if p.remove_publisher:
        for item in p.publisher_removed:
            if item in p.series_parts:
                p.series_parts.remove(item)
            if item in p.title_parts:
                p.title_parts.remove(item)

    p.filename_info["series"] = p.filename_info.get("issue", "")
    if p.series_parts:
        p.filename_info["series"] = join_title(p.series_parts)

    if "free comic book" in p.filename_info["series"].casefold():
        p.filename_info["fcbd"] = True

    p.filename_info["title"] = join_title(p.title_parts)

    p.irrelevant.extend([x for x in p.input if x.typ in p.remove_from_remainder])

    p.filename_info["remainder"] = get_remainder(p)

    return None


def get_remainder(p: Parser) -> str:
    remainder = ""
    rem = []

    # Remove used items and irrelevant items e.g. the series and useless operators
    inp = [x for x in p.input if x not in p.irrelevant and x not in p.used_items]
    for i, item in enumerate(inp):
        # No double space or space next to parentheses
        if item.typ in [filenamelexer.ItemType.Space, filenamelexer.ItemType.Skip]:
            if (
                i > 0
                and inp[i - 1].typ
                not in [
                    filenamelexer.ItemType.Space,
                    filenamelexer.ItemType.LeftBrace,
                    filenamelexer.ItemType.LeftParen,
                    filenamelexer.ItemType.LeftSBrace,
                ]
                and i + 1 < len(inp)
                and inp[i + 1].typ
                not in [
                    filenamelexer.ItemType.RightBrace,
                    filenamelexer.ItemType.RightParen,
                    filenamelexer.ItemType.RightSBrace,
                ]
            ):
                remainder += " "

        # Strip off useless opening parenthesis
        elif (
            item.typ
            in [
                filenamelexer.ItemType.RightBrace,
                filenamelexer.ItemType.RightParen,
                filenamelexer.ItemType.RightSBrace,
            ]
            and i > 0
            and inp[i - 1].typ
            in [filenamelexer.ItemType.LeftBrace, filenamelexer.ItemType.LeftParen, filenamelexer.ItemType.LeftSBrace]
        ):
            remainder = remainder.rstrip("[{(")
            continue

        # Add the next item
        else:
            rem.append(item)
            remainder += item.val

    # Remove empty parentheses
    remainder = re.sub(r"[\[{(]+[]})]+", "", remainder)
    return remainder.strip().rstrip("[{(")


def parse_info_specifier(p: Parser) -> ParserFunc:
    item = p.input[p.pos]
    index = p.pos

    if p.peek().typ == filenamelexer.ItemType.Space:
        p.get()

    # Handles 'volume 3' and 'volume three'
    if p.peek().typ == filenamelexer.ItemType.Number or (
        p.peek().typ == filenamelexer.ItemType.Text and t2d.convert(p.peek().val).isnumeric()
    ):
        number = p.get()
        if item.val.casefold() in ["volume", "vol", "vol.", "v"]:
            p.filename_info["volume"] = t2do.convert(number.val)
            p.used_items.append(item)
            p.used_items.append(number)

        # 'of' is only special if it is inside a parenthesis.
        elif item.val.casefold() == "of":
            i = get_number_rev(p, index)
            if i is not None:
                if p.in_something > 0:
                    if p.issue_number_at is None:
                        # TODO: Figure out what to do here if it ever happens
                        p.filename_info["issue_count"] = str(int(t2do.convert(number.val)))
                        p.used_items.append(item)
                        p.used_items.append(number)

                    # This is definitely the issue number
                    elif p.issue_number_at == i.pos:
                        p.filename_info["issue_count"] = str(int(t2do.convert(number.val)))
                        p.used_items.append(item)
                        p.used_items.append(number)

                    # This is not for the issue number
                    # assume it is the volume number and count, remove from series
                    elif p.issue_number_at != i.pos:
                        p.filename_info["volume"] = i.val
                        p.filename_info["volume_count"] = str(int(t2do.convert(number.val)))
                        for part in p.series:
                            if i in part:
                                part.remove(i)
                                break
                        p.used_items.append(i)
                        p.used_items.append(item)
                        p.used_items.append(number)
                    else:
                        # TODO: Figure out what to do here if it ever happens
                        pass
                else:
                    # Resets back to '1' in  'The Wrath of Foobar-Man, Part 1 of 2'
                    # we then go to parse_series it adds i (the '1') and then continues parsing at of
                    p.pos = [ind for ind, x in enumerate(p.input) if x == i][0]

            if not p.in_something:
                return functools.partial(parse_series, i=i)
    return parse


# Gets 03 in '03 of 6'
def get_number_rev(p: Parser, index: int) -> filenamelexer.Item | None:
    # Go backward through the filename to see if we can find what this is of eg '03 (of 6)' or '008 title 03 (of 6)'
    rev = p.input[:index]
    rev.reverse()
    for i in rev:
        # We don't care about these types, we are looking to see if there is a number that is possibly different from
        # the issue number for this count
        if i.typ in [
            filenamelexer.ItemType.LeftParen,
            filenamelexer.ItemType.LeftBrace,
            filenamelexer.ItemType.LeftSBrace,
            filenamelexer.ItemType.Space,
        ]:
            continue
        if i.typ in [filenamelexer.ItemType.Number, filenamelexer.ItemType.IssueNumber]:
            # We got our number, time to leave
            return i
        # This is not a number and not an ignorable type, give up looking for the number this count belongs to
        break

    return None


# Gets 6 in '03 of 6'
def get_number(p: Parser, index: int) -> filenamelexer.Item | None:
    # Go forward through the filename to see if we can find what this is of eg '03 (of 6)' or '008 title 03 (of 6)'
    filename = p.input[index:]
    of_found = False

    for i in filename:
        # We don't care about these types, we are looking to see if there is a number that is possibly different from
        # the issue number for this count
        if i.typ in [
            filenamelexer.ItemType.LeftParen,
            filenamelexer.ItemType.LeftBrace,
            filenamelexer.ItemType.LeftSBrace,
            filenamelexer.ItemType.Space,
        ]:
            continue
        if i.val == "of":
            of_found = True
            continue
        if i.typ in [filenamelexer.ItemType.Number, filenamelexer.ItemType.IssueNumber]:
            # We got our number, time to leave
            if of_found:
                return i
        # This is not a number and not an ignorable type, give up looking for the number this count belongs to
        break

    return None


def join_title(lst: list[filenamelexer.Item]) -> str:
    title = ""
    for i, item in enumerate(lst):
        if i + 1 == len(lst) and item.val == ",":  # We ignore commas on the end
            continue
        title += item.val  # Add the next item
        # No space after operators
        if item.typ == filenamelexer.ItemType.Operator:
            continue
        # No trailing space
        if i == len(lst) - 1:
            continue
        # No space after honorifics with a dot
        if (
            item.typ in (filenamelexer.ItemType.Honorific, filenamelexer.ItemType.Text)
            and lst[i + 1].typ == filenamelexer.ItemType.Dot
        ):
            continue
        if item.no_space:
            continue
        # No space if the next item is an operator or symbol
        if lst[i + 1].typ in [filenamelexer.ItemType.Operator, filenamelexer.ItemType.Symbol]:
            # exept if followed by a dollarsign
            if lst[i + 1].val != "&":
                continue

        # Add a space
        title += " "

    return title


def Parse(
    lexer_result: list[filenamelexer.Item],
    first_is_alt: bool = False,
    remove_c2c: bool = False,
    remove_fcbd: bool = False,
    remove_publisher: bool = False,
    protofolius_issue_number_scheme: bool = False,
) -> Parser:
    p = Parser(
        lexer_result=lexer_result,
        first_is_alt=first_is_alt,
        remove_c2c=remove_c2c,
        remove_fcbd=remove_fcbd,
        remove_publisher=remove_publisher,
        protofolius_issue_number_scheme=protofolius_issue_number_scheme,
    )
    p.run()
    return p
