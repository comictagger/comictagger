from __future__ import annotations

import dataclasses

import pytest

import comicapi.genericmetadata


@pytest.fixture
def md():
    yield dataclasses.replace(comicapi.genericmetadata.md_test)


stuff = [
    (
        {"series": "test", "issue": "2", "title": "never"},
        dataclasses.replace(comicapi.genericmetadata.md_test, series="test", issue="2", title="never"),
    ),
    (
        {"series": "", "issue": "2", "title": "never"},
        dataclasses.replace(comicapi.genericmetadata.md_test, series=None, issue="2", title="never"),
    ),
    (
        {},
        dataclasses.replace(comicapi.genericmetadata.md_test),
    ),
]


@pytest.mark.parametrize("replaced, expected", stuff)
def test_metadata_overlay(md: comicapi.genericmetadata.GenericMetadata, replaced, expected):
    md_overlay = comicapi.genericmetadata.GenericMetadata(**replaced)
    md.overlay(md_overlay)

    assert md == expected


def test_add_credit():
    md = comicapi.genericmetadata.GenericMetadata()

    md.add_credit(person="test", role="writer", primary=False)
    md.credits == [{"person": "test", "role": "writer", "primary": False}]


def test_add_credit_primary():
    md = comicapi.genericmetadata.GenericMetadata()

    md.add_credit(person="test", role="writer", primary=False)
    md.add_credit(person="test", role="writer", primary=True)
    md.credits == [{"person": "test", "role": "writer", "primary": True}]


credits = [
    ("writer", "Dara Naraghi"),
    ("writeR", "Dara Naraghi"),
]


@pytest.mark.parametrize("role, expected", credits)
def test_get_primary_credit(md, role, expected):
    assert md.get_primary_credit(role) == expected
