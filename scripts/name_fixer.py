#!/usr/bin/python
"""Fix the comic file names using a list of transforms"""

# Copyright 2013 Anthony Beville

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at

#     http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import argparse
import json
#import sys
#import os
#import re

from comictaggerlib.comicarchive import *
from comictaggerlib.settings import *
from comictaggerlib.filerenamer import *
#import comictaggerlib.utils


def parse_args():

    input_args = sys.argv[1:]

    parser = argparse.ArgumentParser(
        description='A script to rename comic files')
    parser.add_argument(
        '-t',
        '--transforms',
        metavar='xformfile',
        help="The file with transforms")
    parser.add_argument(
        '-n',
        '--noconfirm',
        action='store_true',
        help="Don't confirm before rename")
    parser.add_argument('paths', metavar='PATH', type=str,
                        nargs='+', help='path to look for comic files')
    parsed_args = parser.parse_args(input_args)

    return parsed_args


def calculate_rename(ca, md, settings):

    new_ext = None  # default
    if settings.rename_extension_based_on_archive:
        if ca.isZip():
            new_ext = ".cbz"
        elif ca.isRar():
            new_ext = ".cbr"

    renamer = FileRenamer(md)
    renamer.setTemplate(
        "%series% V%volume% #%issue% (of %issuecount%) (%year%) %scaninfo%")
    renamer.setIssueZeroPadding(0)
    renamer.setSmartCleanup(settings.rename_use_smart_string_cleanup)

    return renamer.determineName(ca.path, ext=new_ext)


def perform_rename(filelist):
    for old_name, new_name in filelist:
        folder = os.path.dirname(os.path.abspath(old_name))
        new_abs_path = utils.unique_file(os.path.join(folder, new_name))

        os.rename(old_name, new_abs_path)
        print u"Renamed '{0}' -> '{1}'".format(os.path.basename(old_name), new_name)


def main():

    default_xform_list = [
        ["^2000AD$", "2000 AD"],
        ["^G\.{0,1}I\.{0,1}Joe$", "G.I. Joe"],
    ]

    utils.fix_output_encoding()
    settings = ComicTaggerSettings()

    style = MetaDataStyle.CIX

    parsed_args = parse_args()

    # parsed_args.noconfirm
    if parsed_args.transforms is not None:
        print "Reading in transforms from:", parsed_args.transforms
        json_data = open(parsed_args.transforms).read()
        data = json.loads(json_data)
        xform_list = data['xforms']
    else:
        xform_list = default_xform_list

    #pprint( xform_list, indent=4)

    filelist = utils.get_recursive_filelist(parsed_args.paths)

    # first find all comics
    print "Reading in all comics..."
    comic_list = []
    max_name_len = 2
    fmt_str = ""
    for filename in filelist:
        ca = ComicArchive(filename, settings.rar_exe_path)
        # do we care if it already has metadata?
        if ca.seemsToBeAComicArchive() and not ca.hasMetadata(style):

            comic_list.append(ca)

            max_name_len = max(max_name_len, len(filename))
            fmt_str = u"{{0:{0}}}".format(max_name_len)
            print >> sys.stderr, fmt_str.format(filename) + "\r",
            sys.stderr.flush()

    print >> sys.stderr, fmt_str.format("")
    print "Found {0} comics.".format(len(comic_list))

    modify_list = list()
    # walk through the comic list fix the file names
    for ca in comic_list:

        # 1. parse the filename into a MD object
        md = ca.metadataFromFilename()
        # 2. walk through list of transforms
        if md.series is not None and md.series != "":
            for pattern, replacement in xform_list:
                # apply each transform
                new_series = re.sub(pattern, replacement, md.series)
                if new_series != md.series:
                    md.series = new_series
                    new_name = calculate_rename(ca, md, settings)

                    # found a match.  add to proposed list, and bail on this
                    # file
                    modify_list.append((ca.path, new_name))
                    break

    print "{0} filenames to modify".format(len(modify_list))
    if len(modify_list) > 0:
        if parsed_args.noconfirm:
            print "Not confirming before rename"
        else:
            for old_name, new_name in modify_list:
                print u"'{0}' -> '{1}'".format(os.path.basename(old_name), new_name)

            i = raw_input("Do you want to proceed with rename? [y/N] ")
            if i.lower() not in ('y', 'yes'):
                print "exiting without rename."
                sys.exit(0)

        perform_rename(modify_list)

if __name__ == '__main__':
    main()
