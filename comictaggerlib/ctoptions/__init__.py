from __future__ import annotations

from comictaggerlib.ctoptions.cmdline import initial_cmd_line_parser, register_commandline, validate_commandline_options
from comictaggerlib.ctoptions.file import register_settings, validate_settings
from comictaggerlib.ctoptions.plugin import register_plugin_settings, validate_plugin_settings
from comictaggerlib.ctoptions.talker_plugins import register_talker_settings
from comictaggerlib.ctoptions.types import ComicTaggerPaths

__all__ = [
    "initial_cmd_line_parser",
    "register_commandline",
    "register_settings",
    "register_plugin_settings",
    "register_talker_settings",
    "validate_commandline_options",
    "validate_settings",
    "validate_plugin_settings",
    "ComicTaggerPaths",
]
