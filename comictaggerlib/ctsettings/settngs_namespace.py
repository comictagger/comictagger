from __future__ import annotations

import settngs

import comicapi.genericmetadata
import comictaggerlib.ctsettings.types
import comictaggerlib.defaults


class settngs_namespace(settngs.TypedNS):
    commands_version: bool
    commands_print: bool
    commands_delete: bool
    commands_copy: int
    commands_save: bool
    commands_rename: bool
    commands_export_to_zip: bool
    commands_only_set_cv_key: bool

    runtime_config: comictaggerlib.ctsettings.types.ComicTaggerPaths
    runtime_verbose: int
    runtime_abort_on_conflict: bool
    runtime_delete_after_zip_export: bool
    runtime_parse_filename: bool
    runtime_issue_id: str
    runtime_online: bool
    runtime_metadata: comicapi.genericmetadata.GenericMetadata
    runtime_interactive: bool
    runtime_abort_on_low_confidence: bool
    runtime_summary: bool
    runtime_raw: bool
    runtime_recursive: bool
    runtime_script: str
    runtime_split_words: bool
    runtime_dryrun: bool
    runtime_darkmode: bool
    runtime_glob: bool
    runtime_quiet: bool
    runtime_type: list[int]
    runtime_overwrite: bool
    runtime_no_gui: bool
    runtime_files: list[str]

    general_check_for_new_version: bool

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

    identifier_series_match_identify_thresh: int
    identifier_border_crop_percent: int
    identifier_publisher_filter: list[str]
    identifier_series_match_search_thresh: int
    identifier_clear_metadata_on_import: bool
    identifier_auto_imprint: bool
    identifier_sort_series_by_year: bool
    identifier_exact_series_matches_first: bool
    identifier_always_use_publisher_filter: bool
    identifier_clear_form_before_populating: bool

    dialog_show_disclaimer: bool
    dialog_dont_notify_about_this_version: str
    dialog_ask_about_usage_stats: bool

    filename_complicated_parser: bool
    filename_remove_c2c: bool
    filename_remove_fcbd: bool
    filename_remove_publisher: bool

    talker_source: str

    cbl_assume_lone_credit_is_primary: bool
    cbl_copy_characters_to_tags: bool
    cbl_copy_teams_to_tags: bool
    cbl_copy_locations_to_tags: bool
    cbl_copy_storyarcs_to_tags: bool
    cbl_copy_notes_to_comments: bool
    cbl_copy_weblink_to_comments: bool
    cbl_apply_transform_on_import: bool
    cbl_apply_transform_on_bulk_operation: bool

    rename_template: str
    rename_issue_number_padding: int
    rename_use_smart_string_cleanup: bool
    rename_set_extension_based_on_archive: bool
    rename_dir: str
    rename_move_to_dir: bool
    rename_strict: bool
    rename_replacements: comictaggerlib.defaults.Replacements

    autotag_save_on_low_confidence: bool
    autotag_dont_use_year_when_identifying: bool
    autotag_assume_1_if_no_issue_num: bool
    autotag_ignore_leading_numbers_in_filename: bool
    autotag_remove_archive_after_successful_match: bool
