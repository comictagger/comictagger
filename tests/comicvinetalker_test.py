from __future__ import annotations

import pytest

import comicapi.genericmetadata
import comictalker.talkers.comicvine
import testing.comicvine
from testing.comicdata import select_details


def test_search_for_series(comicvine_api, comic_cache):
    ct = comictalker.talkers.comicvine.ComicVineTalker()
    results = ct.search_for_series("cory doctorows futuristic tales of the here and now")
    cache_issues = comic_cache.get_search_results(ct.source_name, "cory doctorows futuristic tales of the here and now")
    assert results == cache_issues


def test_fetch_volume_data(comicvine_api, comic_cache):
    ct = comictalker.talkers.comicvine.ComicVineTalker()
    result = ct.fetch_partial_volume_data(23437)
    del result["description"]
    del result["image"]
    assert result == comic_cache.get_volume_info(23437, ct.source_name)


def test_fetch_issues_by_volume(comicvine_api, comic_cache):
    ct = comictalker.talkers.comicvine.ComicVineTalker()
    results = ct.fetch_issues_by_volume(23437)
    cache_issues = comic_cache.get_volume_issues_info(23437, ct.source_name)
    for r in results:
        del r["volume"]
        del r["image_thumb"]
    for c in cache_issues:
        del c["volume"]
    assert results == cache_issues


def test_fetch_issue_data_by_issue_id(comicvine_api, settings, mock_now, mock_version):
    ct = comictalker.talkers.comicvine.ComicVineTalker()
    result = ct.fetch_issue_data_by_issue_id(140529)
    assert result == testing.comicvine.cv_md


def test_fetch_issues_by_volume_issue_num_and_year(comicvine_api):
    ct = comictalker.talkers.comicvine.ComicVineTalker()
    results = ct.fetch_issues_by_volume_issue_num_and_year([23437], "1", None)
    cv_expected = testing.comicvine.comic_issue_result.copy()
    testing.comicvine.filter_field_list(
        cv_expected,
        {"params": {"field_list": "id,volume,issue_number,name,image,cover_date,site_detail_url,description,aliases"}},
    )
    for r, e in zip(results, [cv_expected]):
        del r["image_thumb"]
        assert r == e


cv_issue = [
    (23437, "", testing.comicvine.cv_md),
    (23437, "1", testing.comicvine.cv_md),
    (23437, "0", comicapi.genericmetadata.GenericMetadata()),
]


@pytest.mark.parametrize("volume_id, issue_number, expected", cv_issue)
def test_fetch_issue_data(comicvine_api, settings, mock_now, mock_version, volume_id, issue_number, expected):
    ct = comictalker.talkers.comicvine.ComicVineTalker()
    results = ct.fetch_issue_data(volume_id, issue_number)
    assert results == expected


def test_fetch_issue_select_details(comicvine_api, mock_now, mock_version):
    ct = comictalker.talkers.comicvine.ComicVineTalker()
    result = ct.fetch_issue_select_details(140529)
    expected = {
        "cover_date": testing.comicvine.cv_issue_result["results"]["cover_date"],
        "site_detail_url": testing.comicvine.cv_issue_result["results"]["site_detail_url"],
        "image_url": testing.comicvine.cv_issue_result["results"]["image"]["super_url"],
        "thumb_image_url": testing.comicvine.cv_issue_result["results"]["image"]["thumb_url"],
    }
    assert result == expected


@pytest.mark.parametrize("details", select_details)
def test_issue_select_details(comic_cache, details):
    expected = details.copy()
    del expected["issue_id"]

    ct = comictalker.talkers.comicvine.ComicVineTalker()
    ct.cache_issue_select_details(
        issue_id=details["issue_id"],
        image_url=details["image_url"],
        thumb_url=details["thumb_image_url"],
        cover_date=details["cover_date"],
        page_url=details["site_detail_url"],
    )
    result = comic_cache.get_issue_select_details(details["issue_id"], ct.source_name)

    assert result == expected
