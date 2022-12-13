from __future__ import annotations

import argparse
import json
import logging
import pathlib
from collections import defaultdict
from collections.abc import Sequence
from typing import TYPE_CHECKING, Any, Callable, NoReturn, Union

logger = logging.getLogger(__name__)


class Setting:
    def __init__(
        self,
        # From argparse
        *names: str,
        action: type[argparse.Action] | None = None,
        nargs: str | int | None = None,
        const: str | None = None,
        default: str | None = None,
        type: Callable[..., Any] | None = None,  # noqa: A002
        choices: Sequence[Any] | None = None,
        required: bool | None = None,
        help: str | None = None,  # noqa: A002
        metavar: str | None = None,
        dest: str | None = None,
        # ComicTagger
        cmdline: bool = True,
        file: bool = True,
        group: str = "",
        exclusive: bool = False,
    ):
        if not names:
            raise ValueError("names must be specified")
        # We prefix the destination name used by argparse so that there are no conflicts
        # Argument names will still cause an exception if there is a conflict e.g. if '-f' is defined twice
        self.internal_name, dest, flag = self.get_dest(group, names, dest)
        args: Sequence[str] = names

        # We then also set the metavar so that '--config' in the group runtime shows as 'CONFIG' instead of 'RUNTIME_CONFIG'
        if not metavar and action not in ("store_true", "store_false", "count"):
            metavar = dest.upper()

        # If we are not a flag, no '--' or '-' in front
        # we prefix the first name with the group as argparse sets dest to args[0]
        # I believe internal name may be able to be used here
        if not flag:
            args = tuple((f"{group}_{names[0]}".lstrip("_"), *names[1:]))

        self.action = action
        self.nargs = nargs
        self.const = const
        self.default = default
        self.type = type
        self.choices = choices
        self.required = required
        self.help = help
        self.metavar = metavar
        self.dest = dest
        self.cmdline = cmdline
        self.file = file
        self.argparse_args = args
        self.group = group
        self.exclusive = exclusive

        self.argparse_kwargs = {
            "action": action,
            "nargs": nargs,
            "const": const,
            "default": default,
            "type": type,
            "choices": choices,
            "required": required,
            "help": help,
            "metavar": metavar,
            "dest": self.internal_name if flag else None,
        }

    def __str__(self) -> str:
        return f"Setting({self.argparse_args}, type={self.type}, file={self.file}, cmdline={self.cmdline}, kwargs={self.argparse_kwargs})"

    def __repr__(self) -> str:
        return self.__str__()

    def get_dest(self, prefix: str, names: Sequence[str], dest: str | None) -> tuple[str, str, bool]:
        dest_name = None
        flag = False

        for n in names:
            if n.startswith("--"):
                flag = True
                dest_name = n.lstrip("-").replace("-", "_")
                break
            if n.startswith("-"):
                flag = True

        if dest_name is None:
            dest_name = names[0]
        if dest:
            dest_name = dest
        if dest_name is None:
            raise Exception("Something failed, try again")

        internal_name = f"{prefix}_{dest_name}".lstrip("_")
        return internal_name, dest_name, flag

    def filter_argparse_kwargs(self) -> dict[str, Any]:
        return {k: v for k, v in self.argparse_kwargs.items() if v is not None}

    def to_argparse(self) -> tuple[Sequence[str], dict[str, Any]]:
        return self.argparse_args, self.filter_argparse_kwargs()


OptionValues = dict[str, dict[str, Any]]
OptionDefinitions = dict[str, dict[str, Setting]]
if TYPE_CHECKING:
    ArgParser = Union[argparse._MutuallyExclusiveGroup, argparse._ArgumentGroup, argparse.ArgumentParser]


def get_option(options: OptionValues | argparse.Namespace, setting: Setting) -> tuple[Any, bool]:
    """
    Helper function to retrieve the value for a setting and if the value is the default value

    Args:
        options: Dictionary or namespace of options
        setting: The setting object describing the value to retrieve
    """
    if isinstance(options, dict):
        value = options.get(setting.group, {}).get(setting.dest, setting.default)
    else:
        value = getattr(options, setting.internal_name, setting.default)
    return value, value == setting.default


def normalize_options(
    raw_options: OptionValues | argparse.Namespace,
    definitions: OptionDefinitions,
    file: bool = False,
    cmdline: bool = False,
    defaults: bool = True,
    raw_options_2: OptionValues | argparse.Namespace | None = None,
) -> OptionValues:
    """
    Creates an `OptionValues` dictionary with setting definitions taken from `self.definitions`
    and values taken from `raw_options` and `raw_options_2' if defined.
    Values are assigned so if the value is a dictionary mutating it will mutate the original.

    Args:
        raw_options: The dict or Namespace to normalize options from
        definitions: The definition of the options
        file: Include file options
        cmdline: Include cmdline options
        defaults: Include default values in the returned dict
        raw_options_2: If set, merges non-default values into the returned dict
    """
    options: OptionValues = {}
    for group_name, group in definitions.items():
        group_options = {}
        for setting_name, setting in group.items():
            if (setting.cmdline and cmdline) or (setting.file and file):
                # Ensures the option exists with the default if not already set
                value, default = get_option(raw_options, setting)
                if not default or default and defaults:
                    group_options[setting_name] = value

                # will override with option from raw_options_2 if it is not the default
                if raw_options_2 is not None:
                    value, default = get_option(raw_options_2, setting)
                    if not default:
                        group_options[setting_name] = value
        options[group_name] = group_options
    options["definitions"] = definitions
    return options


def parse_file(filename: pathlib.Path, definitions: OptionDefinitions) -> OptionValues:
    """
    Helper function to read options from a json dictionary from a file
    Args:
        filename: A pathlib.Path object to read a json dictionary from
    """
    options: OptionValues = {}
    if filename.exists():
        try:
            with filename.open() as file:
                opts = json.load(file)
            if isinstance(opts, dict):
                options = opts
        except Exception:
            logger.exception("Failed to load config file: %s", filename)
    else:
        logger.info("No config file found")

    return normalize_options(options, definitions, file=True)


def clean_options(
    options: OptionValues | argparse.Namespace, definitions: OptionDefinitions, file: bool = False, cmdline: bool = True
) -> OptionValues:
    """
    Normalizes options and then cleans up empty groups and removes 'definitions'
    Args:
        options:
        file:
        cmdline:

    Returns:

    """

    clean_options = normalize_options(options, definitions, file=file, cmdline=cmdline)
    del clean_options["definitions"]
    for group in list(clean_options.keys()):
        if not clean_options[group]:
            del clean_options[group]
    return clean_options


def defaults(definitions: OptionDefinitions) -> OptionValues:
    return normalize_options({}, definitions, file=True, cmdline=True)


def get_namespace(options: OptionValues, definitions: OptionDefinitions, defaults: bool = True) -> argparse.Namespace:
    """
    Returns an argparse.Namespace object with options in the form "{group_name}_{setting_name}"
    `options` should already be normalized.
    Throws an exception if the internal_name is duplicated

    Args:
        options: Normalized options to turn into a Namespace
        defaults: Include default values in the returned dict
    """
    options = normalize_options(options, definitions, file=True, cmdline=True)
    namespace = argparse.Namespace()
    for group_name, group in definitions.items():
        for setting_name, setting in group.items():
            if hasattr(namespace, setting.internal_name):
                raise Exception(f"Duplicate internal name: {setting.internal_name}")
            value, default = get_option(options, setting)

            if not default or default and defaults:
                setattr(
                    namespace,
                    setting.internal_name,
                    value,
                )
    setattr(namespace, "definitions", definitions)
    return namespace


def save_file(
    options: OptionValues | argparse.Namespace, definitions: OptionDefinitions, filename: pathlib.Path
) -> bool:
    """
    Helper function to save options from a json dictionary to a file
    Args:
        options: The options to save to a json dictionary
        filename: A pathlib.Path object to save the json dictionary to
    """
    file_options = clean_options(options, definitions, file=True)
    if not filename.exists():
        filename.parent.mkdir(exist_ok=True, parents=True)
        filename.touch()

    try:
        json_str = json.dumps(file_options, indent=2)
        filename.write_text(json_str, encoding="utf-8")
    except Exception:
        logger.exception("Failed to save config file: %s", filename)
        return False
    return True


class Manager:
    """docstring for SettingManager"""

    def __init__(
        self, description: str | None = None, epilog: str | None = None, definitions: OptionDefinitions | None = None
    ):
        # This one is never used, it just makes MyPy happy
        self.argparser = argparse.ArgumentParser(description=description, epilog=epilog)
        self.description = description
        self.epilog = epilog

        self.definitions: OptionDefinitions = defaultdict(lambda: dict())
        if definitions:
            self.definitions = definitions

        self.exclusive_group = False
        self.current_group_name = ""

    def add_setting(self, *args: Any, **kwargs: Any) -> None:
        """Takes passes all arguments through to `Setting`, `group` and `exclusive` are already set"""
        setting = Setting(*args, group=self.current_group_name, exclusive=self.exclusive_group, **kwargs)
        self.definitions[self.current_group_name][setting.dest] = setting

    def create_argparser(self) -> None:
        """Creates an :class:`argparse.ArgumentParser` from all cmdline settings"""
        groups: dict[str, ArgParser] = {}
        self.argparser = argparse.ArgumentParser(
            description=self.description,
            epilog=self.epilog,
            formatter_class=argparse.RawTextHelpFormatter,
        )
        for group_name, group in self.definitions.items():
            for setting_name, setting in group.items():
                if setting.cmdline:
                    argparse_args, argparse_kwargs = setting.to_argparse()
                    current_group: ArgParser = self.argparser
                    if setting.group:
                        if setting.group not in groups:
                            if setting.exclusive:
                                groups[setting.group] = self.argparser.add_argument_group(
                                    setting.group,
                                ).add_mutually_exclusive_group()
                            else:
                                groups[setting.group] = self.argparser.add_argument_group(setting.group)

                        # hard coded exception for files
                        if not (setting.group == "runtime" and setting.nargs == "*"):
                            current_group = groups[setting.group]
                    current_group.add_argument(*argparse_args, **argparse_kwargs)

    def add_group(self, name: str, add_settings: Callable[[Manager], None], exclusive_group: bool = False) -> None:
        """
        The primary way to add define options on this class

        Args:
            name: The name of the group to define
            add_settings: A function that registers individual options using :meth:`add_setting`
            exclusive_group: If this group is an argparse exclusive group
        """
        self.current_group_name = name
        self.exclusive_group = exclusive_group
        add_settings(self)
        self.current_group_name = ""
        self.exclusive_group = False

    def exit(self, *args: Any, **kwargs: Any) -> NoReturn:
        """See :class:`~argparse.ArgumentParser`"""
        self.argparser.exit(*args, **kwargs)
        raise SystemExit(99)

    def defaults(self) -> OptionValues:
        return defaults(self.definitions)

    def clean_options(
        self, options: OptionValues | argparse.Namespace, file: bool = False, cmdline: bool = True
    ) -> OptionValues:
        return clean_options(options=options, definitions=self.definitions, file=file, cmdline=cmdline)

    def normalize_options(
        self,
        raw_options: OptionValues | argparse.Namespace,
        file: bool = False,
        cmdline: bool = False,
        defaults: bool = True,
        raw_options_2: OptionValues | argparse.Namespace | None = None,
    ) -> OptionValues:
        return normalize_options(
            raw_options=raw_options,
            definitions=self.definitions,
            file=file,
            cmdline=cmdline,
            defaults=defaults,
            raw_options_2=raw_options_2,
        )

    def get_namespace(self, options: OptionValues, defaults: bool = True) -> argparse.Namespace:
        return get_namespace(options=options, definitions=self.definitions, defaults=defaults)

    def parse_file(self, filename: pathlib.Path) -> OptionValues:
        return parse_file(filename=filename, definitions=self.definitions)

    def save_file(self, options: OptionValues | argparse.Namespace, filename: pathlib.Path) -> bool:
        return save_file(options=options, definitions=self.definitions, filename=filename)

    def parse_args(self, args: list[str] | None = None, namespace: argparse.Namespace | None = None) -> OptionValues:
        """
        Creates an `argparse.ArgumentParser` from cmdline settings in `self.definitions`.
        `args` and `namespace` are passed to `argparse.ArgumentParser.parse_args`

        Args:
            args: Passed to argparse.ArgumentParser.parse
            namespace: Passed to argparse.ArgumentParser.parse
        """
        self.create_argparser()
        ns = self.argparser.parse_args(args, namespace=namespace)

        return normalize_options(ns, definitions=self.definitions, cmdline=True, file=True)

    def parse_options(self, config_path: pathlib.Path, args: list[str] | None = None) -> OptionValues:
        file_options = self.parse_file(
            config_path,
        )
        cli_options = self.parse_args(args, self.get_namespace(file_options, defaults=False))

        final_options = normalize_options(cli_options, definitions=self.definitions, file=True, cmdline=True)
        return final_options
