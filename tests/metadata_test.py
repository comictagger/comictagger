from __future__ import annotations

import pytest
from importlib_metadata import entry_points

import comicapi.genericmetadata

metadata_styles = []

for x in entry_points(group="comicapi.metadata"):
    meetadata = x.load()
    supported = meetadata.enabled
    exe_found = True
    metadata_styles.append(
        pytest.param(meetadata, marks=pytest.mark.xfail(not supported, reason="metadata not enabled"))
    )


@pytest.mark.parametrize("metadata", metadata_styles)
def test_metadata(mock_version, tmp_comic, md_saved, metadata):
    md_style = metadata(mock_version[0])
    supported_attributes = md_style.supported_attributes
    md_style.set_metadata(comicapi.genericmetadata.md_test, tmp_comic.archiver)
    written_metadata = md_style.get_metadata(tmp_comic.archiver)
    md = md_saved.get_clean_metadata(*supported_attributes)

    # Hack back in the pages variable because CoMet supports identifying the cover by the filename
    if md_style.short_name == "comet":
        md.pages = [
            comicapi.genericmetadata.ImageMetadata(
                image_index=0, filename="!cover.jpg", type=comicapi.genericmetadata.PageType.FrontCover
            )
        ]
        written_metadata = written_metadata.get_clean_metadata(*supported_attributes).replace(
            pages=written_metadata.pages
        )
    else:
        written_metadata = written_metadata.get_clean_metadata(*supported_attributes)

    assert written_metadata == md
