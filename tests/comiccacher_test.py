from __future__ import annotations

import json

import pytest

import comictalker.comiccacher
from testing.comicdata import search_results


def test_create_cache(config, mock_version):
    config, definitions = config
    comictalker.comiccacher.ComicCacher(config.runtime_config.user_cache_dir, mock_version[0])
    assert config.runtime_config.user_cache_dir.exists()


def test_search_results(comic_cache):
    comic_cache.add_search_results(
        "test",
        "test search",
        [comictalker.comiccacher.Series(id=x["id"], data=json.dumps(x)) for x in search_results],
        True,
    )
    cached_results = [json.loads(x[0].data) for x in comic_cache.get_search_results("test", "test search")]
    assert search_results == cached_results


@pytest.mark.parametrize("series_info", search_results)
def test_series_info(comic_cache, series_info):
    comic_cache.add_series_info(
        series=comictalker.comiccacher.Series(id=series_info["id"], data=json.dumps(series_info)),
        source="test",
        complete=True,
    )
    vi = series_info.copy()
    cache_result = json.loads(comic_cache.get_series_info(series_id=series_info["id"], source="test")[0].data)
    assert vi == cache_result
