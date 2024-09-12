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
import posixpath
import re
from urllib.parse import urlsplit

logger = logging.getLogger(__name__)


def fix_url(url: str | None) -> str:
    if not url:
        return ""
    tmp_url = urlsplit(url)
    new_path = posixpath.normpath(tmp_url.path)
    if new_path in (".", "/"):
        new_path = ""
    # joinurl only works properly if there is a trailing slash
    tmp_url = tmp_url._replace(path=new_path + "/")
    return tmp_url.geturl()


def cleanup_html(string: str | None, remove_html_tables: bool = False) -> str:
    """Cleans HTML code from any text. Will remove any HTML tables with remove_html_tables"""
    if string is None:
        return ""
    if "<" not in string:
        return string
    from bs4 import BeautifulSoup

    # find any tables
    soup = BeautifulSoup(string, "html.parser")
    tables = soup.findAll("table")

    # put in our own
    string = re.sub(r"<br>|</li>", "\n", string, flags=re.IGNORECASE)
    string = re.sub(r"</p>", "\n\n", string, flags=re.IGNORECASE)
    string = re.sub(r"<h([1-6])>", "*", string, flags=re.IGNORECASE)
    string = re.sub(r"</h[1-6]>", "*\n", string, flags=re.IGNORECASE)

    # remove the tables
    p = re.compile(r"<table[^<]*?>.*?</table>")
    if remove_html_tables:
        string = p.sub("", string)
        string = string.replace("*List of covers and their creators:*", "")
    else:
        string = p.sub("{}", string)

    # now strip all other tags
    p = re.compile(r"<[^<]*?>")
    newstring = p.sub("", string)

    newstring = newstring.replace("&nbsp;", " ")
    newstring = newstring.replace("&amp;", "&")
    newstring = newstring.replace("&#039;", "'")

    newstring = newstring.strip()

    if not remove_html_tables:
        # now rebuild the tables into text from BSoup
        try:
            table_strings = []
            for table in tables:
                rows = []
                hdrs = []
                col_widths = []
                for hdr in table.findAll("th"):
                    item = hdr.string.strip()
                    hdrs.append(item)
                    col_widths.append(len(item))
                rows.append(hdrs)

                for row in table.findAll("tr"):
                    cols = []
                    col = row.findAll("td")

                    for i, c in enumerate(col):
                        item = c.string.strip()
                        cols.append(item)
                        if len(item) > col_widths[i]:
                            col_widths[i] = len(item)

                    if len(cols) != 0:
                        rows.append(cols)
                # now we have the data, make it into text
                fmtstr = "|"
                for w in col_widths:
                    fmtstr += f" {{:{w + 1}}}|"
                table_text = ""

                for counter, row in enumerate(rows):
                    table_text += fmtstr.format(*row) + "\n"
                    if counter == 0 and len(hdrs) != 0:
                        table_text += "|"
                        for w in col_widths:
                            table_text += "-" * (w + 2) + "|"
                        table_text += "\n"

                table_strings.append(table_text + "\n")

            newstring = newstring.format(*table_strings)
        except Exception:
            # we caught an error rebuilding the table.
            # just bail and remove the formatting
            logger.exception("table parse error")
            newstring.replace("{}", "")

    return newstring
