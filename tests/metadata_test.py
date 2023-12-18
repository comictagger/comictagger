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
def test_metadata(mock_version, tmp_comic, md, metadata):
    md_style = metadata(mock_version[0])
    supported_attributes = md_style.supported_attributes
    md_style.set_metadata(comicapi.genericmetadata.md_test, tmp_comic.archiver)
    written_metadata = md_style.get_metadata(tmp_comic.archiver)
    assert written_metadata.get_clean_metadata(*supported_attributes) == md.get_clean_metadata(*supported_attributes)
