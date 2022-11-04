from __future__ import annotations

import pytest

import comicapi.genericmetadata
import comictaggerlib.comicvinetalker
import testing.comicvine
from testing.comicdata import select_details


def test_search_for_series(comicvine_api, comic_cache):
    ct = comictaggerlib.comicvinetalker.ComicVineTalker()
    results = ct.search_for_series("cory doctorows futuristic tales of the here and now")
    for r in results:
        r["image"] = {"super_url": r["image"]["super_url"]}
        r["start_year"] = int(r["start_year"])
        del r["publisher"]["id"]
        del r["publisher"]["api_detail_url"]
    cache_issues = comic_cache.get_search_results(ct.source_name, "cory doctorows futuristic tales of the here and now")
    assert results == cache_issues


def test_fetch_volume_data(comicvine_api, comic_cache):
    ct = comictaggerlib.comicvinetalker.ComicVineTalker()
    result = ct.fetch_volume_data(23437)
    result["start_year"] = int(result["start_year"])
    del result["publisher"]["id"]
    del result["publisher"]["api_detail_url"]
    assert result == comic_cache.get_volume_info(23437, ct.source_name)


def test_fetch_issues_by_volume(comicvine_api, comic_cache):
    ct = comictaggerlib.comicvinetalker.ComicVineTalker()
    results = ct.fetch_issues_by_volume(23437)
    cache_issues = comic_cache.get_volume_issues_info(23437, ct.source_name)
    for r in results:
        r["image"] = {"super_url": r["image"]["super_url"], "thumb_url": r["image"]["thumb_url"]}
        del r["volume"]
    assert results == cache_issues


def test_fetch_issue_data_by_issue_id(comicvine_api, settings, mock_version):
    ct = comictaggerlib.comicvinetalker.ComicVineTalker()
    result = ct.fetch_issue_data_by_issue_id(140529, settings)
    assert result == testing.comicvine.cv_md


def test_fetch_issues_by_volume_issue_num_and_year(comicvine_api):
    ct = comictaggerlib.comicvinetalker.ComicVineTalker()
    results = ct.fetch_issues_by_volume_issue_num_and_year([23437], "1", None)
    cv_expected = testing.comicvine.cv_issue_result["results"].copy()
    testing.comicvine.filter_field_list(
        cv_expected,
        {"params": {"field_list": "id,volume,issue_number,name,image,cover_date,site_detail_url,description,aliases"}},
    )
    for r, e in zip(results, [cv_expected]):
        assert r == e


cv_issue = [
    (23437, "", testing.comicvine.cv_md),
    (23437, "1", testing.comicvine.cv_md),
    (23437, "0", comicapi.genericmetadata.GenericMetadata()),
]


@pytest.mark.parametrize("volume_id, issue_number, expected", cv_issue)
def test_fetch_issue_data(comicvine_api, settings, mock_version, volume_id, issue_number, expected):
    ct = comictaggerlib.comicvinetalker.ComicVineTalker()
    results = ct.fetch_issue_data(volume_id, issue_number, settings)
    assert results == expected


def test_fetch_issue_select_details(comicvine_api, mock_version):
    ct = comictaggerlib.comicvinetalker.ComicVineTalker()
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

    ct = comictaggerlib.comicvinetalker.ComicVineTalker()
    ct.cache_issue_select_details(
        issue_id=details["issue_id"],
        image_url=details["image_url"],
        thumb_url=details["thumb_image_url"],
        cover_date=details["cover_date"],
        page_url=details["site_detail_url"],
    )
    result = comic_cache.get_issue_select_details(details["issue_id"], ct.source_name)

    assert result == expected
