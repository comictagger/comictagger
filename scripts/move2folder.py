#!/usr/bin/python
"""Moves comic files based on metadata organizing in a tree by Publisher/Series (Volume)"""

# This script is based on make_links.py by Anthony Beville

# Copyright 2015 Fabio Cancedda, Anthony Beville

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at

#     http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import shutil
#import sys
#import os
#import platform

from comictaggerlib.settings import *
from comicapi.comicarchive import *
#from comicapi.issuestring import *
#import comicapi.utils


def make_folder(folder):
    if not os.path.exists(folder):
        try:
            os.makedirs(folder)
        except Exception as e:
            print "{0} Can't make {1} -- quitting".format(e, folder)
            quit()


def move_file(source, filename):
    if not os.path.exists(filename):
        shutil.move(os.path.abspath(source), filename)


def main():
    utils.fix_output_encoding()
    settings = ComicTaggerSettings()

    style = MetaDataStyle.CIX

    if platform.system() == "Windows":
        print >> sys.stderr, "Sorry, this script works only on UNIX systems"

    if len(sys.argv) < 3:
        print >> sys.stderr, "Usage: {0} [comic_root][tree_root]".format(
            sys.argv[0])
        return

    comic_root = sys.argv[1]
    tree_root = sys.argv[2]

    print "Root is:", comic_root
    if not os.path.exists(comic_root):
        print >> sys.stderr, "The comic root doesn't seem a directory or it doesn't exists. -- quitting"
        return

    filelist = utils.get_recursive_filelist([comic_root])

    if len(filelist) == 0:
        print >> sys.stderr, "The comic root seems empty. -- quitting"
        return

    make_folder(tree_root)

    # first find all comics with metadata
    print "Reading in all comics..."
    comic_list = []
    max_name_len = 2
    fmt_str = ""
    for filename in filelist:
        ca = ComicArchive(filename, settings.rar_exe_path, ComicTaggerSettings.getGraphic('nocover.png'))
        if ca.seemsToBeAComicArchive() and ca.hasMetadata(style):

            comic_list.append((filename, ca.readMetadata(style)))

            max_name_len = max(max_name_len, len(filename))
            fmt_str = u"{{0:{0}}}".format(max_name_len)
            print >> sys.stderr, fmt_str.format(filename) + "\r",
            sys.stderr.flush()

    print >> sys.stderr, fmt_str.format("")

    print "Found {0} tagged comics.".format(len(comic_list))

    # walk through the comic list and moves each one
    for filename, md in comic_list:
        print >> sys.stderr, fmt_str.format(filename) + "\r",
        sys.stderr.flush()

        # do publisher/series organizing:
        series_name = md.series
        publisher_name = md.publisher
        start_year = md.volume
        if series_name is not None:
            # some tweaks to keep various filesystems happy
            series_name = series_name.replace(":", " -")
            series_name = series_name.replace("/", "-")
            series_name = series_name.replace("?", "")
        series_folder = os.path.join(
            tree_root,
            unicode(publisher_name),
            unicode(series_name) + " (" + unicode(start_year) + ")")
        make_folder(series_folder)
        move_file(filename, os.path.join(
            series_folder, os.path.basename(filename)))

if __name__ == '__main__':
    main()
