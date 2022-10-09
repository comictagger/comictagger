from __future__ import annotations

import pytest

import comictalker.comiccacher
from testing.comicdata import alt_covers, search_results, select_details


def test_create_cache(settings):
    comictalker.comiccacher.ComicCacher()
    assert (settings.get_settings_folder() / "settings").exists()


def test_search_results(comic_cache):
    comic_cache.add_search_results(
        "test",
        "test search",
        search_results,
    )
    assert search_results == comic_cache.get_search_results("test", "test search")


@pytest.mark.parametrize("alt_cover", alt_covers)
def test_alt_covers(comic_cache, alt_cover):
    comic_cache.add_alt_covers(**alt_cover, source_name="test")
    assert alt_cover["url_list"] == comic_cache.get_alt_covers(issue_id=alt_cover["issue_id"], source_name="test")


@pytest.mark.parametrize("volume_info", search_results)
def test_volume_info(comic_cache, volume_info):
    comic_cache.add_volume_info(volume_record=volume_info, source_name="test")
    vi = volume_info.copy()
    del vi["description"]
    del vi["image"]
    assert vi == comic_cache.get_volume_info(volume_id=volume_info["id"], source_name="test")


@pytest.mark.parametrize("details", select_details)
def test_issue_select_details(comic_cache, details):
    comic_cache.add_issue_select_details(**details, source_name="test")
    det = details.copy()
    del det["issue_id"]
    assert det == comic_cache.get_issue_select_details(details["issue_id"], "test")
