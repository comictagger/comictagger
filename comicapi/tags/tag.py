from __future__ import annotations

from typing import ClassVar

from comicapi.archivers import Archiver
from comicapi.genericmetadata import GenericMetadata


class Tag:
    id: ClassVar[str] = ""
    """
    ID form this tag format.
    Currently known used IDs are cr, cix, comet, cbi, metroninfo and acbf.
    You can use an existing ID to override it's behaiour. It is not recommended to do so.
    """

    enabled: bool = False
    """When set to False it will be excluded from selection in ComicTagger"""

    supported_attributes: set[str] = {
        "data_origin",
        "issue_id",
        "series_id",
        "original_hash",
        "series",
        "series_aliases",
        "issue",
        "issue_count",
        "title",
        "title_aliases",
        "volume",
        "volume_count",
        "genres",
        "description",
        "notes",
        "alternate_series",
        "alternate_number",
        "alternate_count",
        "gtin",
        "story_arcs",
        "series_groups",
        "publisher",
        "imprint",
        "day",
        "month",
        "year",
        "language",
        "country",
        "web_link",
        "format",
        "manga",
        "black_and_white",
        "maturity_rating",
        "critical_rating",
        "scan_info",
        "tags",
        "pages",
        "pages.type",
        "pages.bookmark",
        "pages.double_page",
        "pages.image_index",
        "pages.size",
        "pages.height",
        "pages.width",
        "page_count",
        "characters",
        "teams",
        "locations",
        "credits",
        "credits.person",
        "credits.role",
        "credits.primary",
        "credits.language",
        "price",
        "is_version_of",
        "rights",
        "identifier",
        "last_mark",
    }
    """Set of GenericMetadata attributes this tag format can handle"""
    version: str
    """Current version of ComicTagger"""

    def __init__(self, version: str) -> None:
        self.version: str = version

    def supports_credit_role(self, role: str) -> bool:
        """
        Return True if this tag format can handle this credit role.
        Should always return a bool.
        MUST NOT cause an exception.
        """
        self.supported_attributes
        return False

    def supports_tags(self, archive: Archiver) -> bool:
        """
        Checks the given archive for the ability to save these tags.
        Should always return a bool.
        Typically consists of a call to either `archive.supports_comment` or `archive.supports_file`
        """
        raise NotImplementedError

    def has_tags(self, archive: Archiver) -> bool:
        """
        Checks the given archive for tags.
        Should always return a bool.
        """
        raise NotImplementedError

    def remove_tags(self, archive: Archiver) -> None:
        """
        Removes the tags from the given archive.
        Should always return a bool. Failures should return False.
        """
        raise NotImplementedError

    def read_tags(self, archive: Archiver) -> GenericMetadata:
        """
        Returns a GenericMetadata representing the tags saved in the given archive.
        """
        raise NotImplementedError

    def read_raw_tags(self, archive: Archiver) -> str:
        """
        Returns the raw tags as a string.
        If the tags are a binary format a roughly similar text format should be used.
        """
        raise NotImplementedError

    def write_tags(self, metadata: GenericMetadata, archive: Archiver) -> None:
        """
        Saves the given metadata to the given archive.
        Should always return a bool
        """
        raise NotImplementedError

    def name(self) -> str:
        """
        Returns the name of these tags for display purposes eg "Comic Rack".
        Should always return a string.
        MUST NOT cause an exception.
        """
        return ""
