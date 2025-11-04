from __future__ import annotations

import pytest
from importlib_metadata import entry_points

import comicapi.genericmetadata
import testing.comicdata
from comicapi.archivers.zip import ZipArchiver
from comictaggerlib.md import prepare_metadata

tags = []

for x in entry_points(group="comicapi.tags"):
    tag = x.load()
    supported = tag.enabled
    exe_found = True
    tags.append(pytest.param(tag, marks=pytest.mark.xfail(not supported, reason="tags not enabled")))

if not tags:
    raise Exception("No tags found")


@pytest.mark.parametrize("tag_type", tags)
def test_metadata(mock_version, tmp_comic_path, md_saved, tag_type, md):
    archiver = ZipArchiver.open(tmp_comic_path)
    tag = tag_type(mock_version[0])
    supported_attributes = tag.supported_attributes
    tag.write_tags(md, archiver)
    written_metadata = tag.read_tags(archiver)
    md = md_saved._get_clean_metadata(*supported_attributes)

    # Hack back in the pages variable because CoMet supports identifying the cover by the filename
    if tag.id == "comet":
        new_md.pages = [
            comicapi.genericmetadata.PageMetadata(
                archive_index=0,
                bookmark="",
                display_index=0,
                filename="!cover.jpg",
                type=comicapi.genericmetadata.PageType.FrontCover,
            )
        ]
        written_metadata = written_metadata._get_clean_metadata(*supported_attributes).replace(
            pages=written_metadata.pages
        )
    else:
        written_metadata = written_metadata._get_clean_metadata(*supported_attributes)

    assert written_metadata == new_md


@pytest.mark.parametrize("metadata, expected", testing.comicdata.metadata_prepared)
def test_prepare_metadata(mock_version, mock_now, config, metadata, expected):
    new_md = prepare_metadata(metadata[0], metadata[1], config[0])
    assert new_md == expected
