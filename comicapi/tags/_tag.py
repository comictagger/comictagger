from __future__ import annotations

from typing import Protocol, runtime_checkable

from ..genericmetadata import GenericMetadata
from ..utils import StrEnum


class TagLocation(StrEnum):
    """
    TagLocation is where the tags are stored in a file.

    FILE: Tags are stored in a distinct file in a comic. Must set filename_match and filename so that tags can be located.
    COMMENT: Tags are stored in the comment section of an comic.

    CUSTOM: Tags are stored in a file specific format. eg single file acbf format https://acbf.fandom.com/wiki/ACBF_Specifications#Embedding_ACBF_files_and_compatibility_with_popular_comic_book_formats or PDF Metadata https://en.wikipedia.org/wiki/PDF#Metadata
    """

    FILE = "file"
    COMMENT = "comment"
    EXTERNAL = "external"
    CUSTOM = "custom"


@runtime_checkable
class Tag(Protocol):
    """
    Tag class used for loading and saving metadata.

    It is not required that a tag inherit this class but it must implement the data and methods listed here.
    See https://github.com/comictagger/comicinfoxml
    """

    id: str
    name: str
    enabled: bool
    """
    When false ComicApi will refuse to load the tag.
    If external imports are required and are not available this should be false. See rar.py and sevenzip.py.
    """

    location: TagLocation
    filename_match: str = ""
    """
    filename to obtain tags from.
    Either an exact name to match:
    `ComicInfo.xml`
    or an extension:
    `*.xml`

    the first matching file will be used

    Only needed if storage_location is TagLocation.FILE or TagLocation.EXTERNAL
    TagLocation.EXTERNAL tags must have the same name as the archive.
    E.G. `Anda's Game.cbz` with an filename_match of `ComicInfo.xml` will only match `Anda's Game.ComicInfo.xml`
    If filename match is `xml` it will only match will only match `Anda's Game.xml`
    If filename match is `*.xml` it will match any filename that starts with `Anda's Game` and ends with `.xml`
    Renaming will break TagLocation.EXTERNAL files.
    """
    filename: str = ""
    """
    The filename to save tags to.

    Only needed if storage_location is TagLocation.FILE or TagLocation.EXTERNAL
    TagLocation.EXTERNAL tags will have the same name as the archive.
    E.G. `Anda's Game.cbz` with an filename of `ComicInfo.xml` will become `Anda's Game.ComicInfo.xml`
    """

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
    """For enabling/disabling in GUI. Has no effect on data processed"""

    @staticmethod
    def supports_credit_role(role: str) -> bool:
        raise NotImplementedError

    @staticmethod
    def validate_tags(tags: bytes) -> bool:
        raise NotImplementedError

    @staticmethod
    def load_tags(tags: bytes) -> GenericMetadata:
        raise NotImplementedError

    @staticmethod
    def display_tags(tags: bytes) -> str:
        raise NotImplementedError

    @staticmethod
    def create_tags(version: str, metadata: GenericMetadata, existing_tags: bytes) -> bytes:
        raise NotImplementedError


__all__ = []
