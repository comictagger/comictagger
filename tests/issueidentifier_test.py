from __future__ import annotations

import io

import pytest
from PIL import Image

import comictaggerlib.imagehasher
import comictaggerlib.issueidentifier
import testing.comicdata
import testing.comicvine
from comictaggerlib.resulttypes import IssueResult


def test_crop(cbz_double_cover, config, tmp_path, comicvine_api):
    config, definitions = config

    ii = comictaggerlib.issueidentifier.IssueIdentifier(cbz_double_cover, config, comicvine_api)

    im = Image.open(io.BytesIO(cbz_double_cover.archiver.read_file("double_cover.jpg")))

    cropped = ii._crop_double_page(im)
    original = cbz_double_cover.get_page(0)

    original_hash = comictaggerlib.imagehasher.ImageHasher(data=original).average_hash()
    cropped_hash = comictaggerlib.imagehasher.ImageHasher(image=cropped).average_hash()

    assert original_hash == cropped_hash


@pytest.mark.parametrize("additional_md, expected", testing.comicdata.metadata_keys)
def test_get_search_keys(cbz, config, additional_md, expected, comicvine_api):
    config, definitions = config
    ii = comictaggerlib.issueidentifier.IssueIdentifier(cbz, config, comicvine_api)

    assert expected == ii._get_search_keys(additional_md)


def test_get_issue_cover_match_score(cbz, config, comicvine_api):
    config, definitions = config
    ii = comictaggerlib.issueidentifier.IssueIdentifier(cbz, config, comicvine_api)
    score = ii._get_issue_cover_match_score(
        "https://comicvine.gamespot.com/a/uploads/scale_large/0/574/585444-109004_20080707014047_large.jpg",
        ["https://comicvine.gamespot.com/cory-doctorows-futuristic-tales-of-the-here-and-no/4000-140529/"],
        [("Cover 1", ii.calculate_hash(cbz.get_page(0)))],
    )
    expected = {
        "remote_hash": 212201432349720,
        "score": 0,
        "url": "https://comicvine.gamespot.com/a/uploads/scale_large/0/574/585444-109004_20080707014047_large.jpg",
        "local_hash": 212201432349720,
        "local_hash_name": "Cover 1",
    }
    assert expected == score


def test_search(cbz, config, comicvine_api):
    config, definitions = config
    ii = comictaggerlib.issueidentifier.IssueIdentifier(cbz, config, comicvine_api)
    result, issues = ii.identify(cbz, cbz.read_metadata("cr"))
    cv_expected = IssueResult(
        series=f"{testing.comicvine.cv_volume_result['results']['name']} ({testing.comicvine.cv_volume_result['results']['start_year']})",
        distance=0,
        issue_number=testing.comicvine.cv_issue_result["results"]["issue_number"],
        alt_image_urls=[],
        issue_count=testing.comicvine.cv_volume_result["results"]["count_of_issues"],
        issue_title=testing.comicvine.cv_issue_result["results"]["name"],
        issue_id=str(testing.comicvine.cv_issue_result["results"]["id"]),
        series_id=str(testing.comicvine.cv_volume_result["results"]["id"]),
        month=testing.comicvine.date[1],
        year=testing.comicvine.date[2],
        publisher=testing.comicvine.cv_volume_result["results"]["publisher"]["name"],
        image_url=testing.comicvine.cv_issue_result["results"]["image"]["super_url"],
        description=testing.comicvine.cv_issue_result["results"]["description"],
        url_image_hash=212201432349720,
    )
    for r, e in zip(issues, [cv_expected]):
        assert r == e


def test_crop_border(cbz, config, comicvine_api):
    config, definitions = config
    ii = comictaggerlib.issueidentifier.IssueIdentifier(cbz, config, comicvine_api)

    # This creates a white square centered on a black background
    bg = Image.new("RGBA", (100, 100), (0, 0, 0, 255))
    fg = Image.new("RGBA", (50, 50), (255, 255, 255, 255))
    bg.paste(fg, (bg.width // 2 - (fg.width // 2), bg.height // 2 - (fg.height // 2)))

    cropped = ii._crop_border(bg, 49)

    assert cropped
    assert cropped.width == fg.width
    assert cropped.height == fg.height
    assert list(cropped.getdata()) == list(fg.getdata())
