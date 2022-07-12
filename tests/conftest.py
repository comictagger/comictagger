from __future__ import annotations

import dataclasses
import datetime
import unittest.mock
from typing import Any, Generator

import pytest
import requests

import comicapi.genericmetadata
import comictaggerlib.comiccacher
import comictaggerlib.comicvinetalker
import comictaggerlib.settings
from comicapi import utils
from testing import comicvine
from testing.comicdata import all_seed_imprints, seed_imprints


@pytest.fixture(autouse=True)
def no_requests(monkeypatch) -> None:
    """Remove requests.sessions.Session.request for all tests."""
    monkeypatch.delattr("requests.sessions.Session.request")


@pytest.fixture
def comicvine_api(monkeypatch) -> unittest.mock.Mock:
    # Any arguments may be passed and mock_get() will always return our
    # mocked object, which only has the .json() method or None for invalid urls.

    def mock_get(*args, **kwargs):

        if args:
            if args[0].startswith("https://comicvine.gamespot.com/api/volume/4050-23437"):
                return comicvine.MockResponse(comicvine.cv_volume_result)
            if args[0].startswith("https://comicvine.gamespot.com/api/issue/4000-311811"):
                return comicvine.MockResponse(comicvine.cv_issue_result)
        return comicvine.MockResponse({})

    m_get = unittest.mock.Mock(side_effect=mock_get)

    # apply the monkeypatch for requests.get to mock_get
    monkeypatch.setattr(requests, "get", m_get)
    return m_get


@pytest.fixture
def mock_now(monkeypatch):
    class mydatetime:
        time = datetime.datetime(2022, 7, 11, 17, 42, 41)

        @classmethod
        def now(cls):
            return cls.time

    monkeypatch.setattr(comictaggerlib.comicvinetalker, "datetime", mydatetime)


@pytest.fixture
def md():
    yield dataclasses.replace(comicapi.genericmetadata.md_test)


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
    yield comictaggerlib.settings.ComicTaggerSettings(tmp_path / "settings")


@pytest.fixture
def comic_cache(settings) -> Generator[comictaggerlib.comiccacher.ComicCacher, Any, None]:
    yield comictaggerlib.comiccacher.ComicCacher()
