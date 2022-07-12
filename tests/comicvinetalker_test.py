from __future__ import annotations

import pytest

import comictaggerlib.comicvinetalker
import testing.comicvine
from testing.comicdata import select_details


def test_fetch_volume_data(comicvine_api, settings, mock_now, comic_cache):
    ct = comictaggerlib.comicvinetalker.ComicVineTalker()
    volume = ct.fetch_volume_data(23437)
    volume["start_year"] = int(volume["start_year"])
    del volume["publisher"]["id"]
    del volume["publisher"]["api_detail_url"]
    assert volume == comic_cache.get_volume_info(23437, ct.source_name)


def test_fetch_issue_data_by_issue_id(comicvine_api, settings, mock_now, mock_version):
    ct = comictaggerlib.comicvinetalker.ComicVineTalker()
    md = ct.fetch_issue_data_by_issue_id(311811, settings)
    assert md == testing.comicvine.cv_md


@pytest.mark.parametrize("details", select_details)
def test_issue_select_details(comic_cache, details):
    ct = comictaggerlib.comicvinetalker.ComicVineTalker()
    ct.cache_issue_select_details(
        issue_id=details["issue_id"],
        image_url=details["image_url"],
        thumb_url=details["thumb_image_url"],
        cover_date=details["cover_date"],
        page_url=details["site_detail_url"],
    )
    det = details.copy()
    del det["issue_id"]
    assert det == comic_cache.get_issue_select_details(details["issue_id"], ct.source_name)
