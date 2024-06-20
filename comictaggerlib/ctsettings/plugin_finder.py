"""Functions related to finding and loading plugins."""

# Lifted from flake8 https://github.com/PyCQA/flake8/blob/main/src/flake8/plugins/finder.py#L127

from __future__ import annotations

import configparser
import importlib.metadata
import logging
import pathlib
import re
from collections.abc import Generator
from typing import Any, NamedTuple

logger = logging.getLogger(__name__)

NORMALIZE_PACKAGE_NAME_RE = re.compile(r"[-_.]+")
PLUGIN_GROUPS = frozenset(("comictagger.talker", "comicapi.archiver", "comicapi.tags"))


class FailedToLoadPlugin(Exception):
    """Exception raised when a plugin fails to load."""

    FORMAT = 'ComicTagger failed to load local plugin "{name}" due to {exc}.'

    def __init__(self, plugin_name: str, exception: Exception) -> None:
        """Initialize our FailedToLoadPlugin exception."""
        self.plugin_name = plugin_name
        self.original_exception = exception
        super().__init__(plugin_name, exception)

    def __str__(self) -> str:
        """Format our exception message."""
        return self.FORMAT.format(
            name=self.plugin_name,
            exc=self.original_exception,
        )


def normalize_pypi_name(s: str) -> str:
    """Normalize a distribution name according to PEP 503."""
    return NORMALIZE_PACKAGE_NAME_RE.sub("-", s).lower()


class Plugin(NamedTuple):
    """A plugin before loading."""

    package: str
    version: str
    entry_point: importlib.metadata.EntryPoint
    path: pathlib.Path


class LoadedPlugin(NamedTuple):
    """Represents a plugin after being imported."""

    plugin: Plugin
    obj: Any

    @property
    def entry_name(self) -> str:
        """Return the name given in the packaging metadata."""
        return self.plugin.entry_point.name

    @property
    def display_name(self) -> str:
        """Return the name for use in user-facing / error messages."""
        return f"{self.plugin.package}[{self.entry_name}]"


class Plugins(NamedTuple):
    """Classified plugins."""

    archivers: list[Plugin]
    tags: list[Plugin]
    talkers: list[Plugin]

    def all_plugins(self) -> Generator[Plugin, None, None]:
        """Return an iterator over all :class:`LoadedPlugin`s."""
        yield from self.archivers
        yield from self.tags
        yield from self.talkers

    def versions_str(self) -> str:
        """Return a user-displayed list of plugin versions."""
        return ", ".join(sorted({f"{plugin.package}: {plugin.version}" for plugin in self.all_plugins()}))


def _find_local_plugins(plugin_path: pathlib.Path) -> Generator[Plugin, None, None]:

    cfg = configparser.ConfigParser(interpolation=None)
    cfg.read(plugin_path / "setup.cfg")

    for group in PLUGIN_GROUPS:
        for plugin_s in cfg.get("options.entry_points", group, fallback="").splitlines():
            if not plugin_s:
                continue

            name, _, entry_str = plugin_s.partition("=")
            name, entry_str = name.strip(), entry_str.strip()
            ep = importlib.metadata.EntryPoint(name, entry_str, group)
            yield Plugin(plugin_path.name, cfg.get("metadata", "version", fallback="0.0.1"), ep, plugin_path)


def _check_required_plugins(plugins: list[Plugin], expected: frozenset[str]) -> None:
    plugin_names = {normalize_pypi_name(plugin.package) for plugin in plugins}
    expected_names = {normalize_pypi_name(name) for name in expected}
    missing_plugins = expected_names - plugin_names

    if missing_plugins:
        raise Exception(
            "required plugins were not installed!\n"
            + f"- installed: {', '.join(sorted(plugin_names))}\n"
            + f"- expected: {', '.join(sorted(expected_names))}\n"
            + f"- missing: {', '.join(sorted(missing_plugins))}"
        )


def find_plugins(plugin_folder: pathlib.Path) -> Plugins:
    """Discovers all plugins (but does not load them)."""
    ret: list[Plugin] = []
    for plugin_path in plugin_folder.glob("*/setup.cfg"):
        try:
            ret.extend(_find_local_plugins(plugin_path.parent))
        except Exception as err:
            FailedToLoadPlugin(plugin_path.parent.name, err)

    # for determinism, sort the list
    ret.sort()

    return _classify_plugins(ret)


def _classify_plugins(plugins: list[Plugin]) -> Plugins:
    archivers = []
    tags = []
    talkers = []

    for p in plugins:
        if p.entry_point.group == "comictagger.talker":
            talkers.append(p)
        elif p.entry_point.group == "comicapi.tags":
            tags.append(p)
        elif p.entry_point.group == "comicapi.archiver":
            archivers.append(p)
        else:
            logger.warning(NotImplementedError(f"what plugin type? {p}"))

    return Plugins(
        tags=tags,
        archivers=archivers,
        talkers=talkers,
    )
