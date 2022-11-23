"""Functions for renaming files based on metadata"""
#
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

import calendar
import logging
import os
import pathlib
import string
from typing import Any, NamedTuple, cast

from pathvalidate import Platform, normalize_platform, sanitize_filename

from comicapi.comicarchive import ComicArchive
from comicapi.genericmetadata import GenericMetadata
from comicapi.issuestring import IssueString

logger = logging.getLogger(__name__)


class Replacement(NamedTuple):
    find: str
    replce: str
    strict_only: bool


class Replacements(NamedTuple):
    literal_text: list[Replacement]
    format_value: list[Replacement]


REPLACEMENTS = Replacements(
    literal_text=[
        Replacement(": ", " - ", True),
        Replacement(":", "-", True),
    ],
    format_value=[
        Replacement(": ", " - ", True),
        Replacement(":", "-", True),
        Replacement("/", "-", False),
        Replacement("\\", "-", True),
    ],
)


def get_rename_dir(ca: ComicArchive, rename_dir: str | pathlib.Path | None) -> pathlib.Path:
    folder = ca.path.parent.absolute()
    if rename_dir is not None:
        if isinstance(rename_dir, str):
            rename_dir = rename_dir.strip()
        folder = pathlib.Path(rename_dir).absolute()
    return folder


class MetadataFormatter(string.Formatter):
    def __init__(
        self, smart_cleanup: bool = False, platform: str = "auto", replacements: Replacements = REPLACEMENTS
    ) -> None:
        super().__init__()
        self.smart_cleanup = smart_cleanup
        self.platform = normalize_platform(platform)
        self.replacements = replacements

    def format_field(self, value: Any, format_spec: str) -> str:
        if value is None or value == "":
            return ""
        return cast(str, super().format_field(value, format_spec))

    def convert_field(self, value: Any, conversion: str) -> str:
        if conversion == "u":
            return str(value).upper()
        if conversion == "l":
            return str(value).casefold()
        if conversion == "c":
            return str(value).capitalize()
        if conversion == "S":
            return str(value).swapcase()
        if conversion == "t":
            return str(value).title()
        return cast(str, super().convert_field(value, conversion))

    def handle_replacements(self, string: str, replacements: list[Replacement]) -> str:
        for find, replace, strict_only in replacements:
            if self.is_strict() or not strict_only:
                string = string.replace(find, replace)
        return string

    def none_replacement(self, value: Any, replacement: str, r: str) -> Any:
        if r == "-" and value is None or value == "":
            return replacement
        if r == "+" and value is not None:
            return replacement
        return value

    def split_replacement(self, field_name: str) -> tuple[str, str, str]:
        if "-" in field_name:
            return field_name.rpartition("-")
        if "+" in field_name:
            return field_name.rpartition("+")
        return field_name, "", ""

    def is_strict(self) -> bool:
        return self.platform in [Platform.UNIVERSAL, Platform.WINDOWS]

    def _vformat(
        self,
        format_string: str,
        args: list[Any],
        kwargs: dict[str, Any],
        used_args: set[Any],
        recursion_depth: int,
        auto_arg_index: int = 0,
    ) -> tuple[str, int]:
        if recursion_depth < 0:
            raise ValueError("Max string recursion exceeded")
        result = []
        lstrip = False
        for literal_text, field_name, format_spec, conversion in self.parse(format_string):

            # output the literal text
            if literal_text:
                if lstrip:
                    literal_text = literal_text.lstrip("-_)}]#")
                if self.smart_cleanup:
                    literal_text = self.handle_replacements(literal_text, self.replacements.literal_text)
                    lspace = literal_text[0].isspace() if literal_text else False
                    rspace = literal_text[-1].isspace() if literal_text else False
                    literal_text = " ".join(literal_text.split())
                    if literal_text == "":
                        literal_text = " "
                    else:
                        if lspace:
                            literal_text = " " + literal_text
                        if rspace:
                            literal_text += " "
                result.append(literal_text)

            lstrip = False
            # if there's a field, output it
            if field_name is not None and field_name != "":
                field_name, r, replacement = self.split_replacement(field_name)
                field_name = field_name.casefold()
                # this is some markup, find the object and do the formatting

                # handle arg indexing when digit field_names are given.
                if field_name.isdigit():
                    raise ValueError("cannot use a number as a field name")

                # given the field_name, find the object it references
                #  and the argument it came from
                obj, arg_used = self.get_field(field_name, args, kwargs)
                used_args.add(arg_used)

                obj = self.none_replacement(obj, replacement, r)

                # do any conversion on the resulting object
                obj = self.convert_field(obj, conversion)  # type: ignore

                # expand the format spec, if needed
                format_spec, _ = self._vformat(
                    cast(str, format_spec), args, kwargs, used_args, recursion_depth - 1, auto_arg_index=False
                )

                # format the object and append to the result
                fmt_obj = self.format_field(obj, format_spec)
                if fmt_obj == "" and result and self.smart_cleanup and literal_text:
                    if self.str_contains(result[-1], "({["):
                        lstrip = True
                    if result:
                        if " " in result[-1]:
                            result[-1], _, _ = result[-1].rstrip().rpartition(" ")
                        result[-1] = result[-1].rstrip("-_({[#")
                if self.smart_cleanup:
                    # colons and slashes get special treatment
                    fmt_obj = self.handle_replacements(fmt_obj, self.replacements.format_value)
                    fmt_obj = " ".join(fmt_obj.split())
                    fmt_obj = str(sanitize_filename(fmt_obj, platform=self.platform))
                result.append(fmt_obj)

        return "".join(result), False

    def str_contains(self, chars: str, string: str) -> bool:
        for char in chars:
            if char in string:
                return True
        return False


class FileRenamer:
    def __init__(self, metadata: GenericMetadata | None, platform: str = "auto") -> None:
        self.template = "{publisher}/{series}/{series} v{volume} #{issue} (of {issue_count}) ({year})"
        self.smart_cleanup = True
        self.issue_zero_padding = 3
        self.metadata = metadata or GenericMetadata()
        self.move = False
        self.platform = platform

    def set_metadata(self, metadata: GenericMetadata) -> None:
        self.metadata = metadata

    def set_issue_zero_padding(self, count: int) -> None:
        self.issue_zero_padding = count

    def set_smart_cleanup(self, on: bool) -> None:
        self.smart_cleanup = on

    def set_template(self, template: str) -> None:
        self.template = template

    def determine_name(self, ext: str) -> str:
        class Default(dict[str, Any]):
            def __missing__(self, key: str) -> str:
                return "{" + key + "}"

        md = self.metadata

        # padding for issue
        md.issue = IssueString(md.issue).as_string(pad=self.issue_zero_padding)

        template = self.template

        new_name = ""

        fmt = MetadataFormatter(self.smart_cleanup, platform=self.platform)
        md_dict = vars(md)
        for role in ["writer", "penciller", "inker", "colorist", "letterer", "cover artist", "editor"]:
            md_dict[role] = md.get_primary_credit(role)

        if (isinstance(md.month, int) or isinstance(md.month, str) and md.month.isdigit()) and 0 < int(md.month) < 13:
            md_dict["month_name"] = calendar.month_name[int(md.month)]
            md_dict["month_abbr"] = calendar.month_abbr[int(md.month)]
        else:
            md_dict["month_name"] = ""
            md_dict["month_abbr"] = ""

        new_basename = ""
        for component in pathlib.PureWindowsPath(template).parts:
            new_basename = str(
                sanitize_filename(fmt.vformat(component, args=[], kwargs=Default(md_dict)), platform=self.platform)
            ).strip()
            new_name = os.path.join(new_name, new_basename)

        new_name += ext
        new_basename += ext

        # remove padding
        md.issue = IssueString(md.issue).as_string()
        if self.move:
            return new_name.strip()
        return new_basename.strip()
