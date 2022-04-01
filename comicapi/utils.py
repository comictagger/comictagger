"""Some generic utilities"""

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

import codecs
import locale
import os
import platform
import re
import sys
import unicodedata
from collections import defaultdict

import pycountry


class UtilsVars:
    already_fixed_encoding = False


def indent(elem, level=0):
    # for making the XML output readable
    i = "\n" + level * "  "
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = i + "  "
        if not elem.tail or not elem.tail.strip():
            elem.tail = i
        for ele in elem:
            indent(ele, level + 1)
        if not elem.tail or not elem.tail.strip():
            elem.tail = i
    else:
        if level and (not elem.tail or not elem.tail.strip()):
            elem.tail = i


def get_actual_preferred_encoding():
    preferred_encoding = locale.getpreferredencoding()
    if platform.system() == "Darwin":
        preferred_encoding = "utf-8"
    return preferred_encoding


def fix_output_encoding():
    if not UtilsVars.already_fixed_encoding:
        # this reads the environment and inits the right locale
        locale.setlocale(locale.LC_ALL, "")

        # try to make stdout/stderr encodings happy for unicode printing
        preferred_encoding = get_actual_preferred_encoding()
        sys.stdout = codecs.getwriter(preferred_encoding)(sys.stdout)
        sys.stderr = codecs.getwriter(preferred_encoding)(sys.stderr)
        UtilsVars.already_fixed_encoding = True


def get_recursive_filelist(pathlist):
    """Get a recursive list of of all files under all path items in the list"""

    filelist = []
    for p in pathlist:
        # if path is a folder, walk it recursively, and all files underneath
        if not isinstance(p, str):
            # it's probably a QString
            p = str(p)

        if os.path.isdir(p):
            for root, _, files in os.walk(p):
                for f in files:
                    if not isinstance(f, str):
                        # it's probably a QString
                        f = str(f)
                    filelist.append(os.path.join(root, f))
        else:
            filelist.append(p)

    return filelist


def list_to_string(lst):
    string = ""
    if lst is not None:
        for item in lst:
            if len(string) > 0:
                string += ", "
            string += item
    return string


def add_to_path(dirname):
    if dirname is not None and dirname != "":

        # verify that path doesn't already contain the given dirname
        tmpdirname = re.escape(dirname)
        pattern = r"(^|{sep}){dir}({sep}|$)".format(dir=tmpdirname, sep=os.pathsep)

        match = re.search(pattern, os.environ["PATH"])
        if not match:
            os.environ["PATH"] = dirname + os.pathsep + os.environ["PATH"]


def which(program):
    """Returns path of the executable, if it exists"""

    def is_exe(fpath):
        return os.path.isfile(fpath) and os.access(fpath, os.X_OK)

    fpath, _ = os.path.split(program)
    if fpath:
        if is_exe(program):
            return program
    else:
        for path in os.environ["PATH"].split(os.pathsep):
            exe_file = os.path.join(path, program)
            if is_exe(exe_file):
                return exe_file

    return None


def xlate(data, is_int=False):
    if data is None or data == "":
        return None
    if is_int:
        i = str(data).translate(defaultdict(lambda: None, zip((ord(c) for c in "1234567890"), "1234567890")))
        if i == "0":
            return "0"
        if i == "":
            return None
        return int(i)

    return str(data)


def remove_articles(text):
    text = text.lower()
    articles = [
        "&",
        "a",
        "am",
        "an",
        "and",
        "as",
        "at",
        "be",
        "but",
        "by",
        "for",
        "if",
        "is",
        "issue",
        "it",
        "it's",
        "its",
        "itself",
        "of",
        "or",
        "so",
        "the",
        "the",
        "with",
    ]
    new_text = ""
    for word in text.split(" "):
        if word not in articles:
            new_text += word + " "

    new_text = new_text[:-1]

    return new_text


def sanitize_title(text):
    # normalize unicode and convert to ascii. Does not work for everything eg ½ to 1⁄2 not 1/2
    # this will probably cause issues with titles in other character sets e.g. chinese, japanese
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    # comicvine keeps apostrophes a part of the word
    text = text.replace("'", "")
    text = text.replace('"', "")
    # comicvine ignores punctuation and accents
    text = re.sub(r"[^A-Za-z0-9]+", " ", text)
    # remove extra space and articles and all lower case
    text = remove_articles(text).lower().strip()

    return text


def unique_file(file_name):
    counter = 1
    file_name_parts = os.path.splitext(file_name)
    while True:
        if not os.path.lexists(file_name):
            return file_name
        file_name = file_name_parts[0] + " (" + str(counter) + ")" + file_name_parts[1]
        counter += 1


languages = defaultdict(lambda: None)

countries = defaultdict(lambda: None)

for c in pycountry.countries:
    if "alpha_2" in c._fields:
        countries[c.alpha_2] = c.name

for lng in pycountry.languages:
    if "alpha_2" in lng._fields:
        languages[lng.alpha_2] = lng.name


def get_language_from_iso(iso: str):
    return languages[iso]


def get_language(string):
    if string is None:
        return None

    lang = get_language_from_iso(string)

    if lang is None:
        try:
            return pycountry.languages.lookup(string).name
        except:
            return None
    return lang
