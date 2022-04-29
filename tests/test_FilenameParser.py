import pytest
from filenames import fnames

import comicapi.filenameparser


@pytest.mark.parametrize("filename,reason,expected", fnames)
def test_file_name_parser_new(filename, reason, expected):
    p = comicapi.filenameparser.Parse(
        comicapi.filenamelexer.Lex(filename).items,
        first_is_alt=True,
        remove_c2c=True,
        remove_fcbd=True,
        remove_publisher=True,
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


@pytest.mark.parametrize("filename,reason,expected", fnames)
def test_file_name_parser(filename, reason, expected):
    p = comicapi.filenameparser.FileNameParser()
    p.parse_filename(filename)
    fp = p.__dict__
    for s in ["title", "alternate", "publisher", "fcbd", "c2c", "annual", "volume_count"]:
        if s in expected:
            del expected[s]

    if fp != expected:
        pytest.xfail("old parser")
    assert fp == expected
