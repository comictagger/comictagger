from __future__ import annotations

import argparse
import pathlib
import sys
import types
import typing
from collections.abc import Collection, Mapping
from typing import Any

import yaml
from appdirs import AppDirs

from comicapi import utils
from comicapi.comicarchive import metadata_styles
from comicapi.genericmetadata import REMOVE, GenericMetadata

if sys.version_info < (3, 10):

    @typing.no_type_check
    def get_type_hints(obj, globalns=None, localns=None, include_extras=False):
        if getattr(obj, "__no_type_check__", None):
            return {}
        # Classes require a special treatment.
        if isinstance(obj, type):
            hints = {}
            for base in reversed(obj.__mro__):
                if globalns is None:
                    base_globals = getattr(sys.modules.get(base.__module__, None), "__dict__", {})
                else:
                    base_globals = globalns
                ann = base.__dict__.get("__annotations__", {})
                if isinstance(ann, types.GetSetDescriptorType):
                    ann = {}
                base_locals = dict(vars(base)) if localns is None else localns
                if localns is None and globalns is None:
                    # This is surprising, but required.  Before Python 3.10,
                    # get_type_hints only evaluated the globalns of
                    # a class.  To maintain backwards compatibility, we reverse
                    # the globalns and localns order so that eval() looks into
                    # *base_globals* first rather than *base_locals*.
                    # This only affects ForwardRefs.
                    base_globals, base_locals = base_locals, base_globals
                for name, value in ann.items():
                    if value is None:
                        value = type(None)
                    if isinstance(value, str):
                        if "|" in value:
                            value = "Union[" + value.replace(" |", ",") + "]"
                        value = typing.ForwardRef(value, is_argument=False, is_class=True)
                    value = typing._eval_type(value, base_globals, base_locals)
                    hints[name] = value
            return hints if include_extras else {k: typing._strip_annotations(t) for k, t in hints.items()}

        if globalns is None:
            if isinstance(obj, types.ModuleType):
                globalns = obj.__dict__
            else:
                nsobj = obj
                # Find globalns for the unwrapped object.
                while hasattr(nsobj, "__wrapped__"):
                    nsobj = nsobj.__wrapped__
                globalns = getattr(nsobj, "__globals__", {})
            if localns is None:
                localns = globalns
        elif localns is None:
            localns = globalns
        hints = getattr(obj, "__annotations__", None)
        if hints is None:
            # Return empty annotations for something that _could_ have them.
            if isinstance(obj, typing._allowed_types):
                return {}
            else:
                raise TypeError("{!r} is not a module, class, method, " "or function.".format(obj))
        hints = dict(hints)
        for name, value in hints.items():
            if value is None:
                value = type(None)
            if isinstance(value, str):
                if "|" in value:
                    value = "Union[" + value.replace(" |", ",") + "]"
                # class-level forward refs were handled above, this must be either
                # a module-level annotation or a function argument annotation
                value = typing.ForwardRef(
                    value,
                    is_argument=not isinstance(obj, types.ModuleType),
                    is_class=False,
                )
            hints[name] = typing._eval_type(value, globalns, localns)
        return hints if include_extras else {k: typing._strip_annotations(t) for k, t in hints.items()}

else:
    from typing import get_type_hints


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
    def user_plugin_dir(self) -> pathlib.Path:
        if self.path:
            path = self.path / "plugins"
            return path
        return pathlib.Path(super().user_config_dir)

    @property
    def site_data_dir(self) -> pathlib.Path:
        return pathlib.Path(super().site_data_dir)

    @property
    def site_config_dir(self) -> pathlib.Path:
        return pathlib.Path(super().site_config_dir)

    def __str__(self) -> str:
        return f"logs: {self.user_log_dir}, config: {self.user_config_dir}, cache: {self.user_cache_dir}"


def metadata_type_single(types: str) -> str:
    result = metadata_type(types)
    if len(result) > 1:
        raise argparse.ArgumentTypeError(f"invalid choice: {result} (only one metadata style allowed)")
    return result[0]


def metadata_type(types: str) -> list[str]:
    result = []
    types = types.casefold()
    for typ in utils.split(types, ","):
        if typ not in metadata_styles:
            choices = ", ".join(metadata_styles)
            raise argparse.ArgumentTypeError(f"invalid choice: {typ} (choose from {choices.upper()})")
        result.append(metadata_styles[typ].short_name)
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
        if not isinstance(value, t):
            if isinstance(value, (Mapping)):
                value = t(**value)
            elif not isinstance(value, str) and isinstance(value, (Collection)):
                value = t(*value)
            else:
                try:
                    if t is utils.Url and isinstance(value, str):
                        value = utils.parse_url(value)
                    else:
                        value = t(value)
                except (ValueError, TypeError):
                    raise argparse.ArgumentTypeError(f"Invalid syntax for tag '{key}'")
        return value

    md = GenericMetadata()

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
                if value == "" or value is None:
                    value = t[0]()
                else:
                    if isinstance(value, str):
                        values: list[Any] = value.split("::")
                    if not isinstance(value, Collection):
                        raise argparse.ArgumentTypeError(f"Invalid syntax for tag '{key}'")
                    values = list(value)
                    for idx, v in enumerate(values):
                        if not isinstance(v, t[1]):
                            values[idx] = convert_value(t[1], v)
                    value = t[0](values)
            elif value is not None:
                value = convert_value(t, value)

            empty = False
            setattr(md, key, value)
        else:
            raise argparse.ArgumentTypeError(f"'{key}' is not a valid tag name")
    md.is_empty = empty
    return md
