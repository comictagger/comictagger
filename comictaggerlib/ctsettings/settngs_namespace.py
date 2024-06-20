from __future__ import annotations

import typing

import settngs

import comicapi.genericmetadata
import comicapi.merge
import comicapi.utils
import comictaggerlib.ctsettings.types
import comictaggerlib.defaults
import comictaggerlib.resulttypes


class SettngsNS(settngs.TypedNS):
    Commands__version: bool
    Commands__command: comictaggerlib.resulttypes.Action
    Commands__copy: list[str]

    Runtime_Options__config: comictaggerlib.ctsettings.types.ComicTaggerPaths
    Runtime_Options__verbose: int
    Runtime_Options__quiet: bool
    Runtime_Options__json: bool
    Runtime_Options__raw: bool
    Runtime_Options__interactive: bool
    Runtime_Options__abort_on_low_confidence: bool
    Runtime_Options__dryrun: bool
    Runtime_Options__summary: bool
    Runtime_Options__recursive: bool
    Runtime_Options__glob: bool
    Runtime_Options__darkmode: bool
    Runtime_Options__no_gui: bool
    Runtime_Options__abort_on_conflict: bool
    Runtime_Options__delete_original: bool
    Runtime_Options__tags_read: list[str]
    Runtime_Options__tags_write: list[str]
    Runtime_Options__skip_existing_tags: bool
    Runtime_Options__files: list[str]

    internal__install_id: str
    internal__write_tags: list[str]
    internal__read_tags: list[str]
    internal__last_opened_folder: str
    internal__window_width: int
    internal__window_height: int
    internal__window_x: int
    internal__window_y: int
    internal__form_width: int
    internal__list_width: int
    internal__sort_column: int
    internal__sort_direction: int

    Issue_Identifier__series_match_identify_thresh: int
    Issue_Identifier__series_match_search_thresh: int
    Issue_Identifier__border_crop_percent: int
    Issue_Identifier__sort_series_by_year: bool
    Issue_Identifier__exact_series_matches_first: bool

    Filename_Parsing__filename_parser: comicapi.utils.Parser
    Filename_Parsing__remove_c2c: bool
    Filename_Parsing__remove_fcbd: bool
    Filename_Parsing__remove_publisher: bool
    Filename_Parsing__split_words: bool
    Filename_Parsing__protofolius_issue_number_scheme: bool
    Filename_Parsing__allow_issue_start_with_letter: bool

    Sources__source: str
    Sources__remove_html_tables: bool

    Metadata_Options__assume_lone_credit_is_primary: bool
    Metadata_Options__copy_characters_to_tags: bool
    Metadata_Options__copy_teams_to_tags: bool
    Metadata_Options__copy_locations_to_tags: bool
    Metadata_Options__copy_storyarcs_to_tags: bool
    Metadata_Options__copy_notes_to_comments: bool
    Metadata_Options__copy_weblink_to_comments: bool
    Metadata_Options__apply_transform_on_import: bool
    Metadata_Options__apply_transform_on_bulk_operation: bool
    Metadata_Options__use_short_tag_names: bool
    Metadata_Options__cr: bool
    Metadata_Options__tag_merge: comicapi.merge.Mode
    Metadata_Options__metadata_merge: comicapi.merge.Mode
    Metadata_Options__tag_merge_lists: bool
    Metadata_Options__metadata_merge_lists: bool

    File_Rename__template: str
    File_Rename__issue_number_padding: int
    File_Rename__use_smart_string_cleanup: bool
    File_Rename__auto_extension: bool
    File_Rename__dir: str
    File_Rename__move: bool
    File_Rename__only_move: bool
    File_Rename__strict_filenames: bool
    File_Rename__replacements: comictaggerlib.defaults.Replacements

    Auto_Tag__online: bool
    Auto_Tag__save_on_low_confidence: bool
    Auto_Tag__use_year_when_identifying: bool
    Auto_Tag__assume_issue_one: bool
    Auto_Tag__ignore_leading_numbers_in_filename: bool
    Auto_Tag__remove_archive_after_successful_match: bool
    Auto_Tag__parse_filename: bool
    Auto_Tag__issue_id: str | None
    Auto_Tag__metadata: comicapi.genericmetadata.GenericMetadata
    Auto_Tag__clear_tags: bool
    Auto_Tag__publisher_filter: list[str]
    Auto_Tag__use_publisher_filter: bool
    Auto_Tag__auto_imprint: bool

    General__check_for_new_version: bool
    General__prompt_on_save: bool

    Dialog_Flags__show_disclaimer: bool
    Dialog_Flags__dont_notify_about_this_version: str
    Dialog_Flags__ask_about_usage_stats: bool

    Archive__rar: str

    Source_comicvine__comicvine_key: str | None
    Source_comicvine__comicvine_url: str | None
    Source_comicvine__cv_use_series_start_as_volume: bool


class Commands(typing.TypedDict):
    version: bool
    command: comictaggerlib.resulttypes.Action
    copy: list[str]


class Runtime_Options(typing.TypedDict):
    config: comictaggerlib.ctsettings.types.ComicTaggerPaths
    verbose: int
    quiet: bool
    json: bool
    raw: bool
    interactive: bool
    abort_on_low_confidence: bool
    dryrun: bool
    summary: bool
    recursive: bool
    glob: bool
    darkmode: bool
    no_gui: bool
    abort_on_conflict: bool
    delete_original: bool
    tags_read: list[str]
    tags_write: list[str]
    skip_existing_tags: bool
    files: list[str]


class internal(typing.TypedDict):
    install_id: str
    write_tags: list[str]
    read_tags: list[str]
    last_opened_folder: str
    window_width: int
    window_height: int
    window_x: int
    window_y: int
    form_width: int
    list_width: int
    sort_column: int
    sort_direction: int


class Issue_Identifier(typing.TypedDict):
    series_match_identify_thresh: int
    series_match_search_thresh: int
    border_crop_percent: int
    sort_series_by_year: bool
    exact_series_matches_first: bool


class Filename_Parsing(typing.TypedDict):
    filename_parser: comicapi.utils.Parser
    remove_c2c: bool
    remove_fcbd: bool
    remove_publisher: bool
    split_words: bool
    protofolius_issue_number_scheme: bool
    allow_issue_start_with_letter: bool


class Sources(typing.TypedDict):
    source: str
    remove_html_tables: bool


class Metadata_Options(typing.TypedDict):
    assume_lone_credit_is_primary: bool
    copy_characters_to_tags: bool
    copy_teams_to_tags: bool
    copy_locations_to_tags: bool
    copy_storyarcs_to_tags: bool
    copy_notes_to_comments: bool
    copy_weblink_to_comments: bool
    apply_transform_on_import: bool
    apply_transform_on_bulk_operation: bool
    use_short_tag_names: bool
    cr: bool
    tag_merge: comicapi.merge.Mode
    metadata_merge: comicapi.merge.Mode
    tag_merge_lists: bool
    metadata_merge_lists: bool


class File_Rename(typing.TypedDict):
    template: str
    issue_number_padding: int
    use_smart_string_cleanup: bool
    auto_extension: bool
    dir: str
    move: bool
    only_move: bool
    strict_filenames: bool
    replacements: comictaggerlib.defaults.Replacements


class Auto_Tag(typing.TypedDict):
    online: bool
    save_on_low_confidence: bool
    use_year_when_identifying: bool
    assume_issue_one: bool
    ignore_leading_numbers_in_filename: bool
    remove_archive_after_successful_match: bool
    parse_filename: bool
    issue_id: str | None
    metadata: comicapi.genericmetadata.GenericMetadata
    clear_tags: bool
    publisher_filter: list[str]
    use_publisher_filter: bool
    auto_imprint: bool


class General(typing.TypedDict):
    check_for_new_version: bool
    prompt_on_save: bool


class Dialog_Flags(typing.TypedDict):
    show_disclaimer: bool
    dont_notify_about_this_version: str
    ask_about_usage_stats: bool


class Archive(typing.TypedDict):
    rar: str


class Source_comicvine(typing.TypedDict):
    comicvine_key: str | None
    comicvine_url: str | None
    cv_use_series_start_as_volume: bool


SettngsDict = typing.TypedDict(
    "SettngsDict",
    {
        "Commands": Commands,
        "Runtime Options": Runtime_Options,
        "internal": internal,
        "Issue Identifier": Issue_Identifier,
        "Filename Parsing": Filename_Parsing,
        "Sources": Sources,
        "Metadata Options": Metadata_Options,
        "File Rename": File_Rename,
        "Auto-Tag": Auto_Tag,
        "General": General,
        "Dialog Flags": Dialog_Flags,
        "Archive": Archive,
        "Source comicvine": Source_comicvine,
    },
)
