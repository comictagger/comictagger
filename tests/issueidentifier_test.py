from __future__ import annotations

import pytest

import comicapi.comicarchive
import comicapi.issuestring
import comictaggerlib.issueidentifier
import comictalker.comictalker
import testing.comicdata
import testing.comicvine


def test_crop(cbz_double_cover, settings, tmp_path, comicvine_api):
    ii = comictaggerlib.issueidentifier.IssueIdentifier(cbz_double_cover, settings, comicvine_api)
    cropped = ii.crop_cover(cbz_double_cover.archiver.read_file("double_cover.jpg"))
    original_cover = cbz_double_cover.get_page(0)

    original_hash = ii.calculate_hash(original_cover)
    cropped_hash = ii.calculate_hash(cropped)

    assert original_hash == cropped_hash


@pytest.mark.parametrize("additional_md, expected", testing.comicdata.metadata_keys)
def test_get_search_keys(cbz, settings, additional_md, expected, comicvine_api):
    ii = comictaggerlib.issueidentifier.IssueIdentifier(cbz, settings, comicvine_api)
    ii.set_additional_metadata(additional_md)

    assert expected == ii.get_search_keys()


def test_get_issue_cover_match_score(cbz, settings, comicvine_api):
    ii = comictaggerlib.issueidentifier.IssueIdentifier(cbz, settings, comicvine_api)
    score = ii.get_issue_cover_match_score(
        int(
            comicapi.issuestring.IssueString(
                cbz.read_metadata(comicapi.comicarchive.MetaDataStyle.CIX).issue
            ).as_float()
        ),
        "https://comicvine.gamespot.com/a/uploads/scale_large/0/574/585444-109004_20080707014047_large.jpg",
        "https://comicvine.gamespot.com/a/uploads/scale_avatar/0/574/585444-109004_20080707014047_large.jpg",
        "https://comicvine.gamespot.com/cory-doctorows-futuristic-tales-of-the-here-and-no/4000-140529/",
        [ii.calculate_hash(cbz.get_page(0))],
    )
    expected = {
        "hash": 1747255366011518976,
        "score": 0,
        "url": "https://comicvine.gamespot.com/a/uploads/scale_large/0/574/585444-109004_20080707014047_large.jpg",
    }
    assert expected == score


def test_search(cbz, settings, comicvine_api):
    ii = comictaggerlib.issueidentifier.IssueIdentifier(cbz, settings, comictalker.comictalker.ComicTalker("comicvine"))
    results = ii.search()
    cv_expected = {
        "series": f"{testing.comicvine.cv_volume_result['results']['name']} ({testing.comicvine.cv_volume_result['results']['start_year']})",
        "distance": 0,
        "issue_number": testing.comicvine.cv_issue_result["results"]["issue_number"],
        "cv_issue_count": testing.comicvine.cv_volume_result["results"]["count_of_issues"],
        "issue_title": testing.comicvine.cv_issue_result["results"]["name"],
        "issue_id": testing.comicvine.cv_issue_result["results"]["id"],
        "volume_id": testing.comicvine.cv_volume_result["results"]["id"],
        "month": testing.comicvine.date[1],
        "year": testing.comicvine.date[2],
        "publisher": testing.comicvine.cv_volume_result["results"]["publisher"]["name"],
        "image_url": testing.comicvine.cv_issue_result["results"]["image"]["super_url"],
        "thumb_url": testing.comicvine.cv_issue_result["results"]["image"]["thumb_url"],
        "page_url": testing.comicvine.cv_issue_result["results"]["site_detail_url"],
        "description": testing.comicvine.cv_issue_result["results"]["description"],
    }
    for r, e in zip(results, [cv_expected]):
        del r["url_image_hash"]
        assert r == e
