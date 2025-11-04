from __future__ import annotations

import io

import pytest
from PIL import Image

import comicapi.comicarchive
import comicapi.genericmetadata
import comicapi.utils
import comictaggerlib.imagehasher
import comictaggerlib.issueidentifier
import comictaggerlib.resulttypes
import testing.comicdata
import testing.comicvine


def test_crop(cbz_double_cover, config, tmp_path, comicvine_api, tmp_comic_path):
    tmp_comic = comicapi.comicarchive.ComicArchive(tmp_comic_path)
    config, definitions = config
    iio = comictaggerlib.issueidentifier.IssueIdentifierOptions(
        series_match_search_thresh=config.Issue_Identifier__series_match_search_thresh,
        series_match_identify_thresh=config.Issue_Identifier__series_match_identify_thresh,
        use_publisher_filter=config.Auto_Tag__use_publisher_filter,
        publisher_filter=config.Auto_Tag__publisher_filter,
        quiet=config.Runtime_Options__quiet,
        cache_dir=config.Runtime_Options__config.user_cache_dir,
        border_crop_percent=config.Issue_Identifier__border_crop_percent,
        talker=comicvine_api,
    )
    ii = comictaggerlib.issueidentifier.IssueIdentifier(iio, None)

    im = Image.open(io.BytesIO(tmp_comic.archiver.read_file("double_cover.jpg")))

    cropped = ii._crop_double_page(im)
    original = tmp_comic.get_page(0)

    original_hash = comictaggerlib.imagehasher.ImageHasher(data=original).average_hash()
    cropped_hash = comictaggerlib.imagehasher.ImageHasher(image=cropped).average_hash()

    assert original_hash == cropped_hash


@pytest.mark.parametrize("additional_md, expected", testing.comicdata.metadata_keys)
def test_get_search_keys(cbz, config, additional_md, expected, comicvine_api):
    config, definitions = config
    iio = comictaggerlib.issueidentifier.IssueIdentifierOptions(
        series_match_search_thresh=config.Issue_Identifier__series_match_search_thresh,
        series_match_identify_thresh=config.Issue_Identifier__series_match_identify_thresh,
        use_publisher_filter=config.Auto_Tag__use_publisher_filter,
        publisher_filter=config.Auto_Tag__publisher_filter,
        quiet=config.Runtime_Options__quiet,
        cache_dir=config.Runtime_Options__config.user_cache_dir,
        border_crop_percent=config.Issue_Identifier__border_crop_percent,
        talker=comicvine_api,
    )
    ii = comictaggerlib.issueidentifier.IssueIdentifier(iio, None)

    assert expected == ii._get_search_keys(additional_md)


@pytest.mark.parametrize("data, expected", testing.comicdata.issueidentifier_score)
def test_get_issue_cover_match_score(
    cbz,
    config,
    comicvine_api,
    data: tuple[comicapi.genericmetadata.ImageHash, list[comicapi.genericmetadata.ImageHash], bool],
    expected: comictaggerlib.resulttypes.Score,
):
    config, definitions = config
    iio = comictaggerlib.issueidentifier.IssueIdentifierOptions(
        series_match_search_thresh=config.Issue_Identifier__series_match_search_thresh,
        series_match_identify_thresh=config.Issue_Identifier__series_match_identify_thresh,
        use_publisher_filter=config.Auto_Tag__use_publisher_filter,
        publisher_filter=config.Auto_Tag__publisher_filter,
        quiet=config.Runtime_Options__quiet,
        cache_dir=config.Runtime_Options__config.user_cache_dir,
        border_crop_percent=config.Issue_Identifier__border_crop_percent,
        talker=comicvine_api,
    )
    ii = comictaggerlib.issueidentifier.IssueIdentifier(iio, None)
    score = ii._get_issue_cover_match_score(
        primary_img_url=data[0],
        alt_urls=data[1],
        local_hashes=[("Cover 1", ii.calculate_hash(cbz.get_page(0)))],
    )
    assert expected == score


def test_search(cbz, config, comicvine_api):
    config, definitions = config
    iio = comictaggerlib.issueidentifier.IssueIdentifierOptions(
        series_match_search_thresh=config.Issue_Identifier__series_match_search_thresh,
        series_match_identify_thresh=config.Issue_Identifier__series_match_identify_thresh,
        use_publisher_filter=config.Auto_Tag__use_publisher_filter,
        publisher_filter=config.Auto_Tag__publisher_filter,
        quiet=config.Runtime_Options__quiet,
        cache_dir=config.Runtime_Options__config.user_cache_dir,
        border_crop_percent=config.Issue_Identifier__border_crop_percent,
        talker=comicvine_api,
    )
    ii = comictaggerlib.issueidentifier.IssueIdentifier(iio, None)
    result, issues = ii.identify(cbz, cbz.read_tags("cr"))
    cv_expected = comictaggerlib.resulttypes.IssueResult(
        score=comictaggerlib.resulttypes.Score(
            score=0,
            url=testing.comicvine.cv_issue_result["results"]["image"]["super_url"],
            remote_hash=212201432349720,
            local_hash_name="0",
            local_hash=212201432349720,
        ),
        series=comicapi.genericmetadata.ComicSeries(
            id=str(testing.comicvine.cv_volume_result["results"]["id"]),
            name=testing.comicvine.cv_volume_result["results"]["name"],
            count_of_issues=testing.comicvine.cv_volume_result["results"]["count_of_issues"],
            publisher=testing.comicvine.cv_volume_result["results"]["publisher"]["name"],
            start_year=int(testing.comicvine.cv_volume_result["results"]["start_year"]),
            description=testing.comicvine.cv_volume_result["results"]["description"],
            aliases=set(),
            count_of_volumes=None,
            image_url=testing.comicvine.cv_volume_result["results"]["image"]["super_url"],
            format=None,
            web_links=[comicapi.utils.parse_url(testing.comicvine.cv_volume_result["results"]["site_detail_url"])],
        ),
        md=comicapi.genericmetadata.GenericMetadata(
            day=testing.comicvine.date[0],
            month=testing.comicvine.date[1],
            year=testing.comicvine.date[2],
            issue=testing.comicvine.cv_issue_result["results"]["issue_number"],
            issue_id=str(testing.comicvine.cv_issue_result["results"]["id"]),
            series_id=str(testing.comicvine.cv_volume_result["results"]["id"]),
            series=str(testing.comicvine.cv_volume_result["results"]["name"]),
            issue_count=testing.comicvine.cv_volume_result["results"]["count_of_issues"],
            publisher=str(testing.comicvine.cv_volume_result["results"]["publisher"]["name"]),
            title=testing.comicvine.cv_issue_result["results"]["name"],
            data_origin=comicapi.genericmetadata.MetadataOrigin(name="Comic Vine", id="comicvine"),
            description=testing.comicvine.cv_issue_result["results"]["description"],
            web_links=[comicapi.utils.parse_url(testing.comicvine.cv_issue_result["results"]["site_detail_url"])],
            _cover_image=comicapi.genericmetadata.ImageHash(
                Hash=0, Kind="", URL=testing.comicvine.cv_issue_result["results"]["image"]["super_url"]
            ),
        ),
    )
    for r, e in zip(issues, [cv_expected]):
        assert r == e


def test_crop_border(cbz, config, comicvine_api):
    config, definitions = config
    iio = comictaggerlib.issueidentifier.IssueIdentifierOptions(
        series_match_search_thresh=config.Issue_Identifier__series_match_search_thresh,
        series_match_identify_thresh=config.Issue_Identifier__series_match_identify_thresh,
        use_publisher_filter=config.Auto_Tag__use_publisher_filter,
        publisher_filter=config.Auto_Tag__publisher_filter,
        quiet=config.Runtime_Options__quiet,
        cache_dir=config.Runtime_Options__config.user_cache_dir,
        border_crop_percent=config.Issue_Identifier__border_crop_percent,
        talker=comicvine_api,
    )
    ii = comictaggerlib.issueidentifier.IssueIdentifier(iio, None)

    # This creates a white square centered on a black background
    bg = Image.new("RGBA", (100, 100), (0, 0, 0, 255))
    fg = Image.new("RGBA", (50, 50), (255, 255, 255, 255))
    bg.paste(fg, (bg.width // 2 - (fg.width // 2), bg.height // 2 - (fg.height // 2)))

    cropped = ii._crop_border(bg, 49)

    assert cropped
    assert cropped.width == fg.width
    assert cropped.height == fg.height
    assert list(cropped.get_flattened_data()) == list(fg.get_flattened_data())
