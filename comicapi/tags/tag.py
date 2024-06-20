from __future__ import annotations

from comicapi.archivers import Archiver
from comicapi.genericmetadata import GenericMetadata


class Tag:
    enabled: bool = False
    id: str = ""

    def __init__(self, version: str) -> None:
        self.version: str = version
        self.supported_attributes = {
            "data_origin",
            "issue_id",
            "series_id",
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
            "price",
            "is_version_of",
            "rights",
            "identifier",
            "last_mark",
        }

    def supports_credit_role(self, role: str) -> bool:
        return False

    def supports_tags(self, archive: Archiver) -> bool:
        """
        Checks the given archive for the ability to save these tags.
        Should always return a bool. Failures should return False.
        Typically consists of a call to either `archive.supports_comment` or `archive.supports_file`
        """
        return False

    def has_tags(self, archive: Archiver) -> bool:
        """
        Checks the given archive for tags.
        Should always return a bool. Failures should return False.
        """
        return False

    def remove_tags(self, archive: Archiver) -> bool:
        """
        Removes the tags from the given archive.
        Should always return a bool. Failures should return False.
        """
        return False

    def read_tags(self, archive: Archiver) -> GenericMetadata:
        """
        Returns a GenericMetadata representing the tags saved in the given archive.
        Should always return a GenericMetadata. Failures should return an empty metadata object.
        """
        return GenericMetadata()

    def read_raw_tags(self, archive: Archiver) -> str:
        """
        Returns the raw tags as a string.
        If the tags are a binary format a roughly similar text format should be used.
        Should always return a string. Failures should return the empty string.
        """
        return ""

    def write_tags(self, metadata: GenericMetadata, archive: Archiver) -> bool:
        """
        Saves the given metadata to the given archive.
        Should always return a bool. Failures should return False.
        """
        return False

    def name(self) -> str:
        """
        Returns the name of these tags for display purposes eg "Comic Rack".
        Should always return a string. Failures should return the empty string.
        """
        return ""
