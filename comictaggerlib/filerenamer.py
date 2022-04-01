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
import os
import re

from comicapi.genericmetadata import GenericMetadata
from comicapi.issuestring import IssueString


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

    def determine_name(self, filename, ext=None):

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

        if ext is None:
            ext = os.path.splitext(filename)[1]

        new_name += ext

        # some tweaks to keep various filesystems happy
        new_name = new_name.replace("/", "-")
        new_name = new_name.replace(" :", " -")
        new_name = new_name.replace(": ", " - ")
        new_name = new_name.replace(":", "-")
        new_name = new_name.replace("?", "")

        return new_name
