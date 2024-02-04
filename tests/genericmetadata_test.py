from __future__ import annotations

import textwrap

import pytest

import comicapi.genericmetadata
from comicapi.genericmetadata import OverlayMode, parse_url
from testing.comicdata import credits, metadata


def test_apply_default_page_list(tmp_path):
    md = comicapi.genericmetadata.GenericMetadata()
    md.overlay(comicapi.genericmetadata.md_test)
    md.pages = []
    md.apply_default_page_list(["testing"])

    assert isinstance(md.pages[0]["image_index"], int)


@pytest.mark.parametrize("replaced, expected", metadata)
def test_metadata_overlay(md: comicapi.genericmetadata.GenericMetadata, replaced, expected):
    md.overlay(replaced)

    assert md == expected


def test_metadata_overlay_add_missing():
    md = comicapi.genericmetadata.GenericMetadata(series="test", issue="1", title="test", genres={"test", "test2"})
    add = comicapi.genericmetadata.GenericMetadata(
        series="test2", issue="2", title="test2", genres={"test3", "test4"}, issue_count=5
    )
    expected = comicapi.genericmetadata.GenericMetadata(
        series="test", issue="1", title="test", genres={"test", "test2"}, issue_count=5
    )
    md.overlay(add, OverlayMode.add_missing)

    assert md == expected


def test_metadata_overlay_combine():
    md = comicapi.genericmetadata.GenericMetadata(
        series="test",
        issue="1",
        title="test",
        genres={"test", "test2"},
        story_arcs=["arc1"],
        characters={"Bob", "fred"},
        web_links=[parse_url("https://my.comics.here.com")],
    )
    combine_new = comicapi.genericmetadata.GenericMetadata(
        series="test2",
        title="test2",
        genres={"test2", "test3", "test4"},
        story_arcs=["arc1", "arc2"],
        characters={"bob", "fred"},
    )
    expected = comicapi.genericmetadata.GenericMetadata(
        series="test2",
        issue="1",
        title="test2",
        genres={"test", "test2", "test3", "test4"},
        story_arcs=["arc1", "arc2"],
        characters={"bob", "fred"},
        web_links=[parse_url("https://my.comics.here.com")],
    )
    md.overlay(combine_new, OverlayMode.combine)

    assert md == expected


def test_assign_dedupe_set():
    md_cur = comicapi.genericmetadata.GenericMetadata(characters={"Macintosh", "Søren Kierkegaard", "Barry"})
    md_new = comicapi.genericmetadata.GenericMetadata(characters={"MacIntosh", "Soren Kierkegaard"})
    # Expect a failure to normalise with NFKD and 'ø'
    expected = comicapi.genericmetadata.GenericMetadata(
        characters={"MacIntosh", "Soren Kierkegaard", "Søren Kierkegaard", "Barry"}
    )

    md_cur.overlay(md_new, OverlayMode.combine)

    assert md_cur == expected


def test_assign_dedupe_list():
    md_cur = comicapi.genericmetadata.GenericMetadata(story_arcs=["arc 1", "arc2", "arc 3"])
    md_new = comicapi.genericmetadata.GenericMetadata(story_arcs=["Arc 1", "Arc2"])
    expected = comicapi.genericmetadata.GenericMetadata(story_arcs=["Arc 1", "Arc2", "arc 3"])

    md_cur.overlay(md_new, OverlayMode.combine)

    assert md_cur == expected


def test_assign_credits_overlay():
    md = comicapi.genericmetadata.GenericMetadata()
    md.add_credit(person="test", role="writer", primary=False)
    md.add_credit(person="test", role="artist", primary=True)

    md_new = comicapi.genericmetadata.GenericMetadata()
    md_new.add_credit(person="", role="writer")
    md_new.add_credit(person="test2", role="inker")

    expected = comicapi.genericmetadata.GenericMetadata()
    expected.add_credit(person="test", role="writer", primary=False)
    expected.add_credit(person="test", role="artist", primary=True)
    expected.add_credit(person="test2", role="inker")

    assert md.assign_credits_overlay(md.credits, md_new.credits) == expected.credits


def test_assign_credits_add_missing():
    md = comicapi.genericmetadata.GenericMetadata()
    md.add_credit(person="test", role="writer", primary=False)
    md.add_credit(person="test", role="artist", primary=True)

    md_new = comicapi.genericmetadata.GenericMetadata()
    md_new.add_credit(person="Bob", role="writer")
    md_new.add_credit(person="test", role="artist", primary=True)

    expected = comicapi.genericmetadata.GenericMetadata()
    expected.add_credit(person="Bob", role="writer")
    expected.add_credit(person="test", role="artist", primary=True)
    expected.add_credit(person="test", role="writer", primary=False)

    assert md.assign_credits_add_missing(md.credits, md_new.credits) == expected.credits


def test_add_credit():
    md = comicapi.genericmetadata.GenericMetadata()

    md.add_credit(person="test", role="writer", primary=False)
    assert md.credits == [comicapi.genericmetadata.Credit(person="test", role="writer", primary=False)]


def test_add_credit_primary():
    md = comicapi.genericmetadata.GenericMetadata()

    md.add_credit(person="test", role="writer", primary=False)
    md.add_credit(person="test", role="writer", primary=True)
    assert md.credits == [comicapi.genericmetadata.Credit(person="test", role="writer", primary=True)]


@pytest.mark.parametrize("md, role, expected", credits)
def test_get_primary_credit(md, role, expected):
    assert md.get_primary_credit(role) == expected


def test_str(md):
    expected = textwrap.dedent(
        """\
        series:           Cory Doctorow's Futuristic Tales of the Here and Now
        issue:            1
        issue_count:      6
        title:            Anda's Game
        publisher:        IDW Publishing
        year:             2007
        month:            10
        day:              1
        volume:           1
        genres:           Sci-Fi
        language:         en
        critical_rating:  3.0
        alternate_series: Tales
        alternate_number: 2
        alternate_count:  7
        imprint:          craphound.com
        web_links:        ['https://comicvine.gamespot.com/cory-doctorows-futuristic-tales-of-the-here-and-no/4000-140529/']
        format:           Series
        manga:            No
        maturity_rating:  Everyone 10+
        story_arcs:       ['Here and Now']
        series_groups:    ['Futuristic Tales']
        scan_info:        (CC BY-NC-SA 3.0)
        characters:       Anda
        teams:            Fahrenheit
        locations:        lonely  cottage
        description:      For 12-year-old Anda, getting paid real money to kill the characters of players who were cheating in her favorite online computer game was a win-win situation. Until she found out who was paying her, and what those characters meant to the livelihood of children around the world.
        notes:            Tagged with ComicTagger 1.3.2a5 using info from Comic Vine on 2022-04-16 15:52:26. [Issue ID 140529]
        credit:           Writer: Dara Naraghi
        credit:           Penciller: Esteve Polls
        credit:           Inker: Esteve Polls
        credit:           Letterer: Neil Uyetake
        credit:           Cover: Sam Kieth
        credit:           Editor: Ted Adams
    """
    )

    assert str(md) == expected
