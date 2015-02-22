#!/usr/bin/python
"""Test archive cover against Comic Vine for a given issue ID
"""

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

#import sys
#import os

from comictaggerlib.settings import *
from comictaggerlib.comicarchive import *
from comictaggerlib.issueidentifier import *
from comictaggerlib.comicvinetalker import *
#import comictaggerlib.utils


def main():

    utils.fix_output_encoding()
    settings = ComicTaggerSettings()

    if len(sys.argv) < 3:
        print >> sys.stderr, "Usage: {0} [comicfile][issueid]".format(
            sys.argv[0])
        return

    filename = sys.argv[1]
    issue_id = sys.argv[2]

    if not os.path.exists(filename):
        print >> sys.stderr, filename + ": not found!"
        return

    ca = ComicArchive(filename, settings.rar_exe_path)
    if not ca.seemsToBeAComicArchive():
        print >> sys.stderr, "Sorry, but " + \
            filename + " is not a comic archive!"
        return

    ii = IssueIdentifier(ca, settings)

    # calculate the hashes of the first two pages
    cover_image_data = ca.getPage(0)
    cover_hash0 = ii.calculateHash(cover_image_data)
    cover_image_data = ca.getPage(1)
    cover_hash1 = ii.calculateHash(cover_image_data)
    hash_list = [cover_hash0, cover_hash1]

    comicVine = ComicVineTalker()
    result = ii.getIssueCoverMatchScore(
        comicVine, issue_id, hash_list, useRemoteAlternates=True, useLog=False)

    print "Best cover match score is:", result['score']
    if result['score'] < ii.min_alternate_score_thresh:
        print "Looks like a match!"
    else:
        print "Bad score, maybe not a match?"
    print result['url']


if __name__ == '__main__':
    main()
