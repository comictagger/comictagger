from __future__ import annotations

import pathlib

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


@pytest.mark.parametrize("encoding", ["utf-8", "utf-8-sig"])
def test_parse_metadata_from_file_is_utf8(tmp_path, monkeypatch, encoding):
    real_read_text = pathlib.Path.read_text

    def read_text_cp1252(self, *args, **kwargs):
        # Without an explicit encoding, read_text() uses cp1252, as it does on a non-UTF-8 Windows locale
        if not args:
            kwargs.setdefault("encoding", "cp1252")
        return real_read_text(self, *args, **kwargs)

    monkeypatch.setattr(pathlib.Path, "read_text", read_text_cp1252)
    metadata_file = tmp_path / "metadata.yaml"
    metadata_file.write_text("series: Łukasz ✨, issue: '1'\n", encoding=encoding)

    parsed_md = comictaggerlib.ctsettings.types.parse_metadata_from_string(f"@{metadata_file}")

    assert parsed_md.series == "Łukasz ✨"
    assert parsed_md.issue == "1"
