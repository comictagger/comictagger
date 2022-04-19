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

import datetime
import logging
import os
import string

from pathvalidate import sanitize_filepath

from comicapi.genericmetadata import GenericMetadata
from comicapi.issuestring import IssueString

logger = logging.getLogger(__name__)


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


class FileRenamer:
    def __init__(self, metadata):
        self.template = "{publisher}/{series}/{series} v{volume} #{issue} (of {issueCount}) ({year})"
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

    def determine_name(self, filename, ext=None):
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
        for Component in path_components:
            new_name = os.path.join(
                new_name, fmt.vformat(Component, args=[], kwargs=Default(vars(md))).replace("/", "-")
            )

        if ext is None or ext == "":
            ext = os.path.splitext(filename)[1]

        new_name += ext

        # some tweaks to keep various filesystems happy
        new_name = new_name.replace(": ", " - ")
        new_name = new_name.replace(":", "-")

        # remove padding
        md.issue = IssueString(md.issue).as_string()
        if self.move:
            return sanitize_filepath(new_name.strip())
        else:
            return os.path.basename(sanitize_filepath(new_name.strip()))
