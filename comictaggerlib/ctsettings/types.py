from __future__ import annotations

import argparse
import logging
import pathlib
import types
import typing
from collections.abc import Collection, Mapping
from typing import Any, get_type_hints

import yaml
from appdirs import AppDirs

from comicapi import utils
from comicapi.comicarchive import loaded_tags
from comicapi.genericmetadata import REMOVE, GenericMetadata
from comicapi.tags import Tag

logger = logging.getLogger(__name__)


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
            return self.path / "cache"
        return pathlib.Path(super().user_cache_dir)

    @property
    def user_state_dir(self) -> pathlib.Path:
        if self.path:
            return self.path
        return pathlib.Path(super().user_state_dir)

    @property
    def user_log_dir(self) -> pathlib.Path:
        if self.path:
            return self.path / "log"
        return pathlib.Path(super().user_log_dir)

    @property
    def user_plugin_dir(self) -> pathlib.Path:
        if self.path:
            return self.path / "plugins"
        return pathlib.Path(super().user_config_dir) / "plugins"

    @property
    def site_data_dir(self) -> pathlib.Path:
        return pathlib.Path(super().site_data_dir)

    @property
    def site_config_dir(self) -> pathlib.Path:
        return pathlib.Path(super().site_config_dir)

    def __str__(self) -> str:
        return f"logs: {self.user_log_dir}, config: {self.user_config_dir}, cache: {self.user_cache_dir}"


def tag(types: str) -> list[Tag]:
    enabled_tags = [tag for tag in loaded_tags.values() if tag.enabled]
    result: list[Tag] = []
    types = types.casefold()
    ids = [tag.id for tag in enabled_tags]
    for typ in utils.split(types, ","):
        if typ not in ids:
            choices = ", ".join(ids)
            raise argparse.ArgumentTypeError(f"invalid choice: {typ} (choose from {choices.upper()})")
        result.append(loaded_tags[typ])
    return result


def parse_metadata_from_string(mdstr: str) -> GenericMetadata:

    def get_type(key: str, tt: Any = get_type_hints(GenericMetadata)) -> Any:
        t: Any = tt.get(key, None)
        if t is None:
            return None
        if getattr(t, "__origin__", None) is typing.Union and len(t.__args__) == 2 and t.__args__[1] is type(None):
            t = t.__args__[0]
        elif isinstance(t, types.GenericAlias) and issubclass(t.mro()[0], Collection):
            t = t.mro()[0], t.__args__[0]

        if isinstance(t, tuple) and issubclass(t[1], dict):
            return (t[0], dict)
        if isinstance(t, type) and issubclass(t, dict):
            return dict
        return t

    def convert_value(t: type, value: Any) -> Any:
        if isinstance(value, t):
            return value
        try:
            if isinstance(value, (Mapping)):
                value = t(**value)
            elif not isinstance(value, str) and isinstance(value, (Collection)):
                value = t(*value)
            else:
                if t is utils.Url and isinstance(value, str):
                    value = utils.parse_url(value)
                else:
                    value = t(value)
        except (ValueError, TypeError):
            raise argparse.ArgumentTypeError(f"Invalid syntax for tag {key!r}: {value!r}")
        return value

    md = GenericMetadata()

    try:
        if not mdstr:
            return md
        if mdstr[0] == "@":
            p = pathlib.Path(mdstr[1:])
            if not p.is_file():
                raise argparse.ArgumentTypeError("Invalid filepath")
            mdstr = p.read_text()
        if mdstr[0] != "{":
            mdstr = "{" + mdstr + "}"

        md_dict = yaml.safe_load(mdstr)

        empty = True
        # Map the dict to the metadata object
        for key, value in md_dict.items():
            if hasattr(md, key):
                t = get_type(key)
                if value is None:
                    value = REMOVE
                elif isinstance(t, tuple):
                    if value == "":
                        value = t[0]()
                    else:
                        if isinstance(value, str):
                            value = [value]
                        if not isinstance(value, Collection):
                            raise argparse.ArgumentTypeError(f"Invalid syntax for tag '{key}'")
                        values = list(value)
                        for idx, v in enumerate(values):
                            if not isinstance(v, t[1]):
                                values[idx] = convert_value(t[1], v)
                        value = t[0](values)
                else:
                    value = convert_value(t, value)

                empty = False
                setattr(md, key, value)
            else:
                raise argparse.ArgumentTypeError(f"'{key}' is not a valid tag name")
        md.is_empty = empty
    except argparse.ArgumentTypeError as e:
        raise e
    except Exception as e:
        logger.exception("Unable to read metadata from the commandline '%s'", mdstr)
        raise Exception("Unable to read metadata from the commandline") from e
    return md
