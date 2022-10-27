from __future__ import annotations

import pytest

import comicapi.genericmetadata
import comictalker.talkers.comicvine
import testing.comicvine


def test_search_for_series(comicvine_api, comic_cache):
    ct = comictalker.talkers.comicvine.ComicVineTalker()
    results = ct.search_for_series("cory doctorows futuristic tales of the here and now")
    cache_issues = comic_cache.get_search_results(ct.source_name, "cory doctorows futuristic tales of the here and now")
    assert results == cache_issues


def test_fetch_volume_data(comicvine_api, comic_cache):
    ct = comictalker.talkers.comicvine.ComicVineTalker()
    result = ct.fetch_partial_volume_data(23437)
    del result["description"]
    del result["image_url"]
    cache_result = comic_cache.get_volume_info(23437, ct.source_name)
    del cache_result["description"]
    del cache_result["image_url"]
    assert result == cache_result


def test_fetch_issues_by_volume(comicvine_api, comic_cache):
    ct = comictalker.talkers.comicvine.ComicVineTalker()
    results = ct.fetch_issues_by_volume(23437)
    cache_issues = comic_cache.get_volume_issues_info(23437, ct.source_name)
    for r in results:
        del r["volume"]
        del r["image_thumb_url"]
    for c in cache_issues:
        del c["volume"]
    assert results == cache_issues


def test_fetch_issue_data_by_issue_id(comicvine_api, settings, mock_now, mock_version):
    ct = comictalker.talkers.comicvine.ComicVineTalker()
    result = ct.fetch_comic_data(issue_id=140529)
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
        del r["image_thumb_url"]
        del r["image_url"]
        del r["alt_images_url"]
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
