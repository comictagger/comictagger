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
import datetime
import logging
import os
import re
import string

from pathvalidate import sanitize_filepath

from comicapi.genericmetadata import GenericMetadata
from comicapi.issuestring import IssueString

logger = logging.getLogger(__name__)


class FileRenamer:
    def __init__(self, metadata):
        self.template = "%series% v%volume% #%issue% (of %issuecount%) (%year%)"
        self.smart_cleanup = True
        self.issue_zero_padding = 3
        self.metadata = metadata

    def set_metadata(self, metadata: GenericMetadata):
        self.metadata = metadata

    def set_issue_zero_padding(self, count):
        self.issue_zero_padding = count

    def set_smart_cleanup(self, on):
        self.smart_cleanup = on

    def set_template(self, template: str):
        self.template = template

    def replace_token(self, text, value, token):
        # helper func
        def is_token(word):
            return word[0] == "%" and word[-1:] == "%"

        if value is not None:
            return text.replace(token, str(value))

        if self.smart_cleanup:
            # smart cleanup means we want to remove anything appended to token if it's empty (e.g "#%issue%"  or "v%volume%")
            # (TODO: This could fail if there is more than one token appended together, I guess)
            text_list = text.split()

            # special case for issuecount, remove preceding non-token word,
            # as in "...(of %issuecount%)..."
            if token == "%issuecount%":
                for idx, word in enumerate(text_list):
                    if token in word and not is_token(text_list[idx - 1]):
                        text_list[idx - 1] = ""

            text_list = [x for x in text_list if token not in x]
            return " ".join(text_list)

        return text.replace(token, "")

    def determine_name(self, ext):

        md = self.metadata
        new_name = self.template

        new_name = self.replace_token(new_name, md.series, "%series%")
        new_name = self.replace_token(new_name, md.volume, "%volume%")

        if md.issue is not None:
            issue_str = IssueString(md.issue).as_string(pad=self.issue_zero_padding)
        else:
            issue_str = None
        new_name = self.replace_token(new_name, issue_str, "%issue%")

        new_name = self.replace_token(new_name, md.issue_count, "%issuecount%")
        new_name = self.replace_token(new_name, md.year, "%year%")
        new_name = self.replace_token(new_name, md.publisher, "%publisher%")
        new_name = self.replace_token(new_name, md.title, "%title%")
        new_name = self.replace_token(new_name, md.month, "%month%")
        month_name = None
        if md.month is not None:
            if (isinstance(md.month, str) and md.month.isdigit()) or isinstance(md.month, int):
                if int(md.month) in range(1, 13):
                    dt = datetime.datetime(1970, int(md.month), 1, 0, 0)
                    month_name = dt.strftime("%B")
        new_name = self.replace_token(new_name, month_name, "%month_name%")

        new_name = self.replace_token(new_name, md.genre, "%genre%")
        new_name = self.replace_token(new_name, md.language, "%language_code%")
        new_name = self.replace_token(new_name, md.critical_rating, "%criticalrating%")
        new_name = self.replace_token(new_name, md.alternate_series, "%alternateseries%")
        new_name = self.replace_token(new_name, md.alternate_number, "%alternatenumber%")
        new_name = self.replace_token(new_name, md.alternate_count, "%alternatecount%")
        new_name = self.replace_token(new_name, md.imprint, "%imprint%")
        new_name = self.replace_token(new_name, md.format, "%format%")
        new_name = self.replace_token(new_name, md.maturity_rating, "%maturityrating%")
        new_name = self.replace_token(new_name, md.story_arc, "%storyarc%")
        new_name = self.replace_token(new_name, md.series_group, "%seriesgroup%")
        new_name = self.replace_token(new_name, md.scan_info, "%scaninfo%")

        if self.smart_cleanup:
            # remove empty braces,brackets, parentheses
            new_name = re.sub(r"\(\s*[-:]*\s*\)", "", new_name)
            new_name = re.sub(r"\[\s*[-:]*\s*]", "", new_name)
            new_name = re.sub(r"{\s*[-:]*\s*}", "", new_name)

            # remove duplicate spaces
            new_name = " ".join(new_name.split())

            # remove remove duplicate -, _,
            new_name = re.sub(r"[-_]{2,}\s+", "-- ", new_name)
            new_name = re.sub(r"(\s--)+", " --", new_name)
            new_name = re.sub(r"(\s-)+", " -", new_name)

            # remove dash or double dash at end of line
            new_name = re.sub(r"[-]{1,2}\s*$", "", new_name)

            # remove duplicate spaces (again!)
            new_name = " ".join(new_name.split())

        new_name += ext

        # some tweaks to keep various filesystems happy
        new_name = new_name.replace("/", "-")
        new_name = new_name.replace(" :", " -")
        new_name = new_name.replace(": ", " - ")
        new_name = new_name.replace(":", "-")
        new_name = new_name.replace("?", "")

        return new_name


class MetadataFormatter(string.Formatter):
    def __init__(self, smart_cleanup=False):
        super().__init__()
        self.smart_cleanup = smart_cleanup

    def format_field(self, value, format_spec):
        if value is None or value == "":
            return ""
        return super().format_field(value, format_spec)

    def _vformat(self, format_string, args, kwargs, used_args, recursion_depth, auto_arg_index=0):
        if recursion_depth < 0:
            raise ValueError("Max string recursion exceeded")
        result = []
        lstrip = False
        for literal_text, field_name, format_spec, conversion in self.parse(format_string):

            # output the literal text
            if literal_text:
                if lstrip:
                    result.append(literal_text.lstrip("-_)}]#"))
                else:
                    result.append(literal_text)
            lstrip = False
            # if there's a field, output it
            if field_name is not None:
                field_name = field_name.lower()
                # this is some markup, find the object and do
                #  the formatting

                # handle arg indexing when empty field_names are given.
                if field_name == "":
                    if auto_arg_index is False:
                        raise ValueError(
                            "cannot switch from manual field " "specification to automatic field " "numbering"
                        )
                    field_name = str(auto_arg_index)
                    auto_arg_index += 1
                elif field_name.isdigit():
                    if auto_arg_index:
                        raise ValueError(
                            "cannot switch from manual field " "specification to automatic field " "numbering"
                        )
                    # disable auto arg incrementing, if it gets
                    # used later on, then an exception will be raised
                    auto_arg_index = False

                # given the field_name, find the object it references
                #  and the argument it came from
                obj, arg_used = self.get_field(field_name, args, kwargs)
                used_args.add(arg_used)

                # do any conversion on the resulting object
                obj = self.convert_field(obj, conversion)

                # expand the format spec, if needed
                format_spec, auto_arg_index = self._vformat(
                    format_spec, args, kwargs, used_args, recursion_depth - 1, auto_arg_index=auto_arg_index
                )

                # format the object and append to the result
                fmt_obj = self.format_field(obj, format_spec)
                if fmt_obj == "" and len(result) > 0 and self.smart_cleanup:
                    lstrip = True
                    result.pop()
                result.append(fmt_obj)

        return "".join(result), auto_arg_index


class FileRenamer2:
    def __init__(self, metadata):
        self.template = "{publisher}/{series}/{series} v{volume} #{issue} (of {issue_count}) ({year})"
        self.smart_cleanup = True
        self.issue_zero_padding = 3
        self.metadata = metadata
        self.move = False

    def set_metadata(self, metadata: GenericMetadata):
        self.metadata = metadata

    def set_issue_zero_padding(self, count):
        self.issue_zero_padding = count

    def set_smart_cleanup(self, on):
        self.smart_cleanup = on

    def set_template(self, template: str):
        self.template = template

    def determine_name(self, ext):
        class Default(dict):
            def __missing__(self, key):
                return "{" + key + "}"

        md = self.metadata

        # padding for issue
        md.issue = IssueString(md.issue).as_string(pad=self.issue_zero_padding)

        template = self.template

        path_components = template.split(os.sep)
        new_name = ""

        fmt = MetadataFormatter(self.smart_cleanup)
        md_dict = vars(md)
        for role in ["writer", "penciller", "inker", "colorist", "letterer", "cover artist", "editor"]:
            md_dict[role] = md.get_primary_credit(role)

        if (isinstance(md.month, int) or isinstance(md.month, str) and md.month.isdigit()) and 0 < int(md.month) < 13:
            md_dict["month_name"] = calendar.month_name[int(md.month)]
            md_dict["month_abbr"] = calendar.month_abbr[int(md.month)]
        else:
            print(md.month)
            md_dict["month_name"] = ""
            md_dict["month_abbr"] = ""

        for Component in path_components:
            new_name = os.path.join(
                new_name, fmt.vformat(Component, args=[], kwargs=Default(md_dict)).replace("/", "-")
            )

        new_name += ext

        # # some tweaks to keep various filesystems happy
        # new_name = new_name.replace(": ", " - ")
        # new_name = new_name.replace(":", "-")

        # remove padding
        md.issue = IssueString(md.issue).as_string()
        if self.move:
            return sanitize_filepath(new_name.strip())
        else:
            return os.path.basename(sanitize_filepath(new_name.strip()))
