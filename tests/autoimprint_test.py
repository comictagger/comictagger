from __future__ import annotations

import pytest

from comicapi import utils

imprints = [
    ("marvel", ("", "Marvel")),
    ("marvel comics", ("", "Marvel")),
    ("aircel", ("Aircel Comics", "Marvel")),
]

additional_imprints = [
    ("test", ("Test", "Marvel")),
    ("temp", ("Temp", "DC Comics")),
]

all_imprints = imprints + additional_imprints

seed = {
    "Marvel": utils.ImprintDict(
        "Marvel",
        {
            "marvel comics": "",
            "aircel": "Aircel Comics",
        },
    )
}

additional_seed = {
    "Marvel": utils.ImprintDict("Marvel", {"test": "Test"}),
    "DC Comics": utils.ImprintDict("DC Comics", {"temp": "Temp"}),
}

all_seed = {
    "Marvel": seed["Marvel"].copy(),
    "DC Comics": additional_seed["DC Comics"].copy(),
}
all_seed["Marvel"].update(additional_seed["Marvel"])

conflicting_seed = {"Marvel": {"test": "Never"}}


# manually seeds publishers
@pytest.fixture
def seed_publishers(monkeypatch):
    publisher_seed = {}
    for publisher, imprint in seed.items():
        publisher_seed[publisher] = imprint
    monkeypatch.setattr(utils, "publishers", publisher_seed)


@pytest.fixture
def seed_all_publishers(monkeypatch):
    publisher_seed = {}
    for publisher, imprint in all_seed.items():
        publisher_seed[publisher] = imprint
    monkeypatch.setattr(utils, "publishers", publisher_seed)


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
    utils.update_publishers(seed)
    assert expected == utils.get_publisher(publisher)


# tests that update_publishers will add to existing values
@pytest.mark.parametrize("publisher, expected", all_imprints)
def test_update_publisher(publisher: str, expected: tuple[str, str], seed_publishers):
    utils.update_publishers(additional_seed)
    assert expected == utils.get_publisher(publisher)


# tests that update_publishers will overwrite conflicting existing values
def test_conflict_publisher(seed_all_publishers):
    assert ("Test", "Marvel") == utils.get_publisher("test")

    utils.update_publishers(conflicting_seed)

    assert ("Never", "Marvel") == utils.get_publisher("test")
