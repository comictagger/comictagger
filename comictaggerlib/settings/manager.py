from __future__ import annotations

import argparse
import json
import logging
import pathlib
from collections import defaultdict
from collections.abc import Sequence
from typing import Any, Callable, NoReturn, Union

from comictaggerlib.settings.types import ComicTaggerPaths, OptionValues

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
        self.internal_name, dest, flag = self.get_dest(group, names, dest)
        args: Sequence[str] = names
        if not metavar and action not in ("store_true", "store_false", "count"):
            metavar = dest.upper()

        if not flag:
            args = [f"{group}_{names[0]}".lstrip("_"), *names[1:]]

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


ArgParser = Union[argparse._MutuallyExclusiveGroup, argparse._ArgumentGroup, argparse.ArgumentParser]


class Manager:
    """docstring for SettingManager"""

    def __init__(self, options: dict[str, dict[str, Setting]] | None = None):
        self.argparser = argparse.ArgumentParser()

        self.options: dict[str, dict[str, Setting]] = defaultdict(lambda: dict())
        if options:
            self.options = options

        self.current_group: ArgParser | None = None
        self.current_group_name = ""

    def defaults(self) -> OptionValues:
        return self.normalize_options({}, file=True, cmdline=True)

    def get_namespace_for_args(self, options: OptionValues) -> argparse.Namespace:
        namespace = argparse.Namespace()
        for group_name, group in self.options.items():
            for setting_name, setting in group.items():
                if not setting.cmdline:
                    if hasattr(namespace, setting.internal_name):
                        raise Exception(f"Duplicate internal name: {setting.internal_name}")
                    setattr(
                        namespace, setting.internal_name, options.get(group_name, {}).get(setting.dest, setting.default)
                    )
        return namespace

    def add_setting(self, *args: Any, **kwargs: Any) -> None:
        exclusive = isinstance(self.current_group, argparse._MutuallyExclusiveGroup)
        setting = Setting(*args, group=self.current_group_name, exclusive=exclusive, **kwargs)
        self.options[self.current_group_name][setting.dest] = setting

    def create_argparser(self) -> None:
        groups: dict[str, ArgParser] = {}
        self.argparser = argparse.ArgumentParser(
            description="""A utility for reading and writing metadata to comic archives.


If no options are given, %(prog)s will run in windowed mode.""",
            epilog="For more help visit the wiki at: https://github.com/comictagger/comictagger/wiki",
            formatter_class=argparse.RawTextHelpFormatter,
        )
        for group_name, group in self.options.items():
            for setting_name, setting in group.items():
                if setting.cmdline:
                    argparse_args, argparse_kwargs = setting.to_argparse()
                    current_group: ArgParser = self.argparser
                    if setting.group:
                        if setting.group not in groups:
                            if setting.exclusive:
                                groups[setting.group] = self.argparser.add_argument_group(
                                    setting.group
                                ).add_mutually_exclusive_group()
                            else:
                                groups[setting.group] = self.argparser.add_argument_group(setting.group)

                        # hardcoded exception for files
                        if not (setting.group == "runtime" and setting.nargs == "*"):
                            current_group = groups[setting.group]
                    current_group.add_argument(*argparse_args, **argparse_kwargs)

    def add_group(self, name: str, add_settings: Callable[[Manager], None], exclusive_group: bool = False) -> None:
        self.current_group_name = name
        if exclusive_group:
            self.current_group = self.argparser.add_mutually_exclusive_group()
        add_settings(self)
        self.current_group_name = ""
        self.current_group = None

    def exit(self, *args: Any, **kwargs: Any) -> NoReturn:
        self.argparser.exit(*args, **kwargs)
        raise SystemExit(99)

    def save_file(self, options: OptionValues, filename: pathlib.Path) -> bool:
        self.options = options["option_definitions"]
        file_options = self.normalize_options(options, file=True)
        del file_options["option_definitions"]
        for group in list(file_options.keys()):
            if not file_options[group]:
                del file_options[group]
        if not filename.exists():
            filename.touch()

        try:
            json_str = json.dumps(file_options, indent=2)
            with filename.open(mode="w") as file:
                file.write(json_str)
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
        self, raw_options: OptionValues | argparse.Namespace, file: bool = False, cmdline: bool = False
    ) -> OptionValues:
        options: OptionValues = {}
        for group_name, group in self.options.items():
            group_options = {}
            for setting_name, setting in group.items():
                if (setting.cmdline and cmdline) or (setting.file and file):
                    group_options[setting_name] = self.get_option(raw_options, setting, group_name)
            options[group_name] = group_options
        options["option_definitions"] = self.options
        return options

    def get_option(self, options: OptionValues | argparse.Namespace, setting: Setting, group_name: str) -> Any:
        if isinstance(options, dict):
            return options.get(group_name, {}).get(setting.dest, setting.default)
        return getattr(options, setting.internal_name)

    def parse_args(self, args: list[str] | None = None, namespace: argparse.Namespace | None = None) -> OptionValues:
        """Must handle a namespace with both argparse values and file values"""
        self.create_argparser()
        ns = self.argparser.parse_args(args, namespace=namespace)

        return self.normalize_options(ns, cmdline=True, file=True)

    def parse_options(self, config_paths: ComicTaggerPaths, args: list[str] | None = None) -> OptionValues:
        file_options = self.parse_file(config_paths.user_config_dir / "settings.json")
        cli_options = self.parse_args(args, namespace=self.get_namespace_for_args(file_options))

        if "runtime" in cli_options:
            # Just in case something weird happens with the commandline options
            cli_options["runtime"]["config"] = config_paths

        # Normalize a final time for fun
        return self.normalize_options(cli_options, file=True, cmdline=True)
