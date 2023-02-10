from __future__ import annotations

import io

import pytest
from PIL import Image

import comicapi.comicarchive
import comicapi.issuestring
import comictaggerlib.issueidentifier
import testing.comicdata
import testing.comicvine


def test_crop(cbz_double_cover, config, tmp_path, comicvine_api):
    config, definitions = config
    ii = comictaggerlib.issueidentifier.IssueIdentifier(cbz_double_cover, config, comicvine_api)
    cropped = ii.crop_cover(cbz_double_cover.archiver.read_file("double_cover.jpg"))
    original_cover = cbz_double_cover.get_page(0)

    original_hash = ii.calculate_hash(original_cover)
    cropped_hash = ii.calculate_hash(cropped)

    assert original_hash == cropped_hash


@pytest.mark.parametrize("additional_md, expected", testing.comicdata.metadata_keys)
def test_get_search_keys(cbz, config, additional_md, expected, comicvine_api):
    config, definitions = config
    ii = comictaggerlib.issueidentifier.IssueIdentifier(cbz, config, comicvine_api)
    ii.set_additional_metadata(additional_md)

    assert expected == ii.get_search_keys()


def test_get_issue_cover_match_score(cbz, config, comicvine_api):
    config, definitions = config
    ii = comictaggerlib.issueidentifier.IssueIdentifier(cbz, config, comicvine_api)
    score = ii.get_issue_cover_match_score(
        int(
            comicapi.issuestring.IssueString(
                cbz.read_metadata(comicapi.comicarchive.MetaDataStyle.CIX).issue
            ).as_float()
        ),
        "https://comicvine.gamespot.com/a/uploads/scale_large/0/574/585444-109004_20080707014047_large.jpg",
        "https://comicvine.gamespot.com/cory-doctorows-futuristic-tales-of-the-here-and-no/4000-140529/",
        [ii.calculate_hash(cbz.get_page(0))],
    )
    expected = {
        "hash": 1747255366011518976,
        "score": 0,
        "url": "https://comicvine.gamespot.com/a/uploads/scale_large/0/574/585444-109004_20080707014047_large.jpg",
    }
    assert expected == score


def test_search(cbz, config, comicvine_api):
    config, definitions = config
    ii = comictaggerlib.issueidentifier.IssueIdentifier(cbz, config, comicvine_api)
    results = ii.search()
    cv_expected = {
        "series": f"{testing.comicvine.cv_volume_result['results']['name']} ({testing.comicvine.cv_volume_result['results']['start_year']})",
        "distance": 0,
        "issue_number": testing.comicvine.cv_issue_result["results"]["issue_number"],
        "alt_image_urls": [],
        "cv_issue_count": testing.comicvine.cv_volume_result["results"]["count_of_issues"],
        "issue_title": testing.comicvine.cv_issue_result["results"]["name"],
        "issue_id": str(testing.comicvine.cv_issue_result["results"]["id"]),
        "series_id": str(testing.comicvine.cv_volume_result["results"]["id"]),
        "month": testing.comicvine.date[1],
        "year": testing.comicvine.date[2],
        "publisher": testing.comicvine.cv_volume_result["results"]["publisher"]["name"],
        "image_url": testing.comicvine.cv_issue_result["results"]["image"]["super_url"],
        "description": testing.comicvine.cv_issue_result["results"]["description"],
    }
    for r, e in zip(results, [cv_expected]):
        del r["url_image_hash"]
        assert r == e


def test_crop_border(cbz, config, comicvine_api):
    config, definitions = config
    ii = comictaggerlib.issueidentifier.IssueIdentifier(cbz, config, comicvine_api)

    # This creates a white square centered on a black background
    bg = Image.new("RGBA", (100, 100), (0, 0, 0, 255))
    fg = Image.new("RGBA", (50, 50), (255, 255, 255, 255))
    bg.paste(fg, (bg.width // 2 - (fg.width // 2), bg.height // 2 - (fg.height // 2)))
    output = io.BytesIO()
    bg.save(output, format="PNG")
    image_data = output.getvalue()
    output.close()

    cropped = ii.crop_border(image_data, 49)

    im = Image.open(io.BytesIO(cropped))
    assert im.width == fg.width
    assert im.height == fg.height
    assert list(im.getdata()) == list(fg.getdata())
