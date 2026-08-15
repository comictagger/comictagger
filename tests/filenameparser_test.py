from __future__ import annotations

import pytest

import comicapi.filenamelexer
import comicapi.filenameparser
import comicapi.utils
from testing.filenames import newfnames, oldfnames


@pytest.mark.parametrize("filename, reason, expected, xfail", newfnames)
def test_file_name_parser_new(filename, reason, expected, xfail):
    lex = comicapi.filenamelexer.Lex(filename, "protofolius_issue_number_scheme" == reason)
    p = comicapi.filenameparser.Parse(
        lex.items,
        first_is_alt=True,
        remove_c2c=True,
        remove_fcbd=True,
        remove_publisher=True,
        protofolius_issue_number_scheme="protofolius_issue_number_scheme" == reason,
    )
    fp = p.filename_info

    assert fp == expected


@pytest.mark.parametrize("filename, reason, expected, xfail", oldfnames)
def test_file_name_parser(filename, reason, expected, xfail):
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
