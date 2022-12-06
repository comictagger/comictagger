from __future__ import annotations

import argparse
import json
import logging
import pathlib
from collections import defaultdict
from collections.abc import Sequence
from typing import Any, Callable, NoReturn, Union

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
ArgParser = Union[argparse._MutuallyExclusiveGroup, argparse._ArgumentGroup, argparse.ArgumentParser]


class Manager:
    """docstring for SettingManager"""

    def __init__(
        self, description: str | None = None, epilog: str | None = None, definitions: OptionDefinitions | None = None
    ):
        # This one is never used, it just makes MyPy happy
        self.argparser = argparse.ArgumentParser(description=description, epilog=epilog)
        self.description = description
        self.epilog = epilog

        self.option_definitions: OptionDefinitions = defaultdict(lambda: dict())
        if definitions:
            self.option_definitions = definitions

        self.exclusive_group = False
        self.current_group_name = ""

    def defaults(self) -> OptionValues:
        return self.normalize_options({}, file=True, cmdline=True)

    def get_namespace(self, options: OptionValues) -> argparse.Namespace:
        """
        Returns an argparse.Namespace object with options in the form "{group_name}_{setting_name}"
        `options` should already be normalized.
        Throws an exception if the internal_name is duplicated
        """
        namespace = argparse.Namespace()
        for group_name, group in self.option_definitions.items():
            for setting_name, setting in group.items():
                if hasattr(namespace, setting.internal_name):
                    raise Exception(f"Duplicate internal name: {setting.internal_name}")
                setattr(
                    namespace,
                    setting.internal_name,
                    options.get(group_name, {}).get(
                        setting.dest,
                        setting.default,
                    ),
                )
        setattr(namespace, "option_definitions", options.get("option_definitions"))
        return namespace

    def add_setting(self, *args: Any, **kwargs: Any) -> None:
        """Takes passes all arguments through to `Setting`, `group` and `exclusive` are already set"""
        setting = Setting(*args, group=self.current_group_name, exclusive=self.exclusive_group, **kwargs)
        self.option_definitions[self.current_group_name][setting.dest] = setting

    def create_argparser(self) -> None:
        """Creates an argparser object from all cmdline settings"""
        groups: dict[str, ArgParser] = {}
        self.argparser = argparse.ArgumentParser(
            description=self.description,
            epilog=self.epilog,
            formatter_class=argparse.RawTextHelpFormatter,
        )
        for group_name, group in self.option_definitions.items():
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
        self.current_group_name = name
        self.exclusive_group = exclusive_group
        add_settings(self)
        self.current_group_name = ""
        self.exclusive_group = False

    def exit(self, *args: Any, **kwargs: Any) -> NoReturn:
        """Same as `argparser.ArgParser.exit`"""
        self.argparser.exit(*args, **kwargs)
        raise SystemExit(99)

    def save_file(self, options: OptionValues | argparse.Namespace, filename: pathlib.Path) -> bool:
        if isinstance(options, dict):
            self.option_definitions = options["option_definitions"]
        elif isinstance(options, argparse.Namespace):
            self.option_definitions = options.option_definitions

        file_options = self.normalize_options(options, file=True)
        del file_options["option_definitions"]
        for group in list(file_options.keys()):
            if not file_options[group]:
                del file_options[group]
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

    def parse_file(self, filename: pathlib.Path) -> OptionValues:
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

        return self.normalize_options(options, file=True)

    def normalize_options(
        self,
        raw_options: OptionValues | argparse.Namespace,
        file: bool = False,
        cmdline: bool = False,
        raw_options_2: OptionValues | argparse.Namespace | None = None,
    ) -> OptionValues:
        """
        Creates an `OptionValues` dictionary with setting definitions taken from `self.option_definitions`
        and values taken from `raw_options` and `raw_options_2' if defined.
        Values are assigned so if the value is a dictionary mutating it will mutate the original.
        """
        options: OptionValues = {}
        for group_name, group in self.option_definitions.items():
            group_options = {}
            for setting_name, setting in group.items():
                if (setting.cmdline and cmdline) or (setting.file and file):
                    # Ensures the option exists with the default if not already set
                    group_options[setting_name], _ = self.get_option(raw_options, setting, group_name)

                    # will override with option from raw_options_2 if it exists
                    if raw_options_2 is not None:
                        value, default = self.get_option(raw_options_2, setting, group_name)
                        if not default:
                            group_options[setting_name] = value
            options[group_name] = group_options
        options["option_definitions"] = self.option_definitions
        return options

    def get_option(
        self, options: OptionValues | argparse.Namespace, setting: Setting, group_name: str
    ) -> tuple[Any, bool]:
        """Helper function to retrieve the the value for a setting and if the value is the default value"""
        if isinstance(options, dict):
            value = options.get(group_name, {}).get(setting.dest, setting.default)
        else:
            value = getattr(options, setting.internal_name, setting.default)
        return value, value == setting.default

    def parse_args(self, args: list[str] | None = None, namespace: argparse.Namespace | None = None) -> OptionValues:
        """
        Creates an `argparse.ArgumentParser` from cmdline settings in `self.option_definitions`.
        `args` and `namespace` are passed to `argparse.ArgumentParser.parse_args`
        """
        self.create_argparser()
        ns = self.argparser.parse_args(args, namespace=namespace)

        return self.normalize_options(ns, cmdline=True, file=False)

    def parse_options(self, config_path: pathlib.Path, args: list[str] | None = None) -> OptionValues:
        file_options = self.parse_file(config_path)
        cli_options = self.parse_args(args)

        final_options = self.normalize_options(file_options, file=True, cmdline=True, raw_options_2=cli_options)
        return final_options
