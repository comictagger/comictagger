import pytest
from filenames import fnames

import comicapi.filenameparser

# def test_filename_parser():
#     p = comicapi.filenameparser.FileNameParser()
#     p.parse_filename("Cory Doctorows Futuristic Tales of the Here and Now #1 andas game.rar")
#     fp = p.__dict__

#     assert fp["issue"] == "1"
#     assert fp["series"] == "Cory Doctorows Futuristic Tales of the Here and Now"
#     assert fp["remainder"] == "andas game"
#     assert fp["volume"] == ""
#     assert fp["year"] == ""
#     assert fp["issue_count"] == ""


@pytest.mark.parametrize("filename,reason,expected", fnames)
def test_file_name_parser(filename, reason, expected):
    p = comicapi.filenameparser.FileNameParser()
    p.parse_filename(filename)
    fp = p.__dict__
    # del expected["remainder"]
    # del expected["title"]
    # del fp["archive"]
    for s in ["title"]:
        if s in expected:
            # expected[s] = ""
            del expected[s]
        # if s not in fp:
        #     fp[s] = ""

    assert fp == expected
