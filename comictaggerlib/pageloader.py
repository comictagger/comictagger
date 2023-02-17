"""A PyQT4 class to load a page image from a ComicArchive in a background thread"""
#
# Copyright 2012-2014 ComicTagger Authors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
from __future__ import annotations

import logging

from PyQt5 import QtCore

from comicapi.comicarchive import ComicArchive

logger = logging.getLogger(__name__)


class PageLoader(QtCore.QThread):
    """
    This class holds onto a reference of each instance in a list since
    problems occur if the ref count goes to zero and the GC tries to reap
    the object while the thread is going.
    If the client class wants to stop the thread, they should mark it as
    "abandoned", and no signals will be issued.
    """

    loadComplete = QtCore.pyqtSignal(bytes)

    instanceList: list[QtCore.QThread] = []
    mutex = QtCore.QMutex()

    # Remove all finished threads from the list
    @staticmethod
    def reap_instances() -> None:
        for obj in reversed(PageLoader.instanceList):
            if obj.isFinished():
                PageLoader.instanceList.remove(obj)

    def __init__(self, ca: ComicArchive, page_num: int) -> None:
        QtCore.QThread.__init__(self)
        self.ca: ComicArchive = ca
        self.page_num: int = page_num
        self.abandoned = False

        # remove any old instances, and then add ourself
        PageLoader.mutex.lock()
        PageLoader.reap_instances()
        PageLoader.instanceList.append(self)
        PageLoader.mutex.unlock()

    def run(self) -> None:
        image_data = self.ca.get_page(self.page_num)
        if self.abandoned:
            return

        if image_data:
            if self.abandoned:
                return
            self.loadComplete.emit(image_data)
