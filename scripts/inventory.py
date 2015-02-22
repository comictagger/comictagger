#!/usr/bin/python
"""Print out a line-by-line list of basic tag info from all comics"""

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

from comictaggerlib.comicarchive import *
from comictaggerlib.settings import *
from comictaggerlib.issuestring import *
#import comictaggerlib.utils


def main():
    utils.fix_output_encoding()
    settings = ComicTaggerSettings()

    style = MetaDataStyle.CIX

    if len(sys.argv) < 2:
        print >> sys.stderr, "Usage: {0} [comic_folder]".format(sys.argv[0])
        return

    filelist = utils.get_recursive_filelist(sys.argv[1:])

    # first read in metadata from all files
    metadata_list = []
    max_name_len = 2
    for filename in filelist:
        ca = ComicArchive(filename, settings.rar_exe_path)
        if ca.hasMetadata(style):
            # make a list of paired file names and metadata objects
            metadata_list.append((filename, ca.readMetadata(style)))

            max_name_len = max(max_name_len, len(filename))
            fmt_str = u"{{0:{0}}}".format(max_name_len)
            print >> sys.stderr, fmt_str.format(filename) + "\r",
            sys.stderr.flush()

    print >> sys.stderr, fmt_str.format("") + "\r",
    print "--------------------------------------------------------------------------"
    print "Found {0} comics with {1} tags".format(len(metadata_list), MetaDataStyle.name[style])
    print "--------------------------------------------------------------------------"

    # now, figure out column widths
    w0 = 4
    w1 = 4
    for filename, md in metadata_list:
        if not md.isEmpty:
            w0 = max(len((os.path.split(filename)[1])), w0)
            if md.series is not None:
                w1 = max(len(md.series), w1)
    w0 += 2

    # build a format string
    fmt_str = u"{0:" + str(w0) + "} {1:" + str(w1) + "} #{2:6} ({3})"

    # now sort the list by issue, and then series
    metadata_list.sort(
        key=lambda x: IssueString(x[1].issue).asString(3), reverse=False)
    metadata_list.sort(
        key=lambda x: unicode(x[1].series).lower() + str(x[1].year), reverse=False)

    # now print
    for filename, md in metadata_list:
        if not md.isEmpty:
            print fmt_str.format(os.path.split(filename)[1] + ":", md.series, md.issue, md.year), md.title

if __name__ == '__main__':
    main()
