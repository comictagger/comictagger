#!/usr/bin/python
"""
Make some tree structures and symbolic links to comic files based on metadata
organizing by date and series, in different trees
"""

# Copyright 2012 Anthony Beville

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at

#     http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

#import sys
#import os
#import platform

from comictaggerlib.comicarchive import *
from comictaggerlib.settings import *
#from comictaggerlib.issuestring import *
#import comictaggerlib.utils


def make_folder(folder):
    if not os.path.exists(folder):
        try:
            os.makedirs(folder)
        except Exception as e:
            print "{0} Can't make {1} -- quitting".format(e, folder)
            quit()


def make_link(source, link):
    if not os.path.exists(link):
        os.symlink(os.path.abspath(source), link)


def main():
    utils.fix_output_encoding()
    settings = ComicTaggerSettings()

    style = MetaDataStyle.CIX

    if platform.system() == "Windows":
        print >> sys.stderr, "Sorry, this script works only on UNIX systems"

    if len(sys.argv) < 3:
        print >> sys.stderr, "Usage: {0} [comic_root][link_root]".format(
            sys.argv[0])
        return

    comic_root = sys.argv[1]
    link_root = sys.argv[2]

    print "Root is:", comic_root
    filelist = utils.get_recursive_filelist([comic_root])
    make_folder(link_root)

    # first find all comics with metadata
    print "Reading in all comics..."
    comic_list = []
    max_name_len = 2
    for filename in filelist:
        ca = ComicArchive(filename, settings.rar_exe_path)
        if ca.seemsToBeAComicArchive() and ca.hasMetadata(style):

            comic_list.append((filename, ca.readMetadata(style)))

            max_name_len = max(max_name_len, len(filename))
            fmt_str = u"{{0:{0}}}".format(max_name_len)
            print >> sys.stderr, fmt_str.format(filename) + "\r",
            sys.stderr.flush()

    print >> sys.stderr, fmt_str.format("")
    print "Found {0} tagged comics.".format(len(comic_list))

    # walk through the comic list and add subdirs and links for each one
    for filename, md in comic_list:
        print >> sys.stderr, fmt_str.format(filename) + "\r",
        sys.stderr.flush()

        # do date organizing:
        if md.month is not None:
            month_str = "{0:02d}".format(int(md.month))
        else:
            month_str = "00"
        date_folder = os.path.join(link_root, "date", str(md.year), month_str)
        make_folder(date_folder)
        make_link(
            filename, os.path.join(date_folder, os.path.basename(filename)))

        # do publisher/series organizing:
        fixed_series_name = md.series
        if fixed_series_name is not None:
            # some tweaks to keep various filesystems happy
            fixed_series_name = fixed_series_name.replace("/", "-")
            fixed_series_name = fixed_series_name.replace("?", "")
        series_folder = os.path.join(
            link_root, "series", str(md.publisher), unicode(fixed_series_name))
        make_folder(series_folder)
        make_link(filename, os.path.join(
            series_folder, os.path.basename(filename)))

if __name__ == '__main__':
    main()
