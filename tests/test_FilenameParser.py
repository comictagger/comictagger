import pytest
from filenames import fnames

import comicapi.filenameparser


@pytest.mark.parametrize("filename,reason,expected", fnames)
def test_file_name_parser(filename, reason, expected):
    p = comicapi.filenameparser.FileNameParser()
    p.parse_filename(filename)
    fp = p.__dict__
    for s in ["title"]:
        if s in expected:
            del expected[s]

    assert fp == expected
