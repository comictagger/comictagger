from __future__ import annotations

import pytest

import comicapi.genericmetadata
import comictaggerlib.ctsettings.types

md_strings = (
    ("", comicapi.genericmetadata.md_test.replace()),
    ("year:", comicapi.genericmetadata.md_test.replace(year=None)),
    ("year: 2009", comicapi.genericmetadata.md_test.replace(year=2009)),
    ("series:", comicapi.genericmetadata.md_test.replace(series=None)),
    ("series_aliases:", comicapi.genericmetadata.md_test.replace(series_aliases=set())),
    ("black_and_white:", comicapi.genericmetadata.md_test.replace(black_and_white=None)),
    ("credits:", comicapi.genericmetadata.md_test.replace(credits=[])),
    ("story_arcs:", comicapi.genericmetadata.md_test.replace(story_arcs=[])),
)


@pytest.mark.parametrize("string,expected", md_strings)
def test_parse_metadata_from_string(string, expected, md):
    parsed_md = comictaggerlib.ctsettings.types.parse_metadata_from_string(string)

    md.overlay(parsed_md)

    assert md == expected
