"""Functions for parsing comic info from filename

This should probably be re-written, but, well, it mostly works!
"""

# Copyright 2012-2014 Anthony Beville

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at

#     http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# Some portions of this code were modified from pyComicMetaThis project
# http://code.google.com/p/pycomicmetathis/

import logging
import os
import re
from operator import itemgetter
from typing import Callable, Match, Optional, TypedDict
from urllib.parse import unquote

from text2digits import text2digits

from comicapi import filenamelexer, issuestring

t2d = text2digits.Text2Digits(add_ordinal_ending=False)
t2do = text2digits.Text2Digits(add_ordinal_ending=True)

logger = logging.getLogger(__name__)


class FileNameParser:
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
            placeholders = [r"[-_]", r"  +"]
        else:
            placeholders = [r"[_]", r"  +"]
        for ph in placeholders:
            string = re.sub(ph, self.repl, string)
        return string  # .strip()

    def get_issue_count(self, filename: str, issue_end: int) -> str:

        count = ""
        filename = filename[issue_end:]

        # replace any name separators with spaces
        tmpstr = self.fix_spaces(filename)
        found = False

        match = re.search(r"(?<=\sof\s)\d+(?=\s)", tmpstr, re.IGNORECASE)
        if match:
            count = match.group()
            found = True

        if not found:
            match = re.search(r"(?<=\(of\s)\d+(?=\))", tmpstr, re.IGNORECASE)
            if match:
                count = match.group()

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
        filename = re.sub(r"of [\d]+", self.repl, filename)

        # we should now have a cleaned up filename version with all the words in
        # the same positions as original filename

        # make a list of each word and its position
        word_list = []
        for m in re.finditer(r"\S+", filename):
            word_list.append((m.group(0), m.start(), m.end()))

        # remove the first word, since it can't be the issue number
        if len(word_list) > 1:
            word_list = word_list[1:]
        else:
            # only one word??  just bail.
            return issue, start, end

        # Now try to search for the likely issue number word in the list

        # first look for a word with "#" followed by digits with optional suffix
        # this is almost certainly the issue number
        for w in reversed(word_list):
            if re.match(r"#[-]?(([0-9]*\.[0-9]+|[0-9]+)(\w*))", w[0]):
                found = True
                break

        # same as above but w/o a '#', and only look at the last word in the
        # list
        if not found:
            w = word_list[-1]
            if re.match(r"[-]?(([0-9]*\.[0-9]+|[0-9]+)(\w*))", w[0]):
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

        # in case there is no issue number, remove some obvious stuff
        if "--" in filename:
            # the pattern seems to be that anything to left of the first "--"
            # is the series name followed by issue
            filename = re.sub(r"--.*", self.repl, filename)

        elif "__" in filename:
            # the pattern seems to be that anything to left of the first "__"
            # is the series name followed by issue
            filename = re.sub(r"__.*", self.repl, filename)

        filename = filename.replace("+", " ")
        tmpstr = self.fix_spaces(filename, remove_dashes=False)

        series = tmpstr
        volume = ""

        # save the last word
        try:
            last_word = series.split()[-1]
        except:
            last_word = ""

        # remove any parenthetical phrases
        series = re.sub(r"\(.*?\)", "", series)

        # search for volume number
        match = re.search(r"(.+)([vV]|[Vv][oO][Ll]\.?\s?)(\d+)\s*$", series)
        if match:
            series = match.group(1)
            volume = match.group(3)

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
            try:
                last_word = series.split()[-1]
                if last_word.lower() in one_shot_words:
                    series = series.rsplit(" ", 1)[0]
            except:
                pass

        return series, volume.strip()

    def get_year(self, filename: str, issue_end: int) -> str:

        filename = filename[issue_end:]

        year = ""
        # look for four digit number with "(" ")" or "--" around it
        match = re.search(r"(\(\d{4}\))|(--\d{4}--)", filename)
        if match:
            year = match.group()
            # remove non-digits
            year = re.sub(r"[^0-9]", "", year)
        return year

    def get_remainder(self, filename: str, year: str, count: str, volume: str, issue_end: int) -> str:
        """Make a guess at where the the non-interesting stuff begins"""

        remainder = ""

        if "--" in filename:
            remainder = filename.split("--", 1)[1]
        elif "__" in filename:
            remainder = filename.split("__", 1)[1]
        elif issue_end != 0:
            remainder = filename[issue_end:]

        remainder = self.fix_spaces(remainder, remove_dashes=False)
        if volume != "":
            remainder = remainder.replace("Vol." + volume, "", 1)
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

        # provides proper value when the filename doesn't have a issue number
        if issue_end == 0:
            issue_end = len(self.series)

        self.year = self.get_year(filename, issue_end)
        self.issue_count = self.get_issue_count(filename, issue_end)
        self.remainder = self.get_remainder(filename, self.year, self.issue_count, self.volume, issue_end)

        if self.issue != "":
            # strip off leading zeros
            self.issue = self.issue.lstrip("0")
            if self.issue == "":
                self.issue = "0"
            if self.issue[0] == ".":
                self.issue = "0" + self.issue


class FilenameInfo(TypedDict, total=False):
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


eof = filenamelexer.Item(filenamelexer.ItemType.EOF, -1, "")


class Parser:
    """docstring for FilenameParser"""

    def __init__(
        self,
        lexer_result: list[filenamelexer.Item],
        first_is_alt: bool = False,
        remove_c2c: bool = False,
        remove_fcbd: bool = False,
        remove_publisher: bool = False,
    ) -> None:
        self.state: Optional[Callable[[Parser], Optional[Callable]]] = None
        self.pos = -1

        self.firstItem = True
        self.skip = False
        self.alt = False
        self.filename_info: FilenameInfo = {"series": ""}
        self.issue_number_at = None
        self.in_something = 0  # In some sort of brackets {}[]()
        self.in_brace = 0  # In {}
        self.in_s_brace = 0  # In []
        self.in_paren = 0  # In ()
        self.year_candidates: list[tuple[bool, filenamelexer.Item]] = []
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

        self.input = lexer_result
        for i, item in enumerate(self.input):
            if item.typ == filenamelexer.ItemType.IssueNumber:
                self.issue_number_at = i

    # Get returns the next Item in the input.
    def get(self) -> filenamelexer.Item:
        if int(self.pos) >= len(self.input) - 1:
            self.pos += 1
            return eof

        self.pos += 1
        return self.input[self.pos]

    # Peek returns but does not consume the next Item in the input.
    def peek(self) -> filenamelexer.Item:
        if int(self.pos) >= len(self.input) - 1:
            return eof

        return self.input[self.pos + 1]

    # Peek_back returns but does not step back the previous Item in the input.
    def peek_back(self) -> filenamelexer.Item:
        if int(self.pos) == 0:
            return eof

        return self.input[self.pos - 1]

    # Backup steps back one Item.
    def backup(self) -> None:
        self.pos -= 1

    def run(self) -> None:
        self.state = parse
        while self.state is not None:
            self.state = self.state(self)


def parse(p: Parser) -> Optional[Callable[[Parser], Optional[Callable]]]:
    item: filenamelexer.Item = p.get()

    # We're done, time to do final processing
    if item.typ == filenamelexer.ItemType.EOF:
        return parse_finish

    # Need to figure out if this is the issue number
    if item.typ == filenamelexer.ItemType.Number:
        likely_year = False
        if p.firstItem and p.first_is_alt:
            p.alt = True
            return parse_issue_number

        # The issue number should hopefully not be in parentheses
        if p.in_something == 0:
            # Assume that operators indicate a non-issue number e.g. IG-88 or 88-IG
            if filenamelexer.ItemType.Operator not in (p.peek().typ, p.peek_back().typ):
                # It is common to use '89 to refer to an annual reprint from 1989
                if item.val[0] != "'":
                    # Issue number is less than 4 digits. very few series go above 999
                    if len(item.val.lstrip("0")) < 4:
                        # An issue number starting with # Was not found and no previous number was found
                        if p.issue_number_at is None:
                            # Series has already been started/parsed, filters out leading alternate numbers leading alternate number
                            if len(p.series_parts) > 0:
                                # Unset first item
                                if p.firstItem:
                                    p.firstItem = False
                                return parse_issue_number
            else:
                p.operator_rejected.append(item)
                # operator rejected used later to add back to the series/title

        # It is more likely to be a year if it is inside parentheses.
        if p.in_something > 0:
            likely_year = True

        # If numbers are directly followed by text it most likely isn't a year e.g. 2048px
        if p.peek().typ == filenamelexer.ItemType.Text:
            likely_year = False

        # Is either a full year '2001' or a short year "'89"
        if len(item.val) == 4 or item.val[0] == "'":
            if p.in_something == 0:
                # Append to series in case it is a part of the title, but only if were not inside parenthesis
                p.series_parts.append(item)

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

            p.year_candidates.append((likely_year, item))
        # Ensures that IG-88 gets added back to the series/title
        elif (
            p.in_something == 0
            and p.peek_back().typ == filenamelexer.ItemType.Operator
            or p.peek().typ == filenamelexer.ItemType.Operator
        ):
            # Were not in something and the next or previous type is an operator, add it to the series
            p.series_parts.append(item)
            p.used_items.append(item)

            # Unset first item
            if p.firstItem:
                p.firstItem = False
            p.get()
            return parse_series

    # Number with a leading hash e.g. #003
    elif item.typ == filenamelexer.ItemType.IssueNumber:
        # Unset first item
        if p.firstItem:
            p.firstItem = False
        return parse_issue_number

    # Matches FCBD. Not added to p.used_items so it will show in "remainder"
    elif item.typ == filenamelexer.ItemType.FCBD:
        p.filename_info["fcbd"] = True

    # Matches c2c. Not added to p.used_items so it will show in "remainder"
    elif item.typ == filenamelexer.ItemType.C2C:
        p.filename_info["c2c"] = True

    # Matches the extension if it is known to be an archive format e.g. cbt,cbz,zip,rar
    elif item.typ == filenamelexer.ItemType.ArchiveType:
        p.filename_info["archive"] = item.val.lower()
        p.used_items.append(item)
        if p.peek_back().typ == filenamelexer.ItemType.Dot:
            p.used_items.append(p.peek_back())

    # Allows removing DC from 'Wonder Woman 49 DC Sep-Oct 1951' dependent on publisher being in a static list in the lexer
    elif item.typ == filenamelexer.ItemType.Publisher:
        p.filename_info["publisher"] = item.val
        p.used_items.append(item)
        if p.firstItem:
            p.firstItem = False
            if p.in_something == 0:
                return parse_series
        p.publisher_removed.append(item)
        if p.in_something == 0:
            return parse_series

    # Attempts to identify the type e.g. annual
    elif item.typ == filenamelexer.ItemType.ComicType:
        series_append = True

        if p.peek().typ == filenamelexer.ItemType.Space:
            p.get()

        if p.series_parts and "free comic book" in (" ".join([x.val for x in p.series_parts]) + " " + item.val).lower():
            p.filename_info["fcbd"] = True
            series_append = True
        # If the next item is a number it's probably the volume
        elif p.peek().typ == filenamelexer.ItemType.Number or (
            p.peek().typ == filenamelexer.ItemType.Text and t2d.convert(p.peek().val).isnumeric()
        ):
            number = p.get()
            # Mark volume info. Text will be added to the title/series later
            if item.val.lower() in ["book", "tpb"]:
                p.title_parts.extend([item, number])
                p.filename_info["volume"] = t2do.convert(number.val)
                p.filename_info["issue"] = t2do.convert(number.val)

                p.used_items.append(item)
                series_append = False

            # Annuals usually mean the year
            elif item.val.lower() in ["annual"]:
                p.filename_info["annual"] = True
                num = t2d.convert(number.val)
                if num.isnumeric() and len(num) == 4:
                    p.year_candidates.append((True, number))
                else:
                    p.backup()

        elif item.val.lower() in ["annual"]:
            p.filename_info["annual"] = True

        # If we don't have a reason to exclude it from the series go back to parsing the series immediately
        if series_append:
            p.series_parts.append(item)
            p.used_items.append(item)
            return parse_series

    # We found text, it's probably the title or series
    elif item.typ in [filenamelexer.ItemType.Text, filenamelexer.ItemType.Honorific]:
        # Unset first item
        if p.firstItem:
            p.firstItem = False
        if p.in_something == 0:
            return parse_series

    # Usually the word 'of' eg 1 (of 6)
    elif item.typ == filenamelexer.ItemType.InfoSpecifier:
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
                return parse_series
        # This is text that just happens to also be a month/day
        else:
            return parse_series

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
def parse_issue_number(p: Parser) -> Optional[Callable[[Parser], Optional[Callable]]]:
    item = p.input[p.pos]

    if "issue" in p.filename_info:
        if "alternate" in p.filename_info:
            p.filename_info["alternate"] += "," + item.val
        p.filename_info["alternate"] = item.val
    else:
        if p.alt:
            p.filename_info["alternate"] = item.val
        else:
            p.filename_info["issue"] = item.val
            p.issue_number_at = item.pos
        p.used_items.append(item)
        item = p.get()
        if item.typ == filenamelexer.ItemType.Dot:
            p.used_items.append(item)
            item = p.get()
            if item.typ in [filenamelexer.ItemType.Text, filenamelexer.ItemType.Number]:
                if p.alt:
                    p.filename_info["alternate"] += "." + item.val
                else:
                    p.filename_info["issue"] += "." + item.val
                p.used_items.append(item)
            else:
                p.backup()
                p.backup()
        else:
            p.backup()
    p.alt = False
    return parse


def parse_series(p: Parser) -> Optional[Callable[[Parser], Optional[Callable]]]:
    item = p.input[p.pos]

    series: list[list[filenamelexer.Item]] = [[]]
    # Space and Dots are not useful at the beginning of a title/series
    if not p.skip and item.typ not in [filenamelexer.ItemType.Space, filenamelexer.ItemType.Dot]:
        series[0].append(item)

    current_part = 0

    title_parts: list[filenamelexer.Item] = []
    series_parts: list[filenamelexer.Item] = []

    prev_space = False

    # 'free comic book day' screws things up. #TODO look into removing book from ComicType?

    # We stop parsing the series when certain things come up if nothing was done with them continue where we left off
    if (
        p.series_parts
        and p.series_parts[-1].val.lower() == "book"
        or p.peek_back().typ == filenamelexer.ItemType.Number
        or item.typ == filenamelexer.ItemType.Calendar
    ):
        series_parts = p.series_parts
        p.series_parts = []
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
            series[current_part].append(item)
            if item.typ == filenamelexer.ItemType.Honorific and p.peek().typ == filenamelexer.ItemType.Dot:
                series[current_part].append(p.get())
            elif item.typ == filenamelexer.ItemType.Publisher:
                p.filename_info["publisher"] = item.val

        # Handle Volume
        elif item.typ == filenamelexer.ItemType.InfoSpecifier:
            # Exception for 'of'
            if item.val.lower() == "of":
                series[current_part].append(item)
            else:
                # This specifically lets 'X-Men-V1-067' parse correctly as Series: X-Men Volume: 1 Issue: 67
                while len(series[current_part]) > 0 and series[current_part][-1].typ not in [
                    filenamelexer.ItemType.Text,
                    filenamelexer.ItemType.Symbol,
                ]:
                    p.irrelevant.append(series[current_part].pop())
                p.backup()
                break

        elif item.typ == filenamelexer.ItemType.Operator:
            peek = p.peek()
            # ': ' separates the title from the series, only the last section is considered the title
            if not prev_space and peek.typ in [filenamelexer.ItemType.Space]:
                series.append([])  # Starts a new section
                series[current_part].append(item)
                current_part += 1
            else:
                # Force space around '-' makes 'batman - superman' stay otherwise we get 'batman-superman'
                if prev_space and peek.typ in [filenamelexer.ItemType.Space]:
                    item.val = " " + item.val + " "
                series[current_part].append(item)

        # Stop processing series/title if a skip item is found
        elif item.typ == filenamelexer.ItemType.Skip:
            p.backup()
            break

        elif item.typ == filenamelexer.ItemType.Number:
            if p.peek().typ == filenamelexer.ItemType.Space:
                p.get()
                # We have 2 numbers, add the first to the series and then go back to parse
                if p.peek().typ == filenamelexer.ItemType.Number:
                    series[current_part].append(item)
                    break

                # We have 1 number break here, it's possible it's the issue
                p.backup()  # Whitespace
                p.backup()  # The number
                break
            # This is 6 in '1 of 6'
            if series[current_part] and series[current_part][-1].val.lower() == "of":
                series[current_part].append(item)

            # We have 1 number break here, it's possible it's the issue
            else:
                p.backup()  # The number
                break

        else:
            # Ensure 'ms. marvel' parses 'ms.' correctly
            if item.typ == filenamelexer.ItemType.Dot and p.peek_back().typ == filenamelexer.ItemType.Honorific:
                series[current_part].append(item)
            # Allows avengers.hulk to parse correctly
            elif item.typ == filenamelexer.ItemType.Dot and p.peek().typ == filenamelexer.ItemType.Text:
                # Marks the dot as used so that the remainder is clean
                p.used_items.append(item)
            else:
                p.backup()
                break

        prev_space = False

    # We have a title separator e.g. ': "
    if len(series) > 1:
        title_parts.extend(series.pop())
        for s in series:
            if s and s[-1].typ == filenamelexer.ItemType.Operator:
                s[-1].val += " "  # Ensures that when there are multiple separators that they display properly
            series_parts.extend(s)
        p.used_items.append(series_parts.pop())
    else:
        series_parts.extend(series[0])

    # If the series has already been set assume all of this is the title.
    if len(p.series_parts) > 0:
        p.title_parts.extend(series_parts)
        p.title_parts.extend(title_parts)
    else:
        p.series_parts.extend(series_parts)
        p.title_parts.extend(title_parts)
    return parse


def resolve_year(p: Parser) -> None:
    if len(p.year_candidates) > 0:
        # Sort by likely_year boolean
        p.year_candidates.sort(key=itemgetter(0))

        # Take the last year e.g. (2007) 2099 (2008) becomes 2099 2007 2008 and takes 2008
        selected_year = p.year_candidates.pop()[1]

        p.filename_info["year"] = selected_year.val
        p.used_items.append(selected_year)

        # (2008) Title (2009) is many times used to denote the series year if we don't have a volume we use it
        if "volume" not in p.filename_info and p.year_candidates and p.year_candidates[-1][0]:
            vol = p.year_candidates.pop()[1]
            p.filename_info["volume"] = vol.val
            p.used_items.append(vol)

            # Remove volume from series and title
            if selected_year in p.series_parts:
                p.series_parts.remove(selected_year)
            if selected_year in p.title_parts:
                p.title_parts.remove(selected_year)

        # Remove year from series and title
        if selected_year in p.series_parts:
            p.series_parts.remove(selected_year)
        if selected_year in p.title_parts:
            p.title_parts.remove(selected_year)


def parse_finish(p: Parser) -> Optional[Callable[[Parser], Optional[Callable]]]:
    resolve_year(p)

    # If we don't have an issue try to find it in the series
    if "issue" not in p.filename_info and p.series_parts and p.series_parts[-1].typ == filenamelexer.ItemType.Number:
        issue_num = p.series_parts.pop()

        # If the number we just popped is a year put it back on it's probably part of the series e.g. Spider-Man 2099
        if issue_num in [x[1] for x in p.year_candidates]:
            p.series_parts.append(issue_num)
        else:
            # If this number was rejected because of an operator and the operator is still there add it back e.g. 'IG-88'
            if (
                issue_num in p.operator_rejected
                and p.series_parts
                and p.series_parts[-1].typ == filenamelexer.ItemType.Operator
            ):
                p.series_parts.append(issue_num)
            # We have no reason to not use this number as the issue number. Specifically happens when parsing 'X-Men-V1-067.cbr'
            else:
                p.filename_info["issue"] = issue_num.val
                p.used_items.append(issue_num)
                p.issue_number_at = issue_num.pos

    # Remove publishers, currently only marvel and dc are defined,
    # this is an option specifically because this can drastically screw up parsing
    if p.remove_publisher:
        for item in p.publisher_removed:
            if item in p.series_parts:
                p.series_parts.remove(item)
            if item in p.title_parts:
                p.title_parts.remove(item)

    p.filename_info["series"] = join_title(p.series_parts)
    p.used_items.extend(p.series_parts)

    p.filename_info["title"] = join_title(p.title_parts)
    p.used_items.extend(p.title_parts)

    if "issue" in p.filename_info:
        p.filename_info["issue"] = issuestring.IssueString(p.filename_info["issue"].lstrip("#")).as_string()

    if "volume" in p.filename_info:
        p.filename_info["volume"] = p.filename_info["volume"].lstrip("#").lstrip("0")

    if "issue" not in p.filename_info:
        # We have an alternate move it to the issue
        if "alternate" in p.filename_info:
            p.filename_info["issue"] = p.filename_info["alternate"]
            p.filename_info["alternate"] = ""
        else:
            # TODO: This never happens
            inp = [x for x in p.input if x not in p.irrelevant and x not in p.used_items and x.typ != eof.typ]
            if len(inp) == 1 and inp[0].typ == filenamelexer.ItemType.Number:
                p.filename_info["issue"] = inp[0].val
                p.used_items.append(inp[0])

    remove_items = []
    if p.remove_fcbd:
        remove_items.append(filenamelexer.ItemType.FCBD)
    if p.remove_c2c:
        remove_items.append(filenamelexer.ItemType.C2C)

    p.irrelevant.extend([x for x in p.input if x.typ in remove_items])

    p.filename_info["remainder"] = get_remainder(p)

    # Ensure keys always exist
    for s in [
        "alternate",
        "issue",
        "archive",
        "series",
        "title",
        "volume",
        "year",
        "remainder",
        "issue_count",
        "volume_count",
        "publisher",
    ]:
        if s not in p.filename_info:
            p.filename_info[s] = ""  # type: ignore
    for s in ["fcbd", "c2c", "annual"]:
        if s not in p.filename_info:
            p.filename_info[s] = False  # type: ignore
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
                filenamelexer.ItemType.Space,
                filenamelexer.ItemType.RightBrace,
                filenamelexer.ItemType.RightParen,
                filenamelexer.ItemType.RightSBrace,
            ]
            and i > 0
            and inp[i - 1].typ
            in [
                filenamelexer.ItemType.LeftBrace,
                filenamelexer.ItemType.LeftParen,
                filenamelexer.ItemType.LeftSBrace,
            ]
        ):
            remainder = remainder.rstrip("[{(")
            continue

        # Add the next item
        else:
            rem.append(item)
            remainder += item.val

    # Remove empty parentheses
    remainder = re.sub(r"[\[{(]+[]})]+", "", remainder)
    return remainder.strip()


def parse_info_specifier(p: Parser) -> Optional[Callable[[Parser], Optional[Callable]]]:
    item = p.input[p.pos]
    index = p.pos

    if p.peek().typ == filenamelexer.ItemType.Space:
        p.get()

    # Handles 'book 3' and 'book three'
    if p.peek().typ == filenamelexer.ItemType.Number or (
        p.peek().typ == filenamelexer.ItemType.Text and t2d.convert(p.peek().val).isnumeric()
    ):

        number = p.get()
        if item.val.lower() in ["volume", "vol", "vol.", "v"]:
            p.filename_info["volume"] = t2do.convert(number.val)
            p.used_items.append(item)
            p.used_items.append(number)

        # 'of' is only special if it is inside a parenthesis.
        elif item.val.lower() == "of":
            i = get_number(p, index)
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

                    # This is not for the issue number it is not in either the issue or the title, assume it is the volume number and count
                    elif p.issue_number_at != i.pos and i not in p.series_parts and i not in p.title_parts:
                        p.filename_info["volume"] = i.val
                        p.filename_info["volume_count"] = str(int(t2do.convert(number.val)))
                        p.used_items.append(i)
                        p.used_items.append(item)
                        p.used_items.append(number)
                    else:
                        # TODO: Figure out what to do here if it ever happens
                        pass
                else:
                    # Lets 'The Wrath of Foobar-Man, Part 1 of 2' parse correctly as the title
                    p.pos = [ind for ind, x in enumerate(p.input) if x == i][0]

            if not p.in_something:
                return parse_series
    return parse


# Gets 03 in '03 of 6'
def get_number(p: Parser, index: int) -> Optional[filenamelexer.Item]:
    # Go backward through the filename to see if we can find what this is of eg '03 (of 6)' or '008 title 03 (of 6)'
    rev = p.input[:index]
    rev.reverse()
    for i in rev:
        # We don't care about these types, we are looking to see if there is a number that is possibly different from the issue number for this count
        if i.typ in [
            filenamelexer.ItemType.LeftParen,
            filenamelexer.ItemType.LeftBrace,
            filenamelexer.ItemType.LeftSBrace,
            filenamelexer.ItemType.Space,
        ]:
            continue
        if i.typ == filenamelexer.ItemType.Number:
            # We got our number, time to leave
            return i
        # This is not a number and not an ignorable type, give up looking for the number this count belongs to

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
        if item.typ == filenamelexer.ItemType.Honorific and lst[i + 1].typ == filenamelexer.ItemType.Dot:
            continue
        # No space if the next item is an operator or symbol
        if lst[i + 1].typ in [
            filenamelexer.ItemType.Operator,
            filenamelexer.ItemType.Symbol,
        ]:
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
) -> Parser:
    p = Parser(
        lexer_result=lexer_result,
        first_is_alt=first_is_alt,
        remove_c2c=remove_c2c,
        remove_fcbd=remove_fcbd,
        remove_publisher=remove_publisher,
    )
    p.run()
    return p
