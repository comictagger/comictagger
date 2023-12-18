from __future__ import annotations

import settngs

import comicapi.genericmetadata
import comictaggerlib.ctsettings.types
import comictaggerlib.defaults
import comictaggerlib.resulttypes


class settngs_namespace(settngs.TypedNS):
    Commands__version: bool
    Commands__command: comictaggerlib.resulttypes.Action
    Commands__copy: str

    Runtime_Options__config: comictaggerlib.ctsettings.types.ComicTaggerPaths
    Runtime_Options__verbose: int
    Runtime_Options__abort_on_conflict: bool
    Runtime_Options__delete_after_zip_export: bool
    Runtime_Options__parse_filename: bool
    Runtime_Options__issue_id: str
    Runtime_Options__online: bool
    Runtime_Options__metadata: comicapi.genericmetadata.GenericMetadata
    Runtime_Options__interactive: bool
    Runtime_Options__abort_on_low_confidence: bool
    Runtime_Options__summary: bool
    Runtime_Options__raw: bool
    Runtime_Options__recursive: bool
    Runtime_Options__split_words: bool
    Runtime_Options__dryrun: bool
    Runtime_Options__darkmode: bool
    Runtime_Options__glob: bool
    Runtime_Options__quiet: bool
    Runtime_Options__json: bool
    Runtime_Options__type: list[str]
    Runtime_Options__overwrite: bool
    Runtime_Options__no_gui: bool
    Runtime_Options__files: list[str]

    internal__install_id: str
    internal__save_data_style: str
    internal__load_data_style: str
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
    Issue_Identifier__border_crop_percent: int
    Issue_Identifier__publisher_filter: list[str]
    Issue_Identifier__series_match_search_thresh: int
    Issue_Identifier__clear_metadata_on_import: bool
    Issue_Identifier__auto_imprint: bool
    Issue_Identifier__sort_series_by_year: bool
    Issue_Identifier__exact_series_matches_first: bool
    Issue_Identifier__always_use_publisher_filter: bool

    Filename_Parsing__complicated_parser: bool
    Filename_Parsing__remove_c2c: bool
    Filename_Parsing__remove_fcbd: bool
    Filename_Parsing__remove_publisher: bool
    Filename_Parsing__protofolius_issue_number_scheme: bool
    Filename_Parsing__allow_issue_start_with_letter: bool

    Sources__source: str
    Sources__remove_html_tables: bool

    Comic_Book_Lover__assume_lone_credit_is_primary: bool
    Comic_Book_Lover__copy_characters_to_tags: bool
    Comic_Book_Lover__copy_teams_to_tags: bool
    Comic_Book_Lover__copy_locations_to_tags: bool
    Comic_Book_Lover__copy_storyarcs_to_tags: bool
    Comic_Book_Lover__copy_notes_to_comments: bool
    Comic_Book_Lover__copy_weblink_to_comments: bool
    Comic_Book_Lover__apply_transform_on_import: bool
    Comic_Book_Lover__apply_transform_on_bulk_operation: bool

    File_Rename__template: str
    File_Rename__issue_number_padding: int
    File_Rename__use_smart_string_cleanup: bool
    File_Rename__set_extension_based_on_archive: bool
    File_Rename__dir: str
    File_Rename__move_to_dir: bool
    File_Rename__strict: bool
    File_Rename__replacements: comictaggerlib.defaults.Replacements

    Auto_Tag__save_on_low_confidence: bool
    Auto_Tag__dont_use_year_when_identifying: bool
    Auto_Tag__assume_issue_one: bool
    Auto_Tag__ignore_leading_numbers_in_filename: bool
    Auto_Tag__remove_archive_after_successful_match: bool

    General__check_for_new_version: bool

    Dialog_Flags__show_disclaimer: bool
    Dialog_Flags__dont_notify_about_this_version: str
    Dialog_Flags__ask_about_usage_stats: bool

    Source_comicvine__comicvine_key: str
    Source_comicvine__comicvine_url: str
    Source_comicvine__cv_use_series_start_as_volume: bool
