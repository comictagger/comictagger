from __future__ import annotations

from typing import Any

import comicapi.genericmetadata
from comicapi import utils
from comictalker.resulttypes import ComicIssue, ComicSeries
from comictalker.talker_utils import cleanup_html


def filter_field_list(cv_result, kwargs):
    if "field_list" in kwargs["params"]:
        for key in list(cv_result.keys()):
            if key not in kwargs["params"]["field_list"]:
                del cv_result[key]


cv_issue_result: dict[str, Any] = {
    "error": "OK",
    "limit": 1,
    "offset": 0,
    "number_of_page_results": 1,
    "number_of_total_results": 1,
    "status_code": 1,
    "results": {
        "aliases": None,
        "api_detail_url": "https://comicvine.gamespot.com/api/issue/4000-140529/",
        "associated_images": [],
        "character_credits": [],
        "character_died_in": [],
        "concept_credits": [],
        "cover_date": "2007-10-01",
        "date_added": "2008-10-16 05:25:47",
        "date_last_updated": "2010-06-09 18:05:49",
        "deck": None,
        "description": "<i>For 12-year-old Anda, getting paid real money to kill the characters of players who were cheating in her favorite online computer game was a win-win situation. Until she found out who was paying her, and what those characters meant to the livelihood of children around the world.</i>",
        "first_appearance_characters": None,
        "first_appearance_concepts": None,
        "first_appearance_locations": None,
        "first_appearance_objects": None,
        "first_appearance_storyarcs": None,
        "first_appearance_teams": None,
        "has_staff_review": False,
        "id": 140529,
        "image": {
            "icon_url": "https://comicvine.gamespot.com/a/uploads/square_avatar/0/574/585444-109004_20080707014047_large.jpg",
            "medium_url": "https://comicvine.gamespot.com/a/uploads/scale_medium/0/574/585444-109004_20080707014047_large.jpg",
            "screen_url": "https://comicvine.gamespot.com/a/uploads/screen_medium/0/574/585444-109004_20080707014047_large.jpg",
            "screen_large_url": "https://comicvine.gamespot.com/a/uploads/screen_kubrick/0/574/585444-109004_20080707014047_large.jpg",
            "small_url": "https://comicvine.gamespot.com/a/uploads/scale_small/0/574/585444-109004_20080707014047_large.jpg",
            "super_url": "https://comicvine.gamespot.com/a/uploads/scale_large/0/574/585444-109004_20080707014047_large.jpg",
            "thumb_url": "https://comicvine.gamespot.com/a/uploads/scale_avatar/0/574/585444-109004_20080707014047_large.jpg",
            "tiny_url": "https://comicvine.gamespot.com/a/uploads/square_mini/0/574/585444-109004_20080707014047_large.jpg",
            "original_url": "https://comicvine.gamespot.com/a/uploads/original/0/574/585444-109004_20080707014047_large.jpg",
            "image_tags": "All Images",
        },
        "issue_number": "1",
        "location_credits": [],
        "name": "Anda's Game",
        "object_credits": [],
        "person_credits": [
            {
                "api_detail_url": "https://comicvine.gamespot.com/api/person/4040-56410/",
                "id": 56410,
                "name": "Dara Naraghi",
                "site_detail_url": "https://comicvine.gamespot.com/dara-naraghi/4040-56410/",
                "role": "writer",
            },
            {
                "api_detail_url": "https://comicvine.gamespot.com/api/person/4040-57222/",
                "id": 57222,
                "name": "Esteve Polls",
                "site_detail_url": "https://comicvine.gamespot.com/esteve-polls/4040-57222/",
                "role": "artist",
            },
            {
                "api_detail_url": "https://comicvine.gamespot.com/api/person/4040-48472/",
                "id": 48472,
                "name": "Neil Uyetake",
                "site_detail_url": "https://comicvine.gamespot.com/neil-uyetake/4040-48472/",
                "role": "letterer",
            },
            {
                "api_detail_url": "https://comicvine.gamespot.com/api/person/4040-5329/",
                "id": 5329,
                "name": "Sam Kieth",
                "site_detail_url": "https://comicvine.gamespot.com/sam-kieth/4040-5329/",
                "role": "cover",
            },
            {
                "api_detail_url": "https://comicvine.gamespot.com/api/person/4040-58534/",
                "id": 58534,
                "name": "Ted Adams",
                "site_detail_url": "https://comicvine.gamespot.com/ted-adams/4040-58534/",
                "role": "editor",
            },
        ],
        "site_detail_url": "https://comicvine.gamespot.com/cory-doctorows-futuristic-tales-of-the-here-and-no/4000-140529/",
        "store_date": None,
        "story_arc_credits": [],
        "team_credits": [],
        "team_disbanded_in": [],
        "volume": {
            "api_detail_url": "https://comicvine.gamespot.com/api/volume/4050-23437/",
            "id": 23437,
            "name": "Cory Doctorow's Futuristic Tales of the Here and Now",
            "site_detail_url": "https://comicvine.gamespot.com/cory-doctorows-futuristic-tales-of-the-here-and-no/4050-23437/",
        },
    },
    "version": "1.0",
}

cv_volume_result: dict[str, Any] = {
    "error": "OK",
    "limit": 1,
    "offset": 0,
    "number_of_page_results": 1,
    "number_of_total_results": 1,
    "status_code": 1,
    "results": {
        "aliases": None,
        "api_detail_url": "https://comicvine.gamespot.com/api/volume/4050-23437/",
        "count_of_issues": 6,
        "date_added": "2008-10-16 05:25:47",
        "date_last_updated": "2012-01-18 17:21:57",
        "deck": None,
        "description": "<p>Writer and <em>BoingBoing.net</em> co-editor <strong>Cory Doctorow</strong> has won acclaim for his science-fiction writing as well as his Creative Commons presentation of his material. Now, IDW Publishing is proud to present six standalone stories adapted from Doctorow's work, each featuring cover art by some of comics' top talents.</p>",
        "id": 23437,
        "image": {
            "icon_url": "https://comicvine.gamespot.com/a/uploads/square_avatar/0/574/585444-109004_20080707014047_large.jpg",
            "medium_url": "https://comicvine.gamespot.com/a/uploads/scale_medium/0/574/585444-109004_20080707014047_large.jpg",
            "screen_url": "https://comicvine.gamespot.com/a/uploads/screen_medium/0/574/585444-109004_20080707014047_large.jpg",
            "screen_large_url": "https://comicvine.gamespot.com/a/uploads/screen_kubrick/0/574/585444-109004_20080707014047_large.jpg",
            "small_url": "https://comicvine.gamespot.com/a/uploads/scale_small/0/574/585444-109004_20080707014047_large.jpg",
            "super_url": "https://comicvine.gamespot.com/a/uploads/scale_large/0/574/585444-109004_20080707014047_large.jpg",
            "thumb_url": "https://comicvine.gamespot.com/a/uploads/scale_avatar/0/574/585444-109004_20080707014047_large.jpg",
            "tiny_url": "https://comicvine.gamespot.com/a/uploads/square_mini/0/574/585444-109004_20080707014047_large.jpg",
            "original_url": "https://comicvine.gamespot.com/a/uploads/original/0/574/585444-109004_20080707014047_large.jpg",
            "image_tags": "All Images",
        },
        "name": "Cory Doctorow's Futuristic Tales of the Here and Now",
        "publisher": {
            "api_detail_url": "https://comicvine.gamespot.com/api/publisher/4010-1190/",
            "id": 1190,
            "name": "IDW Publishing",
        },
        "site_detail_url": "https://comicvine.gamespot.com/cory-doctorows-futuristic-tales-of-the-here-and-no/4050-23437/",
        "start_year": "2007",
    },
    "version": "1.0",
}
cv_not_found = {
    "error": "Object Not Found",
    "limit": 0,
    "offset": 0,
    "number_of_page_results": 0,
    "number_of_total_results": 0,
    "status_code": 101,
    "results": [],
}
comic_issue_result = ComicIssue(
    aliases=cv_issue_result["results"]["aliases"] or [],
    cover_date=cv_issue_result["results"]["cover_date"],
    description=cv_issue_result["results"]["description"],
    id=str(cv_issue_result["results"]["id"]),
    image_url=cv_issue_result["results"]["image"]["super_url"],
    issue_number=cv_issue_result["results"]["issue_number"],
    volume=None,
    name=cv_issue_result["results"]["name"],
    site_detail_url=cv_issue_result["results"]["site_detail_url"],
    series=ComicSeries(
        id=str(cv_issue_result["results"]["volume"]["id"]),
        name=cv_issue_result["results"]["volume"]["name"],
        aliases=[],
        count_of_issues=cv_volume_result["results"]["count_of_issues"],
        count_of_volumes=None,
        description=cv_volume_result["results"]["description"],
        image_url=cv_volume_result["results"]["image"]["super_url"],
        publisher=cv_volume_result["results"]["publisher"]["name"],
        start_year=int(cv_volume_result["results"]["start_year"]),
        genres=[],
        format=None,
    ),
    characters=[],
    alt_image_urls=[],
    complete=False,
    credits=[],
    locations=[],
    story_arcs=[],
    critical_rating=0,
    maturity_rating="",
    manga="",
    language="",
    country="",
    genres=[],
    tags=[],
    teams=[],
)
date = utils.parse_date_str(cv_issue_result["results"]["cover_date"])

cv_md = comicapi.genericmetadata.GenericMetadata(
    is_empty=False,
    tag_origin="Comic Vine",
    issue_id=str(cv_issue_result["results"]["id"]),
    series=cv_issue_result["results"]["volume"]["name"],
    issue=cv_issue_result["results"]["issue_number"],
    title=cv_issue_result["results"]["name"],
    publisher=cv_volume_result["results"]["publisher"]["name"],
    month=date[1],
    year=date[2],
    day=date[0],
    issue_count=6,
    volume=None,
    genre=None,
    language=None,
    comments=cleanup_html(cv_issue_result["results"]["description"], False),
    volume_count=None,
    critical_rating=None,
    country=None,
    alternate_series=None,
    alternate_number=None,
    alternate_count=None,
    imprint=None,
    notes=None,
    web_link=cv_issue_result["results"]["site_detail_url"],
    format=None,
    manga=None,
    black_and_white=None,
    page_count=None,
    maturity_rating=None,
    story_arc=None,
    series_group=None,
    scan_info=None,
    characters=None,
    teams=None,
    locations=None,
    credits=[
        comicapi.genericmetadata.CreditMetadata(person=x["name"], role=x["role"].title(), primary=False)
        for x in cv_issue_result["results"]["person_credits"]
    ],
    tags=set(),
    pages=[],
    price=None,
    is_version_of=None,
    rights=None,
    identifier=None,
    last_mark=None,
    cover_image=cv_issue_result["results"]["image"]["super_url"],
)


class MockResponse:
    """Mocks the response object from requests"""

    def __init__(self, result: dict[str, Any], content=None) -> None:
        self.status_code = 200
        self.result = result
        self.content = content

    def json(self) -> dict[str, list]:
        return self.result
