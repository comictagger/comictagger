"""Functions for renaming files based on metadata"""

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

import calendar
import logging
import os
import pathlib
import string
import sys
from typing import Any, Optional, cast

from pathvalidate import sanitize_filename

from comicapi.genericmetadata import GenericMetadata
from comicapi.issuestring import IssueString

logger = logging.getLogger(__name__)


class MetadataFormatter(string.Formatter):
    def __init__(self, smart_cleanup: bool = False, platform: str = "auto") -> None:
        super().__init__()
        self.smart_cleanup = smart_cleanup
        self.platform = platform

    def format_field(self, value: Any, format_spec: str) -> str:
        if value is None or value == "":
            return ""
        return cast(str, super().format_field(value, format_spec))

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
                field_name = field_name.lower()
                # this is some markup, find the object and do the formatting

                # handle arg indexing when empty field_names are given.
                if field_name == "":
                    if auto_arg_index is False:
                        raise ValueError("cannot switch from manual field specification to automatic field numbering")
                    field_name = str(auto_arg_index)
                    auto_arg_index += 1
                elif field_name.isdigit():
                    if auto_arg_index:
                        raise ValueError("cannot switch from manual field specification to automatic field numbering")
                    # disable auto arg incrementing, if it gets used later on, then an exception will be raised
                    auto_arg_index = False

                # given the field_name, find the object it references
                #  and the argument it came from
                obj, arg_used = self.get_field(field_name, args, kwargs)
                used_args.add(arg_used)

                # do any conversion on the resulting object
                obj = self.convert_field(obj, conversion)  # type: ignore

                # expand the format spec, if needed
                format_spec, auto_arg_index = self._vformat(
                    cast(str, format_spec), args, kwargs, used_args, recursion_depth - 1, auto_arg_index=auto_arg_index
                )

                # format the object and append to the result
                fmt_obj = self.format_field(obj, format_spec)
                if fmt_obj == "" and len(result) > 0 and self.smart_cleanup:
                    lstrip = True
                    if result:
                        result[-1] = result[-1].rstrip("-_({[#")
                if self.smart_cleanup:
                    fmt_obj = " ".join(fmt_obj.split())
                    fmt_obj = str(sanitize_filename(fmt_obj, platform=self.platform))
                result.append(fmt_obj)

        return "".join(result), auto_arg_index


class FileRenamer:
    def __init__(self, metadata: Optional[GenericMetadata], platform: str = "auto") -> None:
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
        class Default(dict):
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

        for Component in pathlib.PureWindowsPath(template).parts:
            if (
                self.platform.lower() in ["universal", "windows"] or sys.platform.lower() in ["windows"]
            ) and self.smart_cleanup:
                # colons get special treatment
                Component = Component.replace(": ", " - ")
                Component = Component.replace(":", "-")

            new_basename = str(
                sanitize_filename(fmt.vformat(Component, args=[], kwargs=Default(md_dict)), platform=self.platform)
            ).strip()
            new_name = os.path.join(new_name, new_basename)

        new_name += ext
        new_basename += ext

        # remove padding
        md.issue = IssueString(md.issue).as_string()
        if self.move:
            return new_name.strip()
        return new_basename.strip()
