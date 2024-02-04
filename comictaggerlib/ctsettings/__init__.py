from __future__ import annotations

import json
import logging
import pathlib
from enum import Enum
from typing import Any

import settngs

from comictaggerlib.ctsettings.commandline import (
    initial_commandline_parser,
    register_commandline_settings,
    validate_commandline_settings,
)
from comictaggerlib.ctsettings.file import register_file_settings, validate_file_settings
from comictaggerlib.ctsettings.plugin import group_for_plugin, register_plugin_settings, validate_plugin_settings
from comictaggerlib.ctsettings.settngs_namespace import SettngsNS as ct_ns
from comictaggerlib.ctsettings.types import ComicTaggerPaths
from comictalker import ComicTalker

logger = logging.getLogger(__name__)

talkers: dict[str, ComicTalker] = {}

__all__ = [
    "initial_commandline_parser",
    "register_commandline_settings",
    "register_file_settings",
    "register_plugin_settings",
    "validate_commandline_settings",
    "validate_file_settings",
    "validate_plugin_settings",
    "ComicTaggerPaths",
    "ct_ns",
    "group_for_plugin",
]


class SettingsEncoder(json.JSONEncoder):
    def default(self, obj: Any) -> Any:
        if isinstance(obj, pathlib.Path):
            return str(obj)

        # Let the base class default method raise the TypeError
        return json.JSONEncoder.default(self, obj)


def validate_types(config: settngs.Config[settngs.Values]) -> settngs.Config[settngs.Values]:
    # Go through each setting
    for group in config.definitions.values():
        for setting in group.v.values():
            # Get the value and if it is the default
            value, default = settngs.get_option(config.values, setting)
            if not default:
                if setting.type is not None:
                    # If it is not the default and the type attribute is not None
                    # use it to convert the loaded string into the expected value
                    if (
                        isinstance(value, str)
                        or isinstance(default, Enum)
                        or (isinstance(setting.type, type) and issubclass(setting.type, Enum))
                    ):
                        config.values[setting.group][setting.dest] = setting.type(value)
    return config


def parse_config(
    manager: settngs.Manager,
    config_path: pathlib.Path,
    args: list[str] | None = None,
) -> tuple[settngs.Config[settngs.Values], bool]:
    """
    Function to parse options from a json file and passes the resulting Config object to parse_cmdline.

    Args:
        manager: settngs Manager object
        config_path: A `pathlib.Path` object
        args: Passed to argparse.ArgumentParser.parse_args
    """
    file_options, success = settngs.parse_file(manager.definitions, config_path)
    file_options = validate_types(file_options)
    cmdline_options = settngs.parse_cmdline(
        manager.definitions,
        manager.description,
        manager.epilog,
        args,
        file_options,
    )

    final_options = settngs.normalize_config(cmdline_options, file=True, cmdline=True)
    return final_options, success


def save_file(
    config: settngs.Config[settngs.T],
    filename: pathlib.Path,
) -> bool:
    """
    Helper function to save options from a json dictionary to a file

    Args:
        config: The options to save to a json dictionary
        filename: A pathlib.Path object to save the json dictionary to
    """
    file_options = settngs.clean_config(config, file=True)
    try:
        if not filename.exists():
            filename.parent.mkdir(exist_ok=True, parents=True)
            filename.touch()

        json_str = json.dumps(file_options, cls=SettingsEncoder, indent=2)
        filename.write_text(json_str + "\n", encoding="utf-8")
    except Exception:
        logger.exception("Failed to save config file: %s", filename)
        return False
    return True
