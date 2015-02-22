#!/usr/bin/python
"""Reduce the image size of pages in the comic archive"""

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

import shutil
#import sys
#import os
#import tempfile
#import zipfile

import Image

from comictaggerlib.settings import *
from comictaggerlib.comicarchive import *
#import comictaggerlib.utils


subfolder_name = "ORIGINALS"
max_height = 2000


def main():
    utils.fix_output_encoding()
    settings = ComicTaggerSettings()

    # this can only work with files with ComicRack tags
    style = MetaDataStyle.CIX

    if len(sys.argv) < 2:
        print >> sys.stderr, "Usage: {0} [comic_folder]".format(sys.argv[0])
        return

    filelist = utils.get_recursive_filelist(sys.argv[1:])

    # first make a list of all comic archive files
    comics_list = []
    max_name_len = 2
    fmt_str = u"{{0:{0}}}".format(max_name_len)
    for filename in filelist:

        ca = ComicArchive(filename, settings.rar_exe_path)
        if (ca.seemsToBeAComicArchive()):
            # Check the images in the file, see if we need to reduce any

            for idx in range(ca.getNumberOfPages()):
                in_data = ca.getPage(idx)
                if in_data is not None:
                    try:
                        im = Image.open(StringIO.StringIO(in_data))
                        w, h = im.size
                        if h > max_height:
                            comics_list.append(ca)

                            max_name_len = max(max_name_len, len(filename))
                            fmt_str = u"{{0:{0}}}".format(max_name_len)
                            print >> sys.stderr, fmt_str.format(
                                filename) + "\r",
                            sys.stderr.flush()
                            break

                    except IOError:
                        # doesn't appear to be an image
                        pass

    print >> sys.stderr, fmt_str.format("") + "\r",
    print "--------------------------------------------------------------------------"
    print "Found {0} comics with over-large pages".format(len(comics_list))
    print "--------------------------------------------------------------------------"

    for item in comics_list:
        print item.path

    # now actually process those files with over-large pages
    for ca in comics_list:
        filename = ca.path
        curr_folder = os.path.dirname(filename)
        curr_subfolder = os.path.join(curr_folder, subfolder_name)

        # skip any of our generated subfolders...
        if os.path.basename(curr_folder) == subfolder_name:
            continue

        sys.stdout.write("Processing: " + filename)

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

        cix_md = None
        if ca.hasCIX():
            cix_md = ca.readCIX()

        try:
            zout = zipfile.ZipFile(tmp_name, 'w')

            # Check the images in the file, see if we want to reduce them
            page_count = ca.getNumberOfPages()

            for idx in range(ca.getNumberOfPages()):
                name = ca.getPageName(idx)
                in_data = ca.getPage(idx)
                out_data = in_data
                if in_data is not None:
                    try:
                        im = Image.open(StringIO.StringIO(in_data))
                        w, h = im.size
                        if h > max_height:
                            # resize the image
                            hpercent = (max_height / float(h))
                            wsize = int((float(w) * float(hpercent)))
                            size = (wsize, max_height)
                            im = im.resize(size, Image.ANTIALIAS)

                            output = StringIO.StringIO()
                            im.save(output, format="JPEG", quality=85)
                            out_data = output.getvalue()
                            output.close()

                    except IOError:
                        # doesn't appear to be an image
                        pass

                else:
                    # page is empty?? nothing to write
                    out_data = ""

                sys.stdout.write('.')
                sys.stdout.flush()

                # write out the new resized image
                zout.writestr(name, out_data)

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
            # CIX data, w/o page info
            if cix_md is not None:
                ca = ComicArchive(filename, settings.rar_exe_path)
                cix_md.pages = []
                ca.writeCIX(cix_md)


if __name__ == '__main__':
    main()
