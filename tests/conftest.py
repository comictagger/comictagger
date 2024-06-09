from __future__ import annotations

import copy
import datetime
import io
import shutil
import unittest.mock
from argparse import Namespace
from collections.abc import Generator
from typing import Any

import pytest
import settngs
from PIL import Image
from pyrate_limiter import Limiter, RequestRate

import comicapi.comicarchive
import comicapi.genericmetadata
import comictaggerlib.cli
import comictaggerlib.ctsettings
import comictalker
import comictalker.comiccacher
import comictalker.talkers.comicvine
from comicapi import utils
from testing import comicvine, filenames
from testing.comicdata import all_seed_imprints, seed_imprints

try:
    import niquests as requests
except ImportError:
    import requests


@pytest.fixture
def cbz():
    yield comicapi.comicarchive.ComicArchive(filenames.cbz_path)


@pytest.fixture
def tmp_comic(tmp_path):
    shutil.copy(filenames.cbz_path, tmp_path)
    yield comicapi.comicarchive.ComicArchive(tmp_path / filenames.cbz_path.name)


@pytest.fixture
def cbz_double_cover(tmp_path, tmp_comic):
    cover = Image.open(io.BytesIO(tmp_comic.get_page(0)))

    other_page = Image.open(io.BytesIO(tmp_comic.get_page(tmp_comic.get_number_of_pages() - 1)))

    double_cover = Image.new("RGB", (cover.width * 2, cover.height))
    double_cover.paste(other_page, (0, 0))
    double_cover.paste(cover, (cover.width, 0))

    tmp_comic.archiver.write_file("double_cover.jpg", double_cover.tobytes("jpeg", "RGB"))
    yield tmp_comic


@pytest.fixture(autouse=True)
def no_requests(monkeypatch) -> None:
    """Remove requests.sessions.Session.request for all tests."""
    try:
        monkeypatch.delattr("niquests.sessions.Session.request")
    except Exception:
        ...
    try:
        monkeypatch.delattr("requests.sessions.Session.request")
    except Exception:
        ...


@pytest.fixture
def comicvine_api(monkeypatch, cbz, comic_cache, mock_version, config) -> comictalker.talkers.comicvine.ComicVineTalker:
    # Any arguments may be passed and mock_get() will always return our
    # mocked object, which only has the .json() method or None for invalid urls.

    def make_list(cv_result):
        cv_list = copy.deepcopy(cv_result)
        if isinstance(cv_list["results"], dict):
            cv_list["results"] = [cv_list["results"]]
        return cv_list

    def mock_get(*args, **kwargs):
        if args:
            if args[0].startswith("https://comicvine.gamespot.com/api/volume/4050-23437"):
                cv_result = copy.deepcopy(comicvine.cv_volume_result)
                comicvine.filter_field_list(cv_result["results"], kwargs)
                return comicvine.MockResponse(cv_result)
            if args[0].startswith("https://comicvine.gamespot.com/api/issue/4000-140529"):
                return comicvine.MockResponse(comicvine.cv_issue_result)
            if (
                args[0].startswith("https://comicvine.gamespot.com/api/issues/")
                and "params" in kwargs
                and "filter" in kwargs["params"]
                and "23437" in kwargs["params"]["filter"]
            ):
                cv_list = make_list(comicvine.cv_issue_result)
                for cv in cv_list["results"]:
                    comicvine.filter_field_list(cv, kwargs)
                return comicvine.MockResponse(cv_list)
            if (
                args[0].startswith("https://comicvine.gamespot.com/api/search")
                and "params" in kwargs
                and "resources" in kwargs["params"]
                and "volume" == kwargs["params"]["resources"]
            ):
                cv_list = make_list(comicvine.cv_volume_result)
                for cv in cv_list["results"]:
                    comicvine.filter_field_list(cv, kwargs)
                return comicvine.MockResponse(cv_list)
            if (
                args[0]
                == "https://comicvine.gamespot.com/a/uploads/scale_large/0/574/585444-109004_20080707014047_large.jpg"
            ):
                return comicvine.MockResponse({}, cbz.get_page(0))
            if (
                args[0]
                == "https://comicvine.gamespot.com/a/uploads/scale_avatar/0/574/585444-109004_20080707014047_large.jpg"
            ):
                thumb = Image.open(io.BytesIO(cbz.get_page(0)))
                thumb.resize((105, 160), Image.Resampling.LANCZOS)
                return comicvine.MockResponse({}, thumb.tobytes("jpeg", "RGB"))
        return comicvine.MockResponse(comicvine.cv_not_found)

    m_get = unittest.mock.Mock(side_effect=mock_get)

    # apply the monkeypatch for requests.get to mock_get
    monkeypatch.setattr(requests, "get", m_get)
    monkeypatch.setattr(comictalker.talkers.comicvine, "custom_limiter", Limiter(RequestRate(100, 1)))
    monkeypatch.setattr(comictalker.talkers.comicvine, "default_limiter", Limiter(RequestRate(100, 1)))

    cv = comictalker.talkers.comicvine.ComicVineTalker(
        version=mock_version[0],
        cache_folder=config[0].Runtime_Options__config.user_cache_dir,
    )
    manager = settngs.Manager()
    manager.add_persistent_group("comicvine", cv.register_settings)
    cfg, _ = manager.defaults()
    cfg["comicvine"]["comicvine_key"] = "testing"
    cv.parse_settings(cfg["comicvine"])
    return cv


@pytest.fixture
def mock_now(monkeypatch):
    class mydatetime:
        time = datetime.datetime(2022, 4, 16, 15, 52, 26)

        @classmethod
        def now(cls):
            return cls.time

    monkeypatch.setattr(comictaggerlib.md, "datetime", mydatetime)


@pytest.fixture
def mock_version(monkeypatch):
    version = "1.3.2a5"
    version_tuple = (1, 3, 2)

    monkeypatch.setattr(comictaggerlib.ctversion, "version", version)
    monkeypatch.setattr(comictaggerlib.ctversion, "__version__", version)
    monkeypatch.setattr(comictaggerlib.ctversion, "version_tuple", version_tuple)
    monkeypatch.setattr(comictaggerlib.ctversion, "__version_tuple__", version_tuple)
    yield version, version_tuple


@pytest.fixture
def md():
    yield comicapi.genericmetadata.md_test.copy()


@pytest.fixture
def md_saved():
    yield comicapi.genericmetadata.md_test.replace(tag_origin=None, issue_id=None, series_id=None)


# manually seeds publishers
@pytest.fixture
def seed_publishers(monkeypatch):
    publisher_seed = {}
    for publisher, imprint in seed_imprints.items():
        publisher_seed[publisher] = imprint
    monkeypatch.setattr(utils, "publishers", publisher_seed)


@pytest.fixture
def seed_all_publishers(monkeypatch):
    publisher_seed = {}
    for publisher, imprint in all_seed_imprints.items():
        publisher_seed[publisher] = imprint
    monkeypatch.setattr(utils, "publishers", publisher_seed)


@pytest.fixture
def config(tmp_path):
    from comictaggerlib.main import App

    app = App()
    app.register_settings()

    defaults = app.parse_settings(comictaggerlib.ctsettings.ComicTaggerPaths(tmp_path / "config"), "")
    defaults[0].Runtime_Options__config.user_config_dir.mkdir(parents=True, exist_ok=True)
    defaults[0].Runtime_Options__config.user_cache_dir.mkdir(parents=True, exist_ok=True)
    defaults[0].Runtime_Options__config.user_log_dir.mkdir(parents=True, exist_ok=True)
    defaults[0].Runtime_Options__config.user_plugin_dir.mkdir(parents=True, exist_ok=True)
    yield defaults


@pytest.fixture
def plugin_config(tmp_path):
    from comictaggerlib.main import App

    ns = Namespace(config=comictaggerlib.ctsettings.ComicTaggerPaths(tmp_path / "config"))
    app = App()
    app.load_plugins(ns)
    app.register_settings()

    defaults = app.parse_settings(ns.config, "")
    defaults[0].Runtime_Options__config.user_config_dir.mkdir(parents=True, exist_ok=True)
    defaults[0].Runtime_Options__config.user_cache_dir.mkdir(parents=True, exist_ok=True)
    defaults[0].Runtime_Options__config.user_log_dir.mkdir(parents=True, exist_ok=True)
    defaults[0].Runtime_Options__config.user_plugin_dir.mkdir(parents=True, exist_ok=True)
    yield (defaults, app.talkers)


@pytest.fixture
def comic_cache(config, mock_version) -> Generator[comictalker.comiccacher.ComicCacher, Any, None]:
    yield comictalker.comiccacher.ComicCacher(config[0].Runtime_Options__config.user_cache_dir, mock_version[0])
