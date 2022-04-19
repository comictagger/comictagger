import shutil
from os.path import abspath, dirname, join

import pytest

from comicapi.comicarchive import ComicArchive, rar_support
from comicapi.genericmetadata import GenericMetadata, PageType, md_test

thisdir = dirname(abspath(__file__))


@pytest.mark.xfail(not rar_support, reason="rar support")
def test_getPageNameList():
    ComicArchive.logo_data = b""
    c = ComicArchive(join(thisdir, "data", "fake_cbr.cbr"))
    pageNameList = c.get_page_name_list()

    assert pageNameList == [
        "page0.jpg",
        "Page1.jpeg",
        "Page2.png",
        "Page3.gif",
        "page4.webp",
        "page10.jpg",
    ]


def test_set_default_page_list(tmpdir):
    md = GenericMetadata()
    md.overlay(md_test)
    md.pages = []
    print(md_test.pages, md.pages)
    md.set_default_page_list(len(md_test.pages))

    assert isinstance(md.pages[0]["Image"], int)


def test_page_type():
    c_path = join(thisdir, "data", "Cory Doctorow's Futuristic Tales of the Here and Now #001 - Anda's Game (2007).cbz")
    c = ComicArchive(str(c_path))
    md = c.read_cix()

    assert isinstance(md.pages[0]["Type"], PageType)


def test_save_cix(tmpdir):
    comic_path = tmpdir.mkdir("cbz").join(
        "Cory Doctorow's Futuristic Tales of the Here and Now #001 - Anda's Game (2007).cbz"
    )
    c_path = join(thisdir, "data", "Cory Doctorow's Futuristic Tales of the Here and Now #001 - Anda's Game (2007).cbz")
    shutil.copy(c_path, comic_path)

    c = ComicArchive(str(comic_path))
    md = c.read_cix()
    md.set_default_page_list(c.get_number_of_pages())

    assert c.write_cix(md)

    md = c.read_cix()
