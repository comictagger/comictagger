from __future__ import annotations

from comictaggerlib.ctsettings.commandline import (
    initial_commandline_parser,
    register_commandline_settings,
    validate_commandline_settings,
)
from comictaggerlib.ctsettings.file import register_file_settings, validate_file_settings
from comictaggerlib.ctsettings.plugin import group_for_plugin, register_plugin_settings, validate_plugin_settings
from comictaggerlib.ctsettings.settngs_namespace import settngs_namespace as ct_ns
from comictaggerlib.ctsettings.types import ComicTaggerPaths
from comictalker import ComicTalker

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
