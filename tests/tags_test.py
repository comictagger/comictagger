from __future__ import annotations

import pytest
from importlib_metadata import entry_points

import comicapi.genericmetadata
import testing.comicdata
from comicapi.comicarchive import ComicArchive
from comicapi.tags import Tag
from comictaggerlib.md import prepare_metadata

tags = []

for x in entry_points(group="comicapi.tags"):
    tag = x.load()
    supported = tag.enabled
    exe_found = True
    tags.append(pytest.param(tag, marks=pytest.mark.xfail(not supported, reason="tags not enabled")))

if not tags:
    raise Exception("No tags found")


@pytest.mark.parametrize("tag", tags)
def test_metadata(mock_version, tmp_comic_path, md_saved, tag: Tag, md):
    comic = ComicArchive(tmp_comic_path)
    comic.remove_tags(tag)

    no_tags = comic.read_tags(tag)

    assert no_tags == comicapi.genericmetadata.GenericMetadata()

    comic.write_tags(mock_version[0], md, tag)
    written_metadata = comic.read_tags(tag)
    md = md_saved._get_clean_metadata(*tag.supported_attributes)

    written_metadata = written_metadata._get_clean_metadata(*tag.supported_attributes)

    assert written_metadata == new_md


@pytest.mark.parametrize("metadata, expected", testing.comicdata.metadata_prepared)
def test_prepare_metadata(mock_version, mock_now, config, metadata, expected):
    new_md = prepare_metadata(metadata[0], metadata[1], config[0])
    assert new_md == expected
