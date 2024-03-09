from __future__ import annotations

from comicapi.archivers import Archiver
from comicapi.genericmetadata import GenericMetadata


class Metadata:
    enabled: bool = False
    short_name: str = ""

    def __init__(self, version: str) -> None:
        self.version: str = version
        self.supported_attributes = {
            "tag_origin",
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
            "story_arcs_numbers",
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

    def supports_metadata(self, archive: Archiver) -> bool:
        """
        Checks the given archive for the ability to save this metadata style.
        Should always return a bool. Failures should return False.
        Typically consists of a call to either `archive.supports_comment` or `archive.supports_file`
        """
        return False

    def has_metadata(self, archive: Archiver) -> bool:
        """
        Checks the given archive for metadata.
        Should always return a bool. Failures should return False.
        """
        return False

    def remove_metadata(self, archive: Archiver) -> bool:
        """
        Removes the metadata from the given archive.
        Should always return a bool. Failures should return False.
        """
        return False

    def get_metadata(self, archive: Archiver) -> GenericMetadata:
        """
        Returns a GenericMetadata representing the data saved in the given archive.
        Should always return a GenericMetadata. Failures should return an empty metadata object.
        """
        return GenericMetadata()

    def get_metadata_string(self, archive: Archiver) -> str:
        """
        Returns the raw metadata as a string.
        If the metadata is a binary format a roughly similar text format should be used.
        Should always return a string. Failures should return the empty string.
        """
        return ""

    def set_metadata(self, metadata: GenericMetadata, archive: Archiver) -> bool:
        """
        Saves the given metadata to the given archive.
        Should always return a bool. Failures should return False.
        """
        return False

    def name(self) -> str:
        """
        Returns the name of this metadata for display purposes eg "Comic Rack".
        Should always return a string. Failures should return the empty string.
        """
        return ""
