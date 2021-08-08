"""A class to encapsulate the ComicBookInfo data"""

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

import json
from datetime import datetime
#import zipfile

from .genericmetadata import GenericMetadata
from . import utils
#import ctversion


class ComicBookInfo:
    def metadataFromString(self, string):
        class Default(dict):
            def __missing__(self, key):
                return None
        cbi_container = json.loads(str(string, 'utf-8'))

        metadata = GenericMetadata()

        cbi = Default(cbi_container['ComicBookInfo/1.0'])

        metadata.series = utils.xlate(cbi['series'])
        metadata.title = utils.xlate(cbi['title'])
        metadata.issue = utils.xlate(cbi['issue'])
        metadata.publisher = utils.xlate(cbi['publisher'])
        metadata.month = utils.xlate(cbi['publicationMonth'], True)
        metadata.year = utils.xlate(cbi['publicationYear'], True)
        metadata.issueCount = utils.xlate(cbi['numberOfIssues'], True)
        metadata.comments = utils.xlate(cbi['comments'])
        metadata.genre = utils.xlate(cbi['genre'])
        metadata.volume = utils.xlate(cbi['volume'], True)
        metadata.volumeCount = utils.xlate(cbi['numberOfVolumes'], True)
        metadata.language = utils.xlate(cbi['language'])
        metadata.country = utils.xlate(cbi['country'])
        metadata.criticalRating = utils.xlate(cbi['rating'])

        metadata.credits = cbi['credits']
        metadata.tags = cbi['tags']

        # make sure credits and tags are at least empty lists and not None
        if metadata.credits is None:
            metadata.credits = []
        if metadata.tags is None:
            metadata.tags = []

        # need to massage the language string to be ISO
        if metadata.language is not None:
            # reverse look-up
            pattern = metadata.language
            metadata.language = None
            for key in utils.getLanguageDict():
                if utils.getLanguageDict()[key] == pattern.encode('utf-8'):
                    metadata.language = key
                    break

        metadata.isEmpty = False

        return metadata

    def stringFromMetadata(self, metadata):

        cbi_container = self.createJSONDictionary(metadata)
        return json.dumps(cbi_container)

    def validateString(self, string):
        """Verify that the string actually contains CBI data in JSON format"""

        try:
            cbi_container = json.loads(string)
        except:
            return False

        return ('ComicBookInfo/1.0' in cbi_container)

    def createJSONDictionary(self, metadata):
        """Create the dictionary that we will convert to JSON text"""

        cbi = dict()
        cbi_container = {'appID': 'ComicTagger/' + '1.0.0',  # ctversion.version,
                         'lastModified': str(datetime.now()),
                         'ComicBookInfo/1.0': cbi}

        # helper func
        def assign(cbi_entry, md_entry):
            if md_entry is not None or isinstance(md_entry, str) and md_entry != "":
                cbi[cbi_entry] = md_entry

        assign('series', utils.xlate(metadata.series))
        assign('title', utils.xlate(metadata.title))
        assign('issue', utils.xlate(metadata.issue))
        assign('publisher', utils.xlate(metadata.publisher))
        assign('publicationMonth', utils.xlate(metadata.month, True))
        assign('publicationYear', utils.xlate(metadata.year, True))
        assign('numberOfIssues', utils.xlate(metadata.issueCount, True))
        assign('comments', utils.xlate(metadata.comments))
        assign('genre', utils.xlate(metadata.genre))
        assign('volume', utils.xlate(metadata.volume, True))
        assign('numberOfVolumes', utils.xlate(metadata.volumeCount, True))
        assign('language', utils.xlate(utils.getLanguageFromISO(metadata.language)))
        assign('country', utils.xlate(metadata.country))
        assign('rating', utils.xlate(metadata.criticalRating))
        assign('credits', metadata.credits)
        assign('tags', metadata.tags)

        return cbi_container

    def writeToExternalFile(self, filename, metadata):

        cbi_container = self.createJSONDictionary(metadata)

        f = open(filename, 'w')
        f.write(json.dumps(cbi_container, indent=4))
        f.close
