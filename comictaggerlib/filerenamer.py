"""Functions for renaming files based on metadata"""

#
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

import calendar
import datetime
import logging
import os
import pathlib
import string
from collections.abc import Collection, Iterable, Mapping, Sequence, Sized
from typing import Any, cast

from pathvalidate import Platform, normalize_platform, sanitize_filename

from comicapi.comicarchive import ComicArchive
from comicapi.genericmetadata import GenericMetadata
from comicapi.issuestring import IssueString
from comictaggerlib.defaults import DEFAULT_REPLACEMENTS, Replacement, Replacements

logger = logging.getLogger(__name__)


def get_rename_dir(ca: ComicArchive, rename_dir: str | pathlib.Path | None) -> pathlib.Path:
    folder = ca.path.parent.absolute()
    if rename_dir is not None:
        if isinstance(rename_dir, str):
            rename_dir = pathlib.Path(rename_dir.strip())
        folder = rename_dir.absolute()
    return folder


def _isnamedtupleinstance(x: Any) -> bool:  # pragma: no cover
    t = type(x)
    b = t.__bases__

    if len(b) != 1 or b[0] != tuple:
        return False

    f = getattr(t, "_fields", None)
    if not isinstance(f, tuple):
        return False

    return all(isinstance(n, str) for n in f)


class MetadataFormatter(string.Formatter):
    def __init__(
        self, smart_cleanup: bool = False, platform: str = "auto", replacements: Replacements = DEFAULT_REPLACEMENTS
    ) -> None:
        super().__init__()
        self.smart_cleanup = smart_cleanup
        self.platform = normalize_platform(platform)
        self.replacements = replacements

    def format_field(self, value: Any, format_spec: str) -> str:
        if value is None or value == "":
            return ""
        return cast(str, super().format_field(value, format_spec))

    def convert_field(self, value: Any, conversion: str | None) -> str:
        if isinstance(value, Iterable) and not isinstance(value, str) and not _isnamedtupleinstance(value):
            if conversion == "C":
                if isinstance(value, Sized):
                    return str(len(value))
                return ""
            if conversion and conversion.isdecimal():
                if not isinstance(value, Collection):
                    return ""
                i = int(conversion) - 1
                if i < 0:
                    i = 0
                if i < len(value):
                    try:
                        return sorted(value)[i]
                    except Exception:
                        ...
                    return list(value)[i]
                return ""
            try:
                return ", ".join(list(self.convert_field(v, conversion) for v in sorted(value)))
            except Exception:
                ...
            return ", ".join(list(self.convert_field(v, conversion) for v in value))
        if not conversion:
            return cast(str, super().convert_field(value, conversion))
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
        if conversion.isdecimal():
            return ""
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
        args: Sequence[Any],
        kwargs: Mapping[str, Any],
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
                obj = self.convert_field(obj, conversion)
                obj = self.none_replacement(obj, replacement, r)

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
    def __init__(
        self,
        metadata: GenericMetadata | None,
        platform: str = "auto",
        replacements: Replacements = DEFAULT_REPLACEMENTS,
    ) -> None:
        self.template = "{publisher}/{series}/{series} v{volume} #{issue} (of {issue_count}) ({year})"
        self.smart_cleanup = True
        self.issue_zero_padding = 3
        self.metadata = metadata or GenericMetadata()
        self.move = False
        self.platform = platform
        self.replacements = replacements
        self.original_name = ""
        self.move_only = False

    def set_metadata(self, metadata: GenericMetadata, original_name: str) -> None:
        self.metadata = metadata
        self.original_name = original_name

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

        template = self.template

        new_name = ""

        fmt = MetadataFormatter(self.smart_cleanup, platform=self.platform, replacements=self.replacements)
        md_dict = vars(md)
        md_dict.update(
            dict(
                month_name=None,
                month_abbr=None,
                date=None,
                genre=None,
                story_arc=None,
                series_group=None,
                web_link=None,
                character=None,
                team=None,
                location=None,
            )
        )

        md_dict["issue"] = IssueString(md.issue).as_string(pad=self.issue_zero_padding)
        for role in ["writer", "penciller", "inker", "colorist", "letterer", "cover artist", "editor", "translator"]:
            md_dict[role] = md.get_primary_credit(role)

        if (isinstance(md.month, int) or isinstance(md.month, str) and md.month.isdigit()) and 0 < int(md.month) < 13:
            md_dict["month_name"] = calendar.month_name[int(md.month)]
            md_dict["month_abbr"] = calendar.month_abbr[int(md.month)]

        if md.year is not None and datetime.MINYEAR <= md.year <= datetime.MAXYEAR:
            md_dict["date"] = datetime.datetime(year=md.year, month=md.month or 1, day=md.day or 1)

        if md.genres:
            md_dict["genre"] = sorted(md.genres)[0]
        if md.story_arcs:
            md_dict["story_arc"] = md.story_arcs[0]
        if md.series_groups:
            md_dict["series_group"] = md.series_groups[0]
        if md.web_links:
            md_dict["web_link"] = md.web_links[0]
        if md.characters:
            md_dict["character"] = sorted(md.characters)[0]
        if md.teams:
            md_dict["team"] = sorted(md.teams)[0]
        if md.locations:
            md_dict["location"] = sorted(md.locations)[0]

        new_basename = ""
        for component in pathlib.PureWindowsPath(template).parts:
            new_basename = str(
                sanitize_filename(fmt.vformat(component, args=[], kwargs=Default(md_dict)), platform=self.platform)
            ).strip()
            new_name = os.path.join(new_name, new_basename)

        if self.move_only:
            new_folder = os.path.join(new_name, os.path.splitext(self.original_name)[0])
            return new_folder + ext
        if self.move:
            return new_name.strip() + ext
        return new_basename.strip() + ext
