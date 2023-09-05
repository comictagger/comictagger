from __future__ import annotations

import settngs

import comicapi.genericmetadata
import comictaggerlib.ctsettings.types
import comictaggerlib.defaults


class settngs_namespace(settngs.TypedNS):
    Commands_version: bool
    Commands_print: bool
    Commands_delete: bool
    Commands_copy: int
    Commands_save: bool
    Commands_rename: bool
    Commands_export_to_zip: bool
    Commands_only_set_cv_key: bool
    Commands_list_plugins: bool

    Runtime_Options_config: comictaggerlib.ctsettings.types.ComicTaggerPaths
    Runtime_Options_verbose: int
    Runtime_Options_abort_on_conflict: bool
    Runtime_Options_delete_after_zip_export: bool
    Runtime_Options_parse_filename: bool
    Runtime_Options_issue_id: str
    Runtime_Options_online: bool
    Runtime_Options_metadata: comicapi.genericmetadata.GenericMetadata
    Runtime_Options_interactive: bool
    Runtime_Options_abort_on_low_confidence: bool
    Runtime_Options_summary: bool
    Runtime_Options_raw: bool
    Runtime_Options_recursive: bool
    Runtime_Options_script: str
    Runtime_Options_split_words: bool
    Runtime_Options_dryrun: bool
    Runtime_Options_darkmode: bool
    Runtime_Options_glob: bool
    Runtime_Options_quiet: bool
    Runtime_Options_type: list[int]
    Runtime_Options_overwrite: bool
    Runtime_Options_no_gui: bool
    Runtime_Options_files: list[str]

    internal_install_id: str
    internal_save_data_style: int
    internal_load_data_style: int
    internal_last_opened_folder: str
    internal_window_width: int
    internal_window_height: int
    internal_window_x: int
    internal_window_y: int
    internal_form_width: int
    internal_list_width: int
    internal_sort_column: int
    internal_sort_direction: int

    Issue_Identifier_series_match_identify_thresh: int
    Issue_Identifier_border_crop_percent: int
    Issue_Identifier_publisher_filter: list[str]
    Issue_Identifier_series_match_search_thresh: int
    Issue_Identifier_clear_metadata_on_import: bool
    Issue_Identifier_auto_imprint: bool
    Issue_Identifier_sort_series_by_year: bool
    Issue_Identifier_exact_series_matches_first: bool
    Issue_Identifier_always_use_publisher_filter: bool
    Issue_Identifier_clear_form_before_populating: bool

    Filename_Parsing_complicated_parser: bool
    Filename_Parsing_remove_c2c: bool
    Filename_Parsing_remove_fcbd: bool
    Filename_Parsing_remove_publisher: bool

    Sources_source: str
    Sources_remove_html_tables: bool

    Comic_Book_Lover_assume_lone_credit_is_primary: bool
    Comic_Book_Lover_copy_characters_to_tags: bool
    Comic_Book_Lover_copy_teams_to_tags: bool
    Comic_Book_Lover_copy_locations_to_tags: bool
    Comic_Book_Lover_copy_storyarcs_to_tags: bool
    Comic_Book_Lover_copy_notes_to_comments: bool
    Comic_Book_Lover_copy_weblink_to_comments: bool
    Comic_Book_Lover_apply_transform_on_import: bool
    Comic_Book_Lover_apply_transform_on_bulk_operation: bool

    File_Rename_template: str
    File_Rename_issue_number_padding: int
    File_Rename_use_smart_string_cleanup: bool
    File_Rename_set_extension_based_on_archive: bool
    File_Rename_dir: str
    File_Rename_move_to_dir: bool
    File_Rename_strict: bool
    File_Rename_replacements: comictaggerlib.defaults.Replacements

    Auto_Tag_save_on_low_confidence: bool
    Auto_Tag_dont_use_year_when_identifying: bool
    Auto_Tag_assume_1_if_no_issue_num: bool
    Auto_Tag_ignore_leading_numbers_in_filename: bool
    Auto_Tag_remove_archive_after_successful_match: bool

    General_check_for_new_version: bool

    Dialog_Flags_show_disclaimer: bool
    Dialog_Flags_dont_notify_about_this_version: str
    Dialog_Flags_ask_about_usage_stats: bool

    Source_comicvine_comicvine_key: str
    Source_comicvine_comicvine_url: str
    Source_comicvine_cv_use_series_start_as_volume: bool
