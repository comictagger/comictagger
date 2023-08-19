from __future__ import annotations

import json

import pytest

import comicapi.genericmetadata
import testing.comicvine


def test_search_for_series(comicvine_api, comic_cache):
    results = comicvine_api.search_for_series("cory doctorows futuristic tales of the here and now")[0]
    cache_series = comic_cache.get_search_results(
        comicvine_api.id, "cory doctorows futuristic tales of the here and now"
    )[0][0]
    series_results = comicvine_api._format_series(json.loads(cache_series.data))
    assert results == series_results


def test_fetch_series(comicvine_api, comic_cache):
    result = comicvine_api.fetch_series(23437)
    cache_series = comic_cache.get_series_info(23437, comicvine_api.id)[0]
    series_result = comicvine_api._format_series(json.loads(cache_series.data))
    assert result == series_result


def test_fetch_issues_in_series(comicvine_api, comic_cache):
    results = comicvine_api.fetch_issues_in_series(23437)
    cache_issues = comic_cache.get_series_issues_info(23437, comicvine_api.id)
    issues_results = [
        comicvine_api._map_comic_issue_to_metadata(
            json.loads(x[0].data),
            comicvine_api._format_series(
                json.loads(comic_cache.get_series_info(x[0].series_id, comicvine_api.id)[0].data)
            ),
        )
        for x in cache_issues
    ]
    assert results == issues_results


def test_fetch_issue_data_by_issue_id(comicvine_api):
    result = comicvine_api.fetch_comic_data(140529)
    result.notes = None
    assert result == testing.comicvine.cv_md


def test_fetch_issues_in_series_issue_num_and_year(comicvine_api):
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
    results = comicvine_api._fetch_issue_data(series_id, issue_number)
    results.notes = None
    assert results == expected
