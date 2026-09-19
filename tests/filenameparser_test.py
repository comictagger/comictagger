from __future__ import annotations

import pytest

import comicapi.filenamelexer
import comicapi.filenameparser
import comicapi.utils
from testing.filenames import newfnames, oldfnames


@pytest.mark.parametrize("filename, reason, expected", newfnames)
def test_complicated_file_name_parser(filename, reason, expected, load_publishers):
    protofolius_issue_number_scheme = bool(expected["issue"] and expected["issue"][0].isalpha())
    lex = comicapi.filenamelexer.Lex(filename, protofolius_issue_number_scheme, load_publishers.publishers)
    p = comicapi.filenameparser.Parse(
        lex.items,
        first_is_alt=True,
        remove_c2c=True,
        remove_fcbd=True,
        remove_publisher=True,
        protofolius_issue_number_scheme=protofolius_issue_number_scheme,
    )
    fp = p.filename_info

    assert fp == expected


@pytest.mark.parametrize("filename, reason, expected", oldfnames)
def test_original_file_name_parser(filename, reason, expected):
    fp = comicapi.utils.parse_filename(filename)
    # These are currently not tracked in this parser
    for s in [
        "title",
        "alternate",
        "publisher",
        "fcbd",
        "c2c",
        "annual",
        "volume_count",
        "remainder",
        "format",
        "archive",
    ]:
        del expected[s]
        del fp[s]

    assert fp == expected
