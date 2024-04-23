from __future__ import annotations

import comicapi.genericmetadata
from comicapi import utils

search_results = [
    dict(
        count_of_issues=1,
        count_of_volumes=1,
        description="this is a description",
        id="1",
        image_url="https://test.org/image/1",
        name="test",
        publisher="test",
        start_year=0,
        aliases=[],
        format=None,
    ),
    dict(
        count_of_issues=1,
        count_of_volumes=1,
        description="this is a description",
        id="2",
        image_url="https://test.org/image/2",
        name="test 2",
        publisher="test",
        start_year=0,
        aliases=[],
        format=None,
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
        comicapi.genericmetadata.GenericMetadata(),
        comicapi.genericmetadata.md_test.copy(),
    ),
]

metadata_add = [
    (
        comicapi.genericmetadata.GenericMetadata(series="test", issue="1", title="test", genres={"test", "test2"}),
        comicapi.genericmetadata.GenericMetadata(
            series="test2", issue="2", title="test2", genres={"test3", "test4"}, issue_count=5
        ),
        comicapi.genericmetadata.GenericMetadata(
            series="test", issue="1", title="test", genres={"test", "test2"}, issue_count=5
        ),
    ),
]

metadata_combine = [
    (
        comicapi.genericmetadata.GenericMetadata(
            series="test",
            issue="1",
            title="test",
            genres={"test", "test2"},
            story_arcs=["arc1"],
            characters={"Bob", "fred"},
            web_links=[comicapi.genericmetadata.parse_url("https://my.comics.here.com")],
        ),
        comicapi.genericmetadata.GenericMetadata(
            series="test2",
            title="test2",
            genres={"test2", "test3", "test4"},
            story_arcs=["arc1", "arc2"],
            characters={"bob", "fred"},
        ),
        comicapi.genericmetadata.GenericMetadata(
            series="test2",
            issue="1",
            title="test2",
            genres={"test", "test2", "test3", "test4"},
            story_arcs=["arc1", "arc2"],
            characters={"bob", "fred"},
            web_links=[comicapi.genericmetadata.parse_url("https://my.comics.here.com")],
        ),
    ),
]

metadata_dedupe_set = [
    (
        comicapi.genericmetadata.GenericMetadata(characters={"Macintosh", "Søren Kierkegaard", "Barry"}),
        comicapi.genericmetadata.GenericMetadata(characters={"MacIntosh", "Soren Kierkegaard"}),
        comicapi.genericmetadata.GenericMetadata(
            characters={"MacIntosh", "Soren Kierkegaard", "Søren Kierkegaard", "Barry"}
        ),
    ),
]

metadata_dedupe_list = [
    (
        comicapi.genericmetadata.GenericMetadata(story_arcs=["arc 1", "arc2", "arc 3"]),
        comicapi.genericmetadata.GenericMetadata(story_arcs=["Arc 1", "Arc2"]),
        comicapi.genericmetadata.GenericMetadata(story_arcs=["Arc 1", "Arc2", "arc 3"]),
    ),
]

metadata_keys = [
    (
        comicapi.genericmetadata.md_test,
        {
            "issue_count": 6,
            "issue_number": "1",
            "month": 10,
            "series": "Cory Doctorow's Futuristic Tales of the Here and Now",
            "year": 2007,
            "alternate_count": 7,
            "alternate_number": "2",
            "imprint": "craphound.com",
            "publisher": "IDW Publishing",
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


metadata_prepared = (
    (
        (comicapi.genericmetadata.GenericMetadata(), comicapi.genericmetadata.GenericMetadata()),
        comicapi.genericmetadata.GenericMetadata(notes="Tagged with ComicTagger 1.3.2a5 on 2022-04-16 15:52:26."),
    ),
    (
        (comicapi.genericmetadata.GenericMetadata(issue_id="123"), comicapi.genericmetadata.GenericMetadata()),
        comicapi.genericmetadata.GenericMetadata(
            issue_id="123", notes="Tagged with ComicTagger 1.3.2a5 on 2022-04-16 15:52:26. [Issue ID 123]"
        ),
    ),
    (
        (
            comicapi.genericmetadata.GenericMetadata(
                issue_id="123", tag_origin=comicapi.genericmetadata.TagOrigin("SOURCE", "Source")
            ),
            comicapi.genericmetadata.GenericMetadata(),
        ),
        comicapi.genericmetadata.GenericMetadata(
            issue_id="123",
            tag_origin=comicapi.genericmetadata.TagOrigin("SOURCE", "Source"),
            notes="Tagged with ComicTagger 1.3.2a5 using info from Source on 2022-04-16 15:52:26. [Issue ID 123]",
        ),
    ),
)
