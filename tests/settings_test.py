from __future__ import annotations

import argparse
import json

import pytest

import comictaggerlib.settings.manager
from testing.settings import settings_cases


def test_settings_manager():
    manager = comictaggerlib.settings.manager.Manager()
    defaults = manager.defaults()
    assert manager is not None and defaults is not None


@pytest.mark.parametrize("arguments, expected", settings_cases)
def test_setting(arguments, expected):
    assert vars(comictaggerlib.settings.manager.Setting(*arguments[0], **arguments[1])) == expected


def test_add_setting(settings_manager):
    assert settings_manager.add_setting("--test") is None


def test_get_defaults(settings_manager):
    settings_manager.add_setting("--test", default="hello")
    defaults = settings_manager.defaults()
    assert defaults[""]["test"] == "hello"


def test_get_namespace(settings_manager):
    settings_manager.add_setting("--test", default="hello")
    defaults = settings_manager.get_namespace(settings_manager.defaults())
    assert defaults.test == "hello"


def test_get_defaults_group(settings_manager):
    settings_manager.add_group("tst", lambda parser: parser.add_setting("--test", default="hello"))
    defaults = settings_manager.defaults()
    assert defaults["tst"]["test"] == "hello"


def test_get_namespace_group(settings_manager):
    settings_manager.add_group("tst", lambda parser: parser.add_setting("--test", default="hello"))
    defaults = settings_manager.get_namespace(settings_manager.defaults())
    assert defaults.tst_test == "hello"


def test_cmdline_only(settings_manager):
    settings_manager.add_group("tst", lambda parser: parser.add_setting("--test", default="hello", file=False))
    settings_manager.add_group("tst2", lambda parser: parser.add_setting("--test2", default="hello", cmdline=False))

    file_normalized = settings_manager.normalize_options({}, file=True)
    cmdline_normalized = settings_manager.normalize_options({}, cmdline=True)

    assert "test" in cmdline_normalized["tst"]
    assert "test2" not in cmdline_normalized["tst2"]

    assert "test" not in file_normalized["tst"]
    assert "test2" in file_normalized["tst2"]


def test_normalize(settings_manager):
    settings_manager.add_group("tst", lambda parser: parser.add_setting("--test", default="hello"))

    defaults = settings_manager.defaults()
    defaults["test"] = "fail"  # Not defined in settings_manager

    defaults_namespace = settings_manager.get_namespace(defaults)
    defaults_namespace.test = "fail"

    normalized = settings_manager.normalize_options(defaults, file=True)
    normalized_namespace = settings_manager.get_namespace(settings_manager.normalize_options(defaults, file=True))

    assert "test" not in normalized
    assert "tst" in normalized
    assert "test" in normalized["tst"]
    assert normalized["tst"]["test"] == "hello"

    assert not hasattr(normalized_namespace, "test")
    assert hasattr(normalized_namespace, "tst_test")
    assert normalized_namespace.tst_test == "hello"


@pytest.mark.parametrize(
    "raw, raw2, expected",
    [
        ({"tst": {"test": "fail"}}, argparse.Namespace(tst_test="success"), "success"),
        # hello is default so is not used in raw_options_2
        ({"tst": {"test": "success"}}, argparse.Namespace(tst_test="hello"), "success"),
        (argparse.Namespace(tst_test="fail"), {"tst": {"test": "success"}}, "success"),
        (argparse.Namespace(tst_test="success"), {"tst": {"test": "hello"}}, "success"),
    ],
)
def test_normalize_merge(raw, raw2, expected, settings_manager):
    settings_manager.add_group("tst", lambda parser: parser.add_setting("--test", default="hello"))

    normalized = settings_manager.normalize_options(raw, file=True, raw_options_2=raw2)

    assert normalized["tst"]["test"] == expected


def test_cli_set(settings_manager, tmp_path):
    settings_file = tmp_path / "settings.json"
    settings_file.write_text(json.dumps({}))
    settings_manager.add_group("tst", lambda parser: parser.add_setting("--test", default="hello", file=False))

    normalized = settings_manager.parse_options(settings_file, ["--test", "success"])

    assert "test" in normalized["tst"]
    assert normalized["tst"]["test"] == "success"


def test_file_set(settings_manager, tmp_path):
    settings_file = tmp_path / "settings.json"
    settings_file.write_text(
        json.dumps(
            {
                "tst": {"test": "success"},
            }
        )
    )
    settings_manager.add_group("tst", lambda parser: parser.add_setting("--test", default="hello", cmdline=False))

    normalized = settings_manager.parse_options(settings_file, [])

    assert "test" in normalized["tst"]
    assert normalized["tst"]["test"] == "success"


def test_cli_override_file(settings_manager, tmp_path):
    settings_file = tmp_path / "settings.json"
    settings_file.write_text(json.dumps({"tst": {"test": "fail"}}))
    settings_manager.add_group("tst", lambda parser: parser.add_setting("--test", default="hello"))

    normalized = settings_manager.parse_options(settings_file, ["--test", "success"])

    assert "test" in normalized["tst"]
    assert normalized["tst"]["test"] == "success"


def test_cli_explicit_default(settings_manager, tmp_path):
    settings_file = tmp_path / "settings.json"
    settings_file.write_text(json.dumps({"tst": {"test": "fail"}}))
    settings_manager.add_group("tst", lambda parser: parser.add_setting("--test", default="success"))

    normalized = settings_manager.parse_options(settings_file, ["--test", "success"])

    assert "test" in normalized["tst"]
    assert normalized["tst"]["test"] == "success"
