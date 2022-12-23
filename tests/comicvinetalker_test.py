from __future__ import annotations

import dataclasses

import pytest

import comicapi.genericmetadata
import testing.comicvine


def test_search_for_series(comicvine_api, comic_cache):
    results = comicvine_api.search_for_series("cory doctorows futuristic tales of the here and now")
    cache_issues = comic_cache.get_search_results(
        comicvine_api.source_name, "cory doctorows futuristic tales of the here and now"
    )
    assert results == cache_issues


def test_fetch_series_data(comicvine_api, comic_cache):
    result = comicvine_api.fetch_series_data(23437)
    # del result["description"]
    # del result["image_url"]
    cache_result = comic_cache.get_series_info(23437, comicvine_api.source_name)
    # del cache_result["description"]
    # del cache_result["image_url"]
    assert result == cache_result


def test_fetch_issues_by_series(comicvine_api, comic_cache):
    results = comicvine_api.fetch_issues_by_series(23437)
    cache_issues = comic_cache.get_series_issues_info(23437, comicvine_api.source_name)
    assert dataclasses.asdict(results[0])["series"] == dataclasses.asdict(cache_issues[0])["series"]


def test_fetch_issue_data_by_issue_id(comicvine_api):
    result = comicvine_api.fetch_comic_data(140529)
    result.notes = None
    assert result == testing.comicvine.cv_md


def test_fetch_issues_by_series_issue_num_and_year(comicvine_api):
    results = comicvine_api.fetch_issues_by_series_issue_num_and_year([23437], "1", None)
    cv_expected = testing.comicvine.comic_issue_result.copy()

    for r, e in zip(results, [cv_expected]):
        assert r.series == e.series
        assert r == e


cv_issue = [
    (23437, "", testing.comicvine.cv_md),
    (23437, "1", testing.comicvine.cv_md),
    (23437, "0", comicapi.genericmetadata.GenericMetadata()),
]


@pytest.mark.parametrize("series_id, issue_number, expected", cv_issue)
def test_fetch_issue_data(comicvine_api, series_id, issue_number, expected):
    results = comicvine_api.fetch_issue_data(series_id, issue_number)
    results.notes = None
    assert results == expected
