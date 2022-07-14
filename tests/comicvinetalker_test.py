from __future__ import annotations

import pytest

import comicapi.genericmetadata
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


def test_fetch_issues_by_volume(comicvine_api, settings, comic_cache):
    ct = comictaggerlib.comicvinetalker.ComicVineTalker()
    issues = ct.fetch_issues_by_volume(23437)
    cache_issues = comic_cache.get_volume_issues_info(23437, ct.source_name)

    issues[0]["image"] = {"super_url": issues[0]["image"]["super_url"], "thumb_url": issues[0]["image"]["thumb_url"]}
    del issues[0]["volume"]
    assert issues == cache_issues


def test_fetch_issue_data_by_issue_id(comicvine_api, settings, mock_now, mock_version):
    ct = comictaggerlib.comicvinetalker.ComicVineTalker()
    md = ct.fetch_issue_data_by_issue_id(311811, settings)
    assert md == testing.comicvine.cv_md


def test_fetch_issues_by_volume_issue_num_and_year(comicvine_api):
    ct = comictaggerlib.comicvinetalker.ComicVineTalker()
    cv = ct.fetch_issues_by_volume_issue_num_and_year([23437], "3", None)
    cv_expected = testing.comicvine.cv_issue_result["results"].copy()
    testing.comicvine.filter_field_list(
        cv_expected,
        {"params": {"field_list": "id,volume,issue_number,name,image,cover_date,site_detail_url,description"}},
    )
    assert cv[0] == cv_expected


cv_issue = [
    (23437, "3", testing.comicvine.cv_md),
    (23437, "", comicapi.genericmetadata.GenericMetadata()),
    (23437, "0", comicapi.genericmetadata.GenericMetadata()),
]


@pytest.mark.parametrize("volume_id, issue_number, result_md", cv_issue)
def test_fetch_issue_data(comicvine_api, settings, mock_now, mock_version, volume_id, issue_number, result_md):
    ct = comictaggerlib.comicvinetalker.ComicVineTalker()
    md = ct.fetch_issue_data(volume_id, issue_number, settings)
    assert md == result_md


# @pytest.mark.parametrize("volume_id, issue_number, result_md", cv_issue)
def test_fetch_issue_select_details(comicvine_api, settings, mock_now, mock_version):
    ct = comictaggerlib.comicvinetalker.ComicVineTalker()
    md = ct.fetch_issue_select_details(311811)
    res = {
        "cover_date": testing.comicvine.cv_issue_result["results"]["cover_date"],
        "site_detail_url": testing.comicvine.cv_issue_result["results"]["site_detail_url"],
        "image_url": testing.comicvine.cv_issue_result["results"]["image"]["super_url"],
        "thumb_image_url": testing.comicvine.cv_issue_result["results"]["image"]["thumb_url"],
    }
    assert md == res


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
