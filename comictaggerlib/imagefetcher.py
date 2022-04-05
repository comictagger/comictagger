"""A class to manage fetching and caching of images by URL"""

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

import datetime
import os
import shutil
import sqlite3 as lite
import tempfile

import requests

try:
    from PyQt5 import QtCore, QtNetwork

    qt_available = True
except ImportError:
    qt_available = False


import logging

from comictaggerlib import ctversion
from comictaggerlib.settings import ComicTaggerSettings

logger = logging.getLogger(__name__)


class ImageFetcherException(Exception):
    pass


def fetch_complete(this, image_data):
    ...


class ImageFetcher:

    image_fetch_complete = fetch_complete

    def __init__(self):

        self.settings_folder = ComicTaggerSettings.get_settings_folder()
        self.db_file = os.path.join(self.settings_folder, "image_url_cache.db")
        self.cache_folder = os.path.join(self.settings_folder, "image_cache")

        self.user_data = None
        self.fetched_url = ""

        if not os.path.exists(self.db_file):
            self.create_image_db()

        if qt_available:
            self.nam = QtNetwork.QNetworkAccessManager()

    def clear_cache(self):
        os.unlink(self.db_file)
        if os.path.isdir(self.cache_folder):
            shutil.rmtree(self.cache_folder)

    def fetch(self, url, blocking=False):
        """
        If called with blocking=True, this will block until the image is
        fetched.
        If called with blocking=False, this will run the fetch in the
        background, and emit a signal when done
        """

        self.fetched_url = url

        # first look in the DB
        image_data = self.get_image_from_cache(url)
        if blocking or not qt_available:
            if image_data is None:
                try:
                    image_data = requests.get(url, headers={"user-agent": "comictagger/" + ctversion.version}).content
                except Exception as e:
                    logger.exception("Fetching url failed: %s")
                    raise ImageFetcherException("Network Error!") from e

            # save the image to the cache
            self.add_image_to_cache(self.fetched_url, image_data)
            return image_data

        if qt_available:
            # if we found it, just emit the signal asap
            if image_data is not None:
                self.image_fetch_complete(QtCore.QByteArray(image_data))
                return bytes()

            # didn't find it.  look online
            self.nam.finished.connect(self.finish_request)
            self.nam.get(QtNetwork.QNetworkRequest(QtCore.QUrl(url)))

            # we'll get called back when done...
        return bytes()

    def finish_request(self, reply):
        # read in the image data
        logger.debug("request finished")
        image_data = reply.readAll()

        # save the image to the cache
        self.add_image_to_cache(self.fetched_url, image_data)

        self.image_fetch_complete(image_data)

    def create_image_db(self):

        # this will wipe out any existing version
        open(self.db_file, "w").close()

        # wipe any existing image cache folder too
        if os.path.isdir(self.cache_folder):
            shutil.rmtree(self.cache_folder)
        os.makedirs(self.cache_folder)

        con = lite.connect(self.db_file)

        # create tables
        with con:
            cur = con.cursor()

            cur.execute("CREATE TABLE Images(url TEXT,filename TEXT,timestamp TEXT,PRIMARY KEY (url))")

    def add_image_to_cache(self, url, image_data):

        con = lite.connect(self.db_file)

        with con:
            cur = con.cursor()

            timestamp = datetime.datetime.now()

            tmp_fd, filename = tempfile.mkstemp(dir=self.cache_folder, prefix="img")
            f = os.fdopen(tmp_fd, "w+b")
            f.write(image_data)
            f.close()

            cur.execute("INSERT or REPLACE INTO Images VALUES(?, ?, ?)", (url, filename, timestamp))

    def get_image_from_cache(self, url):

        con = lite.connect(self.db_file)
        with con:
            cur = con.cursor()

            cur.execute("SELECT filename FROM Images WHERE url=?", [url])
            row = cur.fetchone()

            if row is None:
                return None

            filename = row[0]
            image_data = None

            try:
                with open(filename, "rb") as f:
                    image_data = f.read()
                    f.close()
            except IOError:
                pass

            return image_data
