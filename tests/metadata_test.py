from __future__ import annotations

import comicapi.comicbookinfo
import comicapi.comicinfoxml
import comicapi.genericmetadata


def test_cix():
    CIX = comicapi.comicinfoxml.ComicInfoXml()
    string = CIX.string_from_metadata(comicapi.genericmetadata.md_test)
    md = CIX.metadata_from_string(string)
    assert md == comicapi.genericmetadata.md_test


def test_cbi():
    CBI = comicapi.comicbookinfo.ComicBookInfo()
    string = CBI.string_from_metadata(comicapi.genericmetadata.md_test)
    md = CBI.metadata_from_string(string)
    md_test = comicapi.genericmetadata.md_test.replace(
        day=None,
        page_count=None,
        maturity_rating=None,
        story_arc=None,
        series_group=None,
        scan_info=None,
        characters=None,
        teams=None,
        locations=None,
        pages=[],
        alternate_series=None,
        alternate_number=None,
        alternate_count=None,
        imprint=None,
        notes=None,
        web_link=None,
        format=None,
        manga=None,
    )
    assert md == md_test


def test_comet():
    CBI = comicapi.comet.CoMet()
    string = CBI.string_from_metadata(comicapi.genericmetadata.md_test)
    md = CBI.metadata_from_string(string)
    md_test = comicapi.genericmetadata.md_test.replace(
        day=None,
        story_arc=None,
        series_group=None,
        scan_info=None,
        teams=None,
        locations=None,
        pages=[],
        alternate_series=None,
        alternate_number=None,
        alternate_count=None,
        imprint=None,
        notes=None,
        web_link=None,
        manga=None,
        critical_rating=None,
        issue_count=None,
    )
    assert md == md_test
