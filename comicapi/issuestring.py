"""Support for mixed digit/string type Issue field

Class for handling the odd permutations of an 'issue number' that the
comics industry throws at us.
  e.g.: "12", "12.1", "0", "-1", "5AU", "100-2"
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
from __future__ import annotations

import logging
import unicodedata

logger = logging.getLogger(__name__)


class IssueString:
    def __init__(self, text: str | None) -> None:
        # break up the issue number string into 2 parts: the numeric and suffix string.
        # (assumes that the numeric portion is always first)

        self.num = None
        self.suffix = ""
        self.prefix = ""

        if text is None:
            return

        text = str(text)

        if len(text) == 0:
            return

        for idx, r in enumerate(text):
            if not r.isalpha():
                break
        self.prefix = text[:idx]
        self.num, self.suffix = self.get_number(text[idx:])

    def get_number(self, text: str) -> tuple[float | None, str]:
        num, suffix = None, ""
        start = 0
        # skip the minus sign if it's first
        if text[0] in ("-", "+"):
            start = 1

        # if it's still not numeric at start skip it
        if text[start].isdigit() or text[start] == ".":
            # walk through the string, look for split point (the first non-numeric)
            decimal_count = 0
            for idx in range(start, len(text)):
                if not (text[idx].isdigit() or text[idx] in "."):
                    break
                # special case: also split on second "."
                if text[idx] == ".":
                    decimal_count += 1
                    if decimal_count > 1:
                        break
            else:
                idx = len(text)

            # move trailing numeric decimal to suffix
            # (only if there is other junk after )
            if text[idx - 1] == "." and len(text) != idx:
                idx = idx - 1

            # if there is no numeric after the minus, make the minus part of the suffix
            if idx == 1 and start == 1:
                idx = 0

            if text[0:idx]:
                num = float(text[0:idx])
            suffix = text[idx : len(text)]
        else:
            suffix = text
        return num, suffix

    def as_string(self, pad: int = 0) -> str:
        """return the number, left side zero-padded, with suffix attached"""

        # if there is no number return the text
        if self.num is None:
            return self.prefix + self.suffix

        # negative is added back in last
        negative = self.num < 0
        num_f = abs(self.num)

        # used for padding
        num_int = int(num_f)

        if num_f.is_integer():
            num_s = str(num_int)
        else:
            num_s = str(num_f)

        # create padding
        padding = ""
        # we only pad the whole number part, we don't care about the decimal
        length = len(str(num_int))
        if length < pad:
            padding = "0" * (pad - length)

        # add the padding to the front
        num_s = padding + num_s

        # finally add the negative back in
        if negative:
            num_s = "-" + num_s

        # return the prefix + formatted number + suffix
        return self.prefix + num_s + self.suffix

    def as_float(self) -> float | None:
        # return the float, with no suffix
        if len(self.suffix) == 1 and self.suffix.isnumeric():
            return (self.num or 0) + unicodedata.numeric(self.suffix)
        return self.num
