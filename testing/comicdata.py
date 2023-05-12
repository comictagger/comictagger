from __future__ import annotations

import comicapi.genericmetadata
import comictalker.resulttypes
from comicapi import utils

search_results = [
    comictalker.resulttypes.ComicSeries(
        count_of_issues=1,
        count_of_volumes=1,
        volume="1",
        description="this is a description",
        id="1",
        image_url="https://test.org/image/1",
        name="test",
        publisher="test",
        start_year=0,
        aliases=[],
        genres=[],
    ),
    comictalker.resulttypes.ComicSeries(
        count_of_issues=1,
        count_of_volumes=1,
        volume="1",
        description="this is a description",
        id="2",
        image_url="https://test.org/image/2",
        name="test 2",
        publisher="test",
        start_year=0,
        aliases=[],
        genres=[],
    ),
]

alt_covers = [
    {"issue_id": 1, "url_list": ["https://test.org/image/1"]},
    {"issue_id": 2, "url_list": ["https://test.org/image/2"]},
]

select_details = [
    {
        "issue_id": 1,
        "image_url": "https://test.org/image/1",
        "thumb_image_url": "https://test.org/thumb/1",
        "cover_date": "1998",
        "site_detail_url": "https://test.org/1",
    },
    {
        "issue_id": 2,
        "image_url": "https://test.org/image/2",
        "thumb_image_url": "https://test.org/thumb/2",
        "cover_date": "1998",
        "site_detail_url": "https://test.org/2",
    },
]

# Used to test GenericMetadata.overlay
metadata = [
    (
        comicapi.genericmetadata.GenericMetadata(series="test", issue="2", title="never"),
        comicapi.genericmetadata.md_test.replace(series="test", issue="2", title="never"),
    ),
    (
        comicapi.genericmetadata.GenericMetadata(series="", issue="2", title="never"),
        comicapi.genericmetadata.md_test.replace(series=None, issue="2", title="never"),
    ),
    (
        comicapi.genericmetadata.GenericMetadata(),
        comicapi.genericmetadata.md_test.copy(),
    ),
]

metadata_keys = [
    (
        comicapi.genericmetadata.GenericMetadata(),
        {
            "issue_count": 6,
            "issue_number": "1",
            "month": 10,
            "series": "Cory Doctorow's Futuristic Tales of the Here and Now",
            "year": 2007,
        },
    ),
    (
        comicapi.genericmetadata.GenericMetadata(series="test"),
        {
            "issue_count": 6,
            "issue_number": "1",
            "month": 10,
            "series": "test",
            "year": 2007,
        },
    ),
    (
        comicapi.genericmetadata.GenericMetadata(series="test", issue="3"),
        {
            "issue_count": 6,
            "issue_number": "3",
            "month": 10,
            "series": "test",
            "year": 2007,
        },
    ),
]

credits = [
    (comicapi.genericmetadata.md_test, "writer", "Dara Naraghi"),
    (comicapi.genericmetadata.md_test, "writeR", "Dara Naraghi"),
    (
        comicapi.genericmetadata.md_test.replace(
            credits=[{"person": "Dara Naraghi", "role": "writer"}, {"person": "Dara Naraghi", "role": "writer"}]
        ),
        "writeR",
        "Dara Naraghi",
    ),
]

imprints = [
    ("marvel", ("", "Marvel")),
    ("marvel comics", ("", "Marvel")),
    ("aircel", ("Aircel Comics", "Marvel")),
    ("nothing", ("", "nothing")),
]

additional_imprints = [
    ("test", ("Test", "Marvel")),
    ("temp", ("Temp", "DC Comics")),
]

all_imprints = imprints + additional_imprints

seed_imprints = {
    "Marvel": utils.ImprintDict("Marvel", {"marvel comics": "", "aircel": "Aircel Comics"}),
}

additional_seed_imprints = {
    "Marvel": utils.ImprintDict("Marvel", {"test": "Test"}),
    "DC Comics": utils.ImprintDict("DC Comics", {"temp": "Temp"}),
}

all_seed_imprints = {
    "Marvel": seed_imprints["Marvel"].copy(),
    "DC Comics": additional_seed_imprints["DC Comics"].copy(),
}
all_seed_imprints["Marvel"].update(additional_seed_imprints["Marvel"])

conflicting_seed_imprints = {"Marvel": {"test": "Never"}}
