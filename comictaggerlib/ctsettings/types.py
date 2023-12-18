from __future__ import annotations

import argparse
import pathlib

from appdirs import AppDirs

from comicapi import utils
from comicapi.comicarchive import metadata_styles
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


def metadata_type_single(types: str) -> str:
    result = metadata_type(types)
    if len(result) > 1:
        raise argparse.ArgumentTypeError(f"invalid choice: {result} (only one metadata style allowed)")
    return result[0]


def metadata_type(types: str) -> list[str]:
    result = []
    types = types.casefold()
    for typ in utils.split(types, ","):
        typ = typ.strip()
        if typ not in metadata_styles:
            choices = ", ".join(metadata_styles)
            raise argparse.ArgumentTypeError(f"invalid choice: {typ} (choose from {choices.upper()})")
        result.append(metadata_styles[typ].short_name)
    return result


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
    tmp_list = utils.split(mdstr, ",")
    md_list = []
    for item in tmp_list:
        item = item.replace(replacement_token, ",")
        md_list.append(item)

    # Now build a nice dict from the list
    md_dict = {}
    for item in md_list:
        # Make sure to fix any escaped equal signs
        i = item.replace(escaped_equals, replacement_token)
        key, _, value = i.partition("=")
        value = value.replace(replacement_token, "=").strip()
        key = key.strip()
        if key.casefold() == "credit":
            cred_attribs = utils.split(value, ":")
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
