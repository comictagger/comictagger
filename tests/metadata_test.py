from __future__ import annotations

import comicapi.comicbookinfo
import comicapi.comicinfoxml
import comicapi.genericmetadata


def test_cix(md_saved):
    CIX = comicapi.comicinfoxml.ComicInfoXml()
    string = CIX.string_from_metadata(comicapi.genericmetadata.md_test)
    md = CIX.metadata_from_string(string)
    assert md == md_saved


def test_cbi(md_saved):
    CBI = comicapi.comicbookinfo.ComicBookInfo()
    string = CBI.string_from_metadata(comicapi.genericmetadata.md_test)
    md = CBI.metadata_from_string(string)
    md_test = md_saved.replace(
        day=None,
        page_count=None,
        maturity_rating=None,
        story_arcs=[],
        series_groups=[],
        scan_info=None,
        characters=[],
        teams=[],
        locations=[],
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


def test_comet(md_saved):
    CBI = comicapi.comet.CoMet()
    string = CBI.string_from_metadata(comicapi.genericmetadata.md_test)
    md = CBI.metadata_from_string(string)
    md_test = md_saved.replace(
        day=None,
        story_arcs=[],
        series_groups=[],
        scan_info=None,
        teams=[],
        locations=[],
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
