from __future__ import annotations

import pytest

from comicapi import utils
from testing.comicdata import additional_seed_imprints, all_imprints, conflicting_seed_imprints, imprints, seed_imprints


# test that that an empty list returns the input unchanged
@pytest.mark.parametrize("publisher, expected", imprints)
def test_get_publisher_empty(publisher: str, expected: tuple[str, str]):
    assert ("", publisher) == utils.get_publisher(publisher)


# initial test
@pytest.mark.parametrize("publisher, expected", imprints)
def test_get_publisher(publisher: str, expected: tuple[str, str], seed_publishers):
    assert expected == utils.get_publisher(publisher)


# tests that update_publishers will initially set values
@pytest.mark.parametrize("publisher, expected", imprints)
def test_set_publisher(publisher: str, expected: tuple[str, str]):
    utils.update_publishers(seed_imprints)
    assert expected == utils.get_publisher(publisher)


# tests that update_publishers will add to existing values
@pytest.mark.parametrize("publisher, expected", all_imprints)
def test_update_publisher(publisher: str, expected: tuple[str, str], seed_publishers):
    utils.update_publishers(additional_seed_imprints)
    assert expected == utils.get_publisher(publisher)


# tests that update_publishers will overwrite conflicting existing values
def test_conflict_publisher(seed_all_publishers):
    assert ("Test", "Marvel") == utils.get_publisher("test")

    utils.update_publishers(conflicting_seed_imprints)

    assert ("Never", "Marvel") == utils.get_publisher("test")
