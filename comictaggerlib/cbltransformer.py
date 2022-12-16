"""A class to manage modifying metadata specifically for CBL/CBI"""
#
# Copyright 2012-2014 Anthony Beville
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

import settngs

from comicapi.genericmetadata import CreditMetadata, GenericMetadata

logger = logging.getLogger(__name__)


class CBLTransformer:
    def __init__(self, metadata: GenericMetadata, options: settngs.Namespace) -> None:
        self.metadata = metadata
        self.options = options

    def apply(self) -> GenericMetadata:
        # helper funcs
        def append_to_tags_if_unique(item: str) -> None:
            if item.casefold() not in (tag.casefold() for tag in self.metadata.tags):
                self.metadata.tags.add(item)

        def add_string_list_to_tags(str_list: str | None) -> None:
            if str_list:
                items = [s.strip() for s in str_list.split(",")]
                for item in items:
                    append_to_tags_if_unique(item)

        if self.options.cbl_assume_lone_credit_is_primary:

            # helper
            def set_lone_primary(role_list: list[str]) -> tuple[CreditMetadata | None, int]:
                lone_credit: CreditMetadata | None = None
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

        if self.options.cbl_copy_characters_to_tags:
            add_string_list_to_tags(self.metadata.characters)

        if self.options.cbl_copy_teams_to_tags:
            add_string_list_to_tags(self.metadata.teams)

        if self.options.cbl_copy_locations_to_tags:
            add_string_list_to_tags(self.metadata.locations)

        if self.options.cbl_copy_storyarcs_to_tags:
            add_string_list_to_tags(self.metadata.story_arc)

        if self.options.cbl_copy_notes_to_comments:
            if self.metadata.notes is not None:
                if self.metadata.comments is None:
                    self.metadata.comments = ""
                else:
                    self.metadata.comments += "\n\n"
                if self.metadata.notes not in self.metadata.comments:
                    self.metadata.comments += self.metadata.notes

        if self.options.cbl_copy_weblink_to_comments:
            if self.metadata.web_link is not None:
                if self.metadata.comments is None:
                    self.metadata.comments = ""
                else:
                    self.metadata.comments += "\n\n"
                if self.metadata.web_link not in self.metadata.comments:
                    self.metadata.comments += self.metadata.web_link

        return self.metadata
