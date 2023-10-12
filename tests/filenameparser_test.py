from __future__ import annotations

import pytest

import comicapi.filenamelexer
import comicapi.filenameparser
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

    for s in ["archive"]:
        if s in fp:
            del fp[s]
    for s in ["alternate", "publisher", "volume_count"]:
        if s not in expected:
            expected[s] = ""
    for s in ["fcbd", "c2c", "annual"]:
        if s not in expected:
            expected[s] = False

    assert fp == expected


@pytest.mark.parametrize("filename, reason, expected, xfail", oldfnames)
def test_file_name_parser(filename, reason, expected, xfail):
    p = comicapi.filenameparser.FileNameParser()
    p.parse_filename(filename)
    fp = p.__dict__
    # These are currently not tracked in this parser
    for s in ["title", "alternate", "publisher", "fcbd", "c2c", "annual", "volume_count", "remainder", "format"]:
        if s in expected:
            del expected[s]

    # The remainder is not considered compatible between parsers
    if "remainder" in fp:
        del fp["remainder"]

    assert fp == expected
