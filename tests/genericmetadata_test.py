from __future__ import annotations

import pytest

import comicapi.genericmetadata
from testing.comicdata import credits, metadata


def test_set_default_page_list(tmp_path):
    md = comicapi.genericmetadata.GenericMetadata()
    md.overlay(comicapi.genericmetadata.md_test)
    md.pages = []
    md.set_default_page_list(len(comicapi.genericmetadata.md_test.pages))

    assert isinstance(md.pages[0]["Image"], int)


@pytest.mark.parametrize("replaced, expected", metadata)
def test_metadata_overlay(md: comicapi.genericmetadata.GenericMetadata, replaced, expected):
    md.overlay(replaced)

    assert md == expected


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
