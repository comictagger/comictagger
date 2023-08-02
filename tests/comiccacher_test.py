from __future__ import annotations

import pytest

import comictalker.comiccacher
from comicapi.genericmetadata import TagOrigin
from testing.comicdata import search_results


def test_create_cache(config, mock_version):
    config, definitions = config
    comictalker.comiccacher.ComicCacher(config.runtime_config.user_cache_dir, mock_version[0])
    assert config.runtime_config.user_cache_dir.exists()


def test_search_results(comic_cache):
    comic_cache.add_search_results(TagOrigin("test", "test"), "test search", search_results)
    assert search_results == comic_cache.get_search_results(TagOrigin("test", "test"), "test search")


@pytest.mark.parametrize("series_info", search_results)
def test_series_info(comic_cache, series_info):
    comic_cache.add_series_info(series=series_info, source=TagOrigin("test", "test"))
    vi = series_info.copy()
    cache_result = comic_cache.get_series_info(series_id=series_info.id, source=TagOrigin("test", "test"))
    assert vi == cache_result
