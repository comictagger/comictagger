from __future__ import annotations

from typing import Any

import comicapi.genericmetadata
import comictaggerlib.comicvinetalker

cv_issue_result: dict[str, Any] = {
    "error": "OK",
    "limit": 1,
    "offset": 0,
    "number_of_page_results": 1,
    "number_of_total_results": 1,
    "status_code": 1,
    "results": {
        "aliases": None,
        "api_detail_url": "https://comicvine.gamespot.com/api/issue/4000-311811/",
        "associated_images": [],
        "character_credits": [],
        "character_died_in": [],
        "concept_credits": [],
        "cover_date": "2007-12-01",
        "date_added": "2012-01-18 06:48:56",
        "date_last_updated": "2012-01-18 17:27:48",
        "deck": None,
        "description": '<p><i>IDW Publishing continues to bring the stories of acclaimed science-fiction author Cory Doctorow to comics, this time offering up "Craphound." Despite the exoskeleton and mouth full of poisonous suckers, Jerry got along with the alien better than with most humans. In fact, Jerry had nicknamed him "Craphound", after their shared love of hunting for unique treasures at garage sales and thrift stores. They were buddies. That is, until Craphound found the old cowboy trunk. Adapted by Dara Naraghi (whose Lifelike debuts this month, too. See previous page for info), with a cover by Eisner-winning artist Paul Pope!</i></p>',
        "first_appearance_characters": None,
        "first_appearance_concepts": None,
        "first_appearance_locations": None,
        "first_appearance_objects": None,
        "first_appearance_storyarcs": None,
        "first_appearance_teams": None,
        "has_staff_review": False,
        "id": 311811,
        "image": {
            "icon_url": "https://comicvine.gamespot.com/a/uploads/square_avatar/11/115179/2165551-cd3.jpg",
            "medium_url": "https://comicvine.gamespot.com/a/uploads/scale_medium/11/115179/2165551-cd3.jpg",
            "screen_url": "https://comicvine.gamespot.com/a/uploads/screen_medium/11/115179/2165551-cd3.jpg",
            "screen_large_url": "https://comicvine.gamespot.com/a/uploads/screen_kubrick/11/115179/2165551-cd3.jpg",
            "small_url": "https://comicvine.gamespot.com/a/uploads/scale_small/11/115179/2165551-cd3.jpg",
            "super_url": "https://comicvine.gamespot.com/a/uploads/scale_large/11/115179/2165551-cd3.jpg",
            "thumb_url": "https://comicvine.gamespot.com/a/uploads/scale_avatar/11/115179/2165551-cd3.jpg",
            "tiny_url": "https://comicvine.gamespot.com/a/uploads/square_mini/11/115179/2165551-cd3.jpg",
            "original_url": "https://comicvine.gamespot.com/a/uploads/original/11/115179/2165551-cd3.jpg",
            "image_tags": "All Images",
        },
        "issue_number": "3",
        "location_credits": [],
        "name": "Craphound",
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
                "api_detail_url": "https://comicvine.gamespot.com/api/person/4040-4306/",
                "id": 4306,
                "name": "Paul Pope",
                "site_detail_url": "https://comicvine.gamespot.com/paul-pope/4040-4306/",
                "role": "cover",
            },
        ],
        "site_detail_url": "https://comicvine.gamespot.com/cory-doctorows-futuristic-tales-of-the-here-and-no/4000-311811/",
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
        "count_of_issues": 6,
        "id": 23437,
        "name": "Cory Doctorow's Futuristic Tales of the Here and Now",
        "publisher": {
            "api_detail_url": "https://comicvine.gamespot.com/api/publisher/4010-1190/",
            "id": 1190,
            "name": "IDW Publishing",
        },
        "start_year": "2007",
    },
    "version": "1.0",
}
date = comictaggerlib.comicvinetalker.ComicVineTalker().parse_date_str(cv_issue_result["results"]["cover_date"])

cv_md = comicapi.genericmetadata.GenericMetadata(
    is_empty=False,
    tag_origin=None,
    series=cv_issue_result["results"]["volume"]["name"],
    issue=cv_issue_result["results"]["issue_number"],
    title=cv_issue_result["results"]["name"],
    publisher=cv_volume_result["results"]["publisher"]["name"],
    month=date[1],
    year=date[2],
    day=date[0],
    issue_count=None,
    volume=None,
    genre=None,
    language=None,
    comments=comictaggerlib.comicvinetalker.ComicVineTalker().cleanup_html(
        cv_issue_result["results"]["description"], False
    ),
    volume_count=None,
    critical_rating=None,
    country=None,
    alternate_series=None,
    alternate_number=None,
    alternate_count=None,
    imprint=None,
    notes="Tagged with ComicTagger 1.4.4a9.dev20 using info from Comic Vine on 2022-07-11 17:42:41.  [Issue ID 311811]",
    web_link=cv_issue_result["results"]["site_detail_url"],
    format=None,
    manga=None,
    black_and_white=None,
    page_count=None,
    maturity_rating=None,
    story_arc=None,
    series_group=None,
    scan_info=None,
    characters="",
    teams="",
    locations="",
    credits=[
        {
            "person": cv_issue_result["results"]["person_credits"][0]["name"],
            "role": cv_issue_result["results"]["person_credits"][0]["role"].title(),
            "primary": False,
        },
        {
            "person": cv_issue_result["results"]["person_credits"][1]["name"],
            "role": cv_issue_result["results"]["person_credits"][1]["role"].title(),
            "primary": False,
        },
    ],
    tags=[],
    pages=[],
    price=None,
    is_version_of=None,
    rights=None,
    identifier=None,
    last_mark=None,
    cover_image=None,
)


class MockResponse:
    """Mocks the response object from requests"""

    def __init__(self, result: dict[str, Any]) -> None:
        self.status_code = 200
        self.result = result

    # mock json() method always returns a specific testing dictionary
    def json(self) -> dict[str, list]:
        return self.result
