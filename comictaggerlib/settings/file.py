from __future__ import annotations

import argparse
import uuid
from collections.abc import Sequence
from typing import Any, Callable

from comictaggerlib.settings.manager import Manager


def general(parser: Manager) -> None:
    # General Settings
    parser.add_setting("--rar-exe-path", default="rar")
    parser.add_setting("--allow-cbi-in-rar", default=True, action=argparse.BooleanOptionalAction)
    parser.add_setting("check_for_new_version", default=False, cmdline=False)
    parser.add_setting("send_usage_stats", default=False, cmdline=False)


def internal(parser: Manager) -> None:
    # automatic settings
    parser.add_setting("install_id", default=uuid.uuid4().hex, cmdline=False)
    parser.add_setting("last_selected_save_data_style", default=0, cmdline=False)
    parser.add_setting("last_selected_load_data_style", default=0, cmdline=False)
    parser.add_setting("last_opened_folder", default="", cmdline=False)
    parser.add_setting("last_main_window_width", default=0, cmdline=False)
    parser.add_setting("last_main_window_height", default=0, cmdline=False)
    parser.add_setting("last_main_window_x", default=0, cmdline=False)
    parser.add_setting("last_main_window_y", default=0, cmdline=False)
    parser.add_setting("last_form_side_width", default=-1, cmdline=False)
    parser.add_setting("last_list_side_width", default=-1, cmdline=False)
    parser.add_setting("last_filelist_sorted_column", default=-1, cmdline=False)
    parser.add_setting("last_filelist_sorted_order", default=0, cmdline=False)


def identifier(parser: Manager) -> None:
    # identifier settings
    parser.add_setting("--series-match-identify-thresh", default=91, type=int)
    parser.add_setting(
        "--publisher-filter",
        default=["Panini Comics", "Abril", "Planeta DeAgostini", "Editorial Televisa", "Dino Comics"],
        action=_AppendAction,
    )


def _copy_items(items: Sequence[Any] | None) -> Sequence[Any]:
    if items is None:
        return []
    # The copy module is used only in the 'append' and 'append_const'
    # actions, and it is needed only when the default value isn't a list.
    # Delay its import for speeding up the common case.
    if type(items) is list:
        return items[:]
    import copy

    return copy.copy(items)


class _AppendAction(argparse.Action):
    def __init__(
        self,
        option_strings: list[str],
        dest: str,
        nargs: str | None = None,
        const: Any = None,
        default: Any = None,
        type: Callable[[str], Any] | None = None,  # noqa: A002
        choices: list[Any] | None = None,
        required: bool = False,
        help: str | None = None,  # noqa: A002
        metavar: str | None = None,
    ):
        self.called = False
        if nargs == 0:
            raise ValueError(
                "nargs for append actions must be != 0; if arg "
                "strings are not supplying the value to append, "
                "the append const action may be more appropriate"
            )
        if const is not None and nargs != argparse.OPTIONAL:
            raise ValueError("nargs must be %r to supply const" % argparse.OPTIONAL)
        super().__init__(
            option_strings=option_strings,
            dest=dest,
            nargs=nargs,
            const=const,
            default=default,
            type=type,
            choices=choices,
            required=required,
            help=help,
            metavar=metavar,
        )

    def __call__(
        self,
        parser: argparse.ArgumentParser,
        namespace: argparse.Namespace,
        values: str | Sequence[Any] | None,
        option_string: str | None = None,
    ) -> None:
        if values:
            if not self.called:
                setattr(namespace, self.dest, [])
            items = getattr(namespace, self.dest, None)
            items = _copy_items(items)
            items.append(values)  # type: ignore
            setattr(namespace, self.dest, items)


def dialog(parser: Manager) -> None:
    # Show/ask dialog flags
    parser.add_setting("ask_about_cbi_in_rar", default=True, cmdline=False)
    parser.add_setting("show_disclaimer", default=True, cmdline=False)
    parser.add_setting("dont_notify_about_this_version", default="", cmdline=False)
    parser.add_setting("ask_about_usage_stats", default=True, cmdline=False)


def filename(parser: Manager) -> None:
    # filename parsing settings
    parser.add_setting("--complicated-parser", default=False, action=argparse.BooleanOptionalAction)
    parser.add_setting("--remove-c2c", default=False, action=argparse.BooleanOptionalAction)
    parser.add_setting("--remove-fcbd", default=False, action=argparse.BooleanOptionalAction)
    parser.add_setting("--remove-publisher", default=False, action=argparse.BooleanOptionalAction)


def comicvine(parser: Manager) -> None:
    # Comic Vine settings
    parser.add_setting(
        "--series-match-search-thresh",
        default=90,
    )
    parser.add_setting("--use-series-start-as-volume", default=False, action=argparse.BooleanOptionalAction)
    parser.add_setting(
        "--overwrite",
        default=True,
        help="Overwrite all existing metadata.\nMay be used in conjunction with -o, -f and -m.\n\n",
        dest="clear_metadata_on_import",
        action=argparse.BooleanOptionalAction,
    )
    parser.add_setting("--remove-html-tables", default=False, action=argparse.BooleanOptionalAction)
    parser.add_setting(
        "--cv-api-key",
        default="",
        help="Use the given Comic Vine API Key (persisted in settings).",
    )
    parser.add_setting(
        "--cv-url",
        default="",
        help="Use the given Comic Vine URL (persisted in settings).",
    )
    parser.add_setting(
        "-a",
        "--auto-imprint",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="""Enables the auto imprint functionality.\ne.g. if the publisher is set to 'vertigo' it\nwill be updated to 'DC Comics' and the imprint\nproperty will be set to 'Vertigo'.\n\n""",
    )

    parser.add_setting("--sort-series-by-year", default=True, action=argparse.BooleanOptionalAction)
    parser.add_setting("--exact-series-matches-first", default=True, action=argparse.BooleanOptionalAction)
    parser.add_setting("--always-use-publisher-filter", default=False, action=argparse.BooleanOptionalAction)
    parser.add_setting("--clear-form-before-populating-from-cv", default=False, action=argparse.BooleanOptionalAction)


def cbl(parser: Manager) -> None:
    # CBL Transform settings
    parser.add_setting("--assume-lone-credit-is-primary", default=False, action=argparse.BooleanOptionalAction)
    parser.add_setting("--copy-characters-to-tags", default=False, action=argparse.BooleanOptionalAction)
    parser.add_setting("--copy-teams-to-tags", default=False, action=argparse.BooleanOptionalAction)
    parser.add_setting("--copy-locations-to-tags", default=False, action=argparse.BooleanOptionalAction)
    parser.add_setting("--copy-storyarcs-to-tags", default=False, action=argparse.BooleanOptionalAction)
    parser.add_setting("--copy-notes-to-comments", default=False, action=argparse.BooleanOptionalAction)
    parser.add_setting("--copy-weblink-to-comments", default=False, action=argparse.BooleanOptionalAction)
    parser.add_setting("--apply-cbl-transform-on-cv-import", default=False, action=argparse.BooleanOptionalAction)
    parser.add_setting("--apply-cbl-transform-on-bulk-operation", default=False, action=argparse.BooleanOptionalAction)


def rename(parser: Manager) -> None:
    # Rename settings
    parser.add_setting("--template", default="{series} #{issue} ({year})")
    parser.add_setting("--issue-number-padding", default=3, type=int)
    parser.add_setting("--use-smart-string-cleanup", default=True, action=argparse.BooleanOptionalAction)
    parser.add_setting("--set-extension-based-on-archive", default=True, action=argparse.BooleanOptionalAction)
    parser.add_setting("--dir", default="")
    parser.add_setting("--move-to-dir", default=False, action=argparse.BooleanOptionalAction)
    parser.add_setting("--strict", default=False, action=argparse.BooleanOptionalAction)


def autotag(parser: Manager) -> None:
    # Auto-tag stickies
    parser.add_setting("--save-on-low-confidence", default=False, action=argparse.BooleanOptionalAction)
    parser.add_setting("--dont-use-year-when-identifying", default=False, action=argparse.BooleanOptionalAction)
    parser.add_setting(
        "-1",
        "--assume-issue-one",
        dest="assume_1_if_no_issue_num",
        action=argparse.BooleanOptionalAction,
        help="""Assume issue number is 1 if not found (relevant for -s).\n\n""",
        default=False,
    )
    parser.add_setting("--ignore-leading-numbers-in-filename", default=False, action=argparse.BooleanOptionalAction)
    parser.add_setting("--remove-archive-after-successful-match", default=False, action=argparse.BooleanOptionalAction)
    parser.add_setting(
        "-w",
        "--wait-on-cv-rate-limit",
        dest="wait_and_retry_on_rate_limit",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="""When encountering a Comic Vine rate limit\nerror, wait and retry query.\n\n""",
    )


def validate_settings(options: dict[str, dict[str, Any]], parser: Manager) -> dict[str, dict[str, Any]]:
    options["identifier"]["publisher_filter"] = [
        x.strip() for x in options["identifier"]["publisher_filter"] if x.strip()
    ]
    return options


def register_settings(parser: Manager) -> None:
    parser.add_group("general", general, False)
    parser.add_group("internal", internal, False)
    parser.add_group("identifier", identifier, False)
    parser.add_group("dialog", dialog, False)
    parser.add_group("filename", filename, False)
    parser.add_group("comicvine", comicvine, False)
    parser.add_group("cbl", cbl, False)
    parser.add_group("rename", rename, False)
    parser.add_group("autotag", autotag, False)
