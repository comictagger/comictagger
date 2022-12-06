from __future__ import annotations

import copy
import io
import shutil
import unittest.mock
from collections.abc import Generator
from typing import Any

import pytest
import requests
from PIL import Image

import comicapi.comicarchive
import comicapi.genericmetadata
import comictaggerlib.settings
import comictalker.comiccacher
import comictalker.talkers.comicvine
from comicapi import utils
from comictaggerlib import settings as ctsettings
from testing import comicvine, filenames
from testing.comicdata import all_seed_imprints, seed_imprints


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
    monkeypatch.delattr("requests.sessions.Session.request")


@pytest.fixture
def comicvine_api(
    monkeypatch, cbz, comic_cache, mock_version, settings
) -> comictalker.talkers.comicvine.ComicVineTalker:
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

    cv = comictalker.talkers.comicvine.ComicVineTalker(
        version=mock_version[0],
        cache_folder=settings["runtime"]["config"].user_cache_dir,
        api_url="",
        api_key="",
        series_match_thresh=90,
        remove_html_tables=False,
        use_series_start_as_volume=False,
        wait_on_ratelimit=False,
    )
    return cv


@pytest.fixture
def mock_version(monkeypatch):
    version = "1.4.4a9.dev20"
    version_tuple = (1, 4, 4, "dev20")

    monkeypatch.setattr(comictaggerlib.ctversion, "version", version)
    monkeypatch.setattr(comictaggerlib.ctversion, "__version__", version)
    monkeypatch.setattr(comictaggerlib.ctversion, "version_tuple", version_tuple)
    monkeypatch.setattr(comictaggerlib.ctversion, "__version_tuple__", version_tuple)
    yield (version, version_tuple)


@pytest.fixture
def md():
    yield comicapi.genericmetadata.md_test.copy()


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
def settings(tmp_path):

    manager = ctsettings.Manager()
    ctsettings.register_commandline(manager)
    ctsettings.register_settings(manager)
    defaults = manager.defaults()
    defaults["runtime"]["config"] = ctsettings.ComicTaggerPaths(tmp_path / "config")
    defaults["runtime"]["config"].user_data_dir.mkdir(parents=True, exist_ok=True)
    defaults["runtime"]["config"].user_config_dir.mkdir(parents=True, exist_ok=True)
    defaults["runtime"]["config"].user_cache_dir.mkdir(parents=True, exist_ok=True)
    defaults["runtime"]["config"].user_state_dir.mkdir(parents=True, exist_ok=True)
    defaults["runtime"]["config"].user_log_dir.mkdir(parents=True, exist_ok=True)
    yield defaults


@pytest.fixture
def comic_cache(settings, mock_version) -> Generator[comictalker.comiccacher.ComicCacher, Any, None]:
    yield comictalker.comiccacher.ComicCacher(settings["runtime"]["config"].user_cache_dir, mock_version[0])
