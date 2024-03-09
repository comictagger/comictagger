"""A class to manage modifying metadata specifically for CBL/CBI"""

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

from comicapi.genericmetadata import Credit, GenericMetadata
from comictaggerlib.ctsettings import ct_ns

logger = logging.getLogger(__name__)


class CBLTransformer:
    def __init__(self, metadata: GenericMetadata, config: ct_ns) -> None:
        self.metadata = metadata
        self.config = config

    def apply(self) -> GenericMetadata:
        if self.config.Comic_Book_Lover__assume_lone_credit_is_primary:
            # helper
            def set_lone_primary(role_list: list[str]) -> tuple[Credit | None, int]:
                lone_credit: Credit | None = None
                count = 0
                for c in self.metadata.credits:
                    if c["role"].casefold() in role_list:
                        count += 1
                        lone_credit = c
                    if count > 1:
                        lone_credit = None
                        break
                if lone_credit is not None:
                    lone_credit["primary"] = True
                return lone_credit, count

            # need to loop three times, once for 'writer', 'artist', and then
            # 'penciler' if no artist
            set_lone_primary(["writer"])
            c, count = set_lone_primary(["artist"])
            if c is None and count == 0:
                c, count = set_lone_primary(["penciler", "penciller"])
                if c is not None:
                    c["primary"] = False
                    self.metadata.add_credit(c["person"], "Artist", True)

        if self.config.Comic_Book_Lover__copy_characters_to_tags:
            self.metadata.tags.update(x for x in self.metadata.characters)

        if self.config.Comic_Book_Lover__copy_teams_to_tags:
            self.metadata.tags.update(x for x in self.metadata.teams)

        if self.config.Comic_Book_Lover__copy_locations_to_tags:
            self.metadata.tags.update(x for x in self.metadata.locations)

        if self.config.Comic_Book_Lover__copy_storyarcs_to_tags:
            self.metadata.tags.update(x for x in self.metadata.story_arcs)

        if self.config.Comic_Book_Lover__copy_notes_to_comments:
            if self.metadata.notes is not None:
                if self.metadata.description is None:
                    self.metadata.description = ""
                else:
                    self.metadata.description += "\n\n"
                if self.metadata.notes not in self.metadata.description:
                    self.metadata.description += self.metadata.notes

        if self.config.Comic_Book_Lover__copy_weblink_to_comments:
            for web_link in self.metadata.web_links:
                temp_desc = self.metadata.description
                if temp_desc is None:
                    temp_desc = ""
                else:
                    temp_desc += "\n\n"
                if web_link.url and web_link.url not in temp_desc:
                    self.metadata.description = temp_desc + web_link.url

        return self.metadata
