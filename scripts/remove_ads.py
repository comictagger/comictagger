#!/usr/bin/python
"""
Create new comic archives from old one, removing  pages marked as ads
and deleted. Walks recursively through the given folders.  Originals
are kept in a sub-folder at the level of the original
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

import sys
import os
import tempfile
import zipfile
import shutil

import comictaggerlib.utils
from comictaggerlib.settings import *
from comictaggerlib.comicarchive import *

subfolder_name = "PRE_AD_REMOVAL"
unwanted_types = ['Deleted', 'Advertisement']


def main():
    utils.fix_output_encoding()
    settings = ComicTaggerSettings()

    # this can only work with files with ComicRack tags
    style = MetaDataStyle.CIX

    if len(sys.argv) < 2:
        print >> sys.stderr, "Usage: {0} [comic_folder]".format(sys.argv[0])
        return

    filelist = utils.get_recursive_filelist(sys.argv[1:])

    # first read in CIX metadata from all files, make a list of candidates
    modify_list = []
    for filename in filelist:

        ca = ComicArchive(filename, settings.rar_exe_path)
        if (ca.isZip or ca.isRar()) and ca.hasMetadata(style):
            md = ca.readMetadata(style)
            if len(md.pages) != 0:
                for p in md.pages:
                    if 'Type' in p and p['Type'] in unwanted_types:
                        # This one has pages to remove.  add to list!
                        modify_list.append((filename, md))
                        break

    # now actually process those files
    for filename, md in modify_list:
        ca = ComicArchive(filename, settings.rar_exe_path)
        curr_folder = os.path.dirname(filename)
        curr_subfolder = os.path.join(curr_folder, subfolder_name)

        # skip any of our generated subfolders...
        if os.path.basename(curr_folder) == subfolder_name:
            continue
        sys.stdout.write("Removing unwanted pages from " + filename)

        # verify that we can write to current folder
        if not os.access(filename, os.W_OK):
            print "Can't move: {0}: skipped!".format(filename)
            continue
        if not os.path.exists(curr_subfolder) and not os.access(
                curr_folder, os.W_OK):
            print "Can't create subfolder here: {0}: skipped!".format(filename)
            continue
        if not os.path.exists(curr_subfolder):
            os.mkdir(curr_subfolder)
        if not os.access(curr_subfolder, os.W_OK):
            print "Can't write to the subfolder here: {0}: skipped!".format(filename)
            continue

        # generate a new file with temp name
        tmp_fd, tmp_name = tempfile.mkstemp(dir=os.path.dirname(filename))
        os.close(tmp_fd)

        try:
            zout = zipfile.ZipFile(tmp_name, 'w')

            # now read in all the pages from the old one, except the ones we
            # want to skip
            new_num = 0
            new_pages = list()
            for p in md.pages:
                if 'Type' in p and p['Type'] in unwanted_types:
                    continue
                else:
                    pageNum = int(p['Image'])
                    name = ca.getPageName(pageNum)
                    buffer = ca.getPage(pageNum)
                    sys.stdout.write('.')
                    sys.stdout.flush()

                    # Generate a new name for the page file
                    ext = os.path.splitext(name)[1]
                    new_name = "page{0:04d}{1}".format(new_num, ext)
                    zout.writestr(new_name, buffer)

                    # create new page entry
                    new_p = dict()
                    new_p['Image'] = str(new_num)
                    if 'Type' in p:
                        new_p['Type'] = p['Type']
                    new_pages.append(new_p)
                    new_num += 1

            # preserve the old comment
            comment = ca.archiver.getArchiveComment()
            if comment is not None:
                zout.comment = ca.archiver.getArchiveComment()

        except Exception as e:
            print "Failure creating new archive: {0}!".format(filename)
            print e, sys.exc_info()[0]
            zout.close()
            os.unlink(tmp_name)
        else:
            zout.close()

            # Success!  Now move the files
            shutil.move(filename, curr_subfolder)
            os.rename(tmp_name, filename)
            # TODO: We might have converted a rar to a zip, and should probably change
            #  the extension, as needed.

            print "Done!".format(filename)

            # Create a new archive object for the new file, and write the old
            # CIX data, with new page info
            ca = ComicArchive(filename, settings.rar_exe_path)
            md.pages = new_pages
            ca.writeMetadata(style, md)


if __name__ == '__main__':
    main()
