from __future__ import annotations

import dataclasses

import comicapi.genericmetadata
import comictaggerlib.resulttypes
from comicapi import utils

search_results = [
    comictaggerlib.resulttypes.CVVolumeResults(
        count_of_issues=1,
        description="this is a description",
        id=1,
        image={"super_url": "https://test.org/image/1"},
        name="test",
        publisher=comictaggerlib.resulttypes.CVPublisher(name="test"),
        start_year="",  # This is currently submitted as a string and returned as an int
    ),
    comictaggerlib.resulttypes.CVVolumeResults(
        count_of_issues=1,
        description="this is a description",
        id=1,
        image={"super_url": "https://test.org/image/2"},
        name="test 2",
        publisher=comictaggerlib.resulttypes.CVPublisher(name="test"),
        start_year="",  # This is currently submitted as a string and returned as an int
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
        dataclasses.replace(comicapi.genericmetadata.md_test, series="test", issue="2", title="never"),
    ),
    (
        comicapi.genericmetadata.GenericMetadata(series="", issue="2", title="never"),
        dataclasses.replace(comicapi.genericmetadata.md_test, series=None, issue="2", title="never"),
    ),
    (
        comicapi.genericmetadata.GenericMetadata(),
        dataclasses.replace(comicapi.genericmetadata.md_test),
    ),
]

credits = [
    ("writer", "Dara Naraghi"),
    ("writeR", "Dara Naraghi"),
]

imprints = [
    ("marvel", ("", "Marvel")),
    ("marvel comics", ("", "Marvel")),
    ("aircel", ("Aircel Comics", "Marvel")),
]

additional_imprints = [
    ("test", ("Test", "Marvel")),
    ("temp", ("Temp", "DC Comics")),
]

all_imprints = imprints + additional_imprints

seed_imprints = {
    "Marvel": utils.ImprintDict(
        "Marvel",
        {
            "marvel comics": "",
            "aircel": "Aircel Comics",
        },
    )
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
