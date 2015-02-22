#!/usr/bin/python
"""Find all duplicate comics"""

#import sys

from comictaggerlib.comicarchive import *
from comictaggerlib.settings import *
#from comictaggerlib.issuestring import *
#import comictaggerlib.utils


def main():
    utils.fix_output_encoding()
    settings = ComicTaggerSettings()

    style = MetaDataStyle.CIX

    if len(sys.argv) < 2:
        print >> sys.stderr, "Usage:  {0} [comic_folder]".format(sys.argv[0])
        return

    filelist = utils.get_recursive_filelist(sys.argv[1:])

    # first find all comics with metadata
    print >> sys.stderr, "Reading in all comics..."
    comic_list = []
    fmt_str = ""
    max_name_len = 2
    for filename in filelist:
        ca = ComicArchive(filename, settings.rar_exe_path)
        if ca.seemsToBeAComicArchive() and ca.hasMetadata(style):
            max_name_len = max(max_name_len, len(filename))
            fmt_str = u"{{0:{0}}}".format(max_name_len)
            print >> sys.stderr, fmt_str.format(filename) + "\r",
            sys.stderr.flush()
            comic_list.append((filename, ca.readMetadata(style)))

    print >> sys.stderr, fmt_str.format("") + "\r",
    print "--------------------------------------------------------------------------"
    print "Found {0} comics with {1} tags".format(len(comic_list), MetaDataStyle.name[style])
    print "--------------------------------------------------------------------------"

    # sort the list by series+issue+year, to put all the dupes together
    def makeKey(x):
        return "<" + unicode(x[1].series) + u" #" + \
            unicode(x[1].issue) + u" - " + unicode(x[1].year) + ">"
    comic_list.sort(key=makeKey, reverse=False)

    # look for duplicate blocks
    dupe_set_list = list()
    dupe_set = list()
    prev_key = ""
    for filename, md in comic_list:
        print >> sys.stderr, fmt_str.format(filename) + "\r",
        sys.stderr.flush()

        new_key = makeKey((filename, md))

        # if the new key same as the last, add to to dupe set
        if new_key == prev_key:
            dupe_set.append(filename)

        # else we're on a new potential block
        else:
            # only add if the dupe list has 2 or more
            if len(dupe_set) > 1:
                dupe_set_list.append(dupe_set)
            dupe_set = list()
            dupe_set.append(filename)

        prev_key = new_key

    print >> sys.stderr, fmt_str.format("") + "\r",
    print "Found {0} duplicate sets".format(len(dupe_set_list))

    for dupe_set in dupe_set_list:
        ca = ComicArchive(dupe_set[0], settings.rar_exe_path)
        md = ca.readMetadata(style)
        print "{0} #{1} ({2})".format(md.series, md.issue, md.year)
        for filename in dupe_set:
            print "------>{0}".format(filename)

if __name__ == '__main__':
    main()
