from __future__ import annotations

import argparse
import pathlib
from collections.abc import Sequence
from typing import Any, Callable

from appdirs import AppDirs

from comicapi.comicarchive import MetaDataStyle
from comicapi.genericmetadata import GenericMetadata


class ComicTaggerPaths(AppDirs):
    def __init__(self, config_path: pathlib.Path | str | None = None) -> None:
        super().__init__("ComicTagger", None, None, False, False)
        self.path: pathlib.Path | None = None
        if config_path:
            self.path = pathlib.Path(config_path).absolute()

    @property
    def user_data_dir(self) -> pathlib.Path:
        if self.path:
            return self.path
        return pathlib.Path(super().user_data_dir)

    @property
    def user_config_dir(self) -> pathlib.Path:
        if self.path:
            return self.path
        return pathlib.Path(super().user_config_dir)

    @property
    def user_cache_dir(self) -> pathlib.Path:
        if self.path:
            path = self.path / "cache"
            return path
        return pathlib.Path(super().user_cache_dir)

    @property
    def user_state_dir(self) -> pathlib.Path:
        if self.path:
            return self.path
        return pathlib.Path(super().user_state_dir)

    @property
    def user_log_dir(self) -> pathlib.Path:
        if self.path:
            path = self.path / "log"
            return path
        return pathlib.Path(super().user_log_dir)

    @property
    def site_data_dir(self) -> pathlib.Path:
        return pathlib.Path(super().site_data_dir)

    @property
    def site_config_dir(self) -> pathlib.Path:
        return pathlib.Path(super().site_config_dir)


def metadata_type(types: str) -> list[int]:
    result = []
    types = types.casefold()
    for typ in types.split(","):
        typ = typ.strip()
        if typ not in MetaDataStyle.short_name:
            choices = ", ".join(MetaDataStyle.short_name)
            raise argparse.ArgumentTypeError(f"invalid choice: {typ} (choose from {choices.upper()})")
        result.append(MetaDataStyle.short_name.index(typ))
    return result


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


class AppendAction(argparse.Action):
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


def parse_metadata_from_string(mdstr: str) -> GenericMetadata:
    """The metadata string is a comma separated list of name-value pairs
    The names match the attributes of the internal metadata struct (for now)
    The caret is the special "escape character", since it's not common in
    natural language text

    example = "series=Kickers^, Inc. ,issue=1, year=1986"
    """

    escaped_comma = "^,"
    escaped_equals = "^="
    replacement_token = "<_~_>"

    md = GenericMetadata()

    # First, replace escaped commas with with a unique token (to be changed back later)
    mdstr = mdstr.replace(escaped_comma, replacement_token)
    tmp_list = mdstr.split(",")
    md_list = []
    for item in tmp_list:
        item = item.replace(replacement_token, ",")
        md_list.append(item)

    # Now build a nice dict from the list
    md_dict = {}
    for item in md_list:
        # Make sure to fix any escaped equal signs
        i = item.replace(escaped_equals, replacement_token)
        key, value = i.split("=")
        value = value.replace(replacement_token, "=").strip()
        key = key.strip()
        if key.casefold() == "credit":
            cred_attribs = value.split(":")
            role = cred_attribs[0]
            person = cred_attribs[1] if len(cred_attribs) > 1 else ""
            primary = len(cred_attribs) > 2
            md.add_credit(person.strip(), role.strip(), primary)
        else:
            md_dict[key] = value

    # Map the dict to the metadata object
    for key, value in md_dict.items():
        if not hasattr(md, key):
            raise argparse.ArgumentTypeError(f"'{key}' is not a valid tag name")
        else:
            md.is_empty = False
            setattr(md, key, value)
    return md
