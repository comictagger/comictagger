from __future__ import annotations

import pathlib
import shutil

import pytest

import comicapi.comicarchive
import comicapi.genericmetadata

thisdir = pathlib.Path(__file__).parent
cbz_path = thisdir / "data" / "Cory Doctorow's Futuristic Tales of the Here and Now #001 - Anda's Game (2007).cbz"


@pytest.mark.xfail(not comicapi.comicarchive.rar_support, reason="rar support")
def test_getPageNameList():
    c = comicapi.comicarchive.ComicArchive(thisdir / "data" / "fake_cbr.cbr")
    pageNameList = c.get_page_name_list()

    assert pageNameList == [
        "page0.jpg",
        "Page1.jpeg",
        "Page2.png",
        "Page3.gif",
        "page4.webp",
        "page10.jpg",
    ]


def test_set_default_page_list(tmp_path):
    md = comicapi.genericmetadata.GenericMetadata()
    md.overlay(comicapi.genericmetadata.md_test)
    md.pages = []
    md.set_default_page_list(len(comicapi.genericmetadata.md_test.pages))

    assert isinstance(md.pages[0]["Image"], int)


def test_page_type_read():
    c = comicapi.comicarchive.ComicArchive(cbz_path)
    md = c.read_cix()

    assert isinstance(md.pages[0]["Type"], str)


def test_metadata_read():
    c = comicapi.comicarchive.ComicArchive(
        thisdir / "data" / "Cory Doctorow's Futuristic Tales of the Here and Now #001 - Anda's Game (2007).cbz"
    )
    md = c.read_cix()
    assert md == comicapi.genericmetadata.md_test


def test_save_cix(tmp_path):
    comic_path = tmp_path / cbz_path.name
    shutil.copy(cbz_path, comic_path)

    c = comicapi.comicarchive.ComicArchive(comic_path)
    md = c.read_cix()
    md.set_default_page_list(c.get_number_of_pages())

    assert c.write_cix(md)

    md = c.read_cix()


def test_page_type_save(tmp_path):
    comic_path = tmp_path / cbz_path.name

    shutil.copy(cbz_path, comic_path)

    c = comicapi.comicarchive.ComicArchive(comic_path)
    md = c.read_cix()
    t = md.pages[0]
    t["Type"] = ""

    assert c.write_cix(md)

    md = c.read_cix()


def test_invalid_zip(tmp_path):
    comic_path = tmp_path / cbz_path.name

    with open(cbz_path, mode="b+r") as f:
        comic_path.write_bytes(b"PK\003\004" + f.read()[4:].replace(b"PK\003\004", b"PK\000\000"))

    c = comicapi.comicarchive.ComicArchive(comic_path)

    assert not c.write_cix(comicapi.genericmetadata.md_test)


archivers = [
    comicapi.comicarchive.ZipArchiver,
    comicapi.comicarchive.SevenZipArchiver,
    comicapi.comicarchive.FolderArchiver,
    pytest.param(
        comicapi.comicarchive.RarArchiver,
        marks=pytest.mark.xfail(not (comicapi.comicarchive.rar_support and shutil.which("rar")), reason="rar support"),
    ),
]


@pytest.mark.parametrize("archiver", archivers)
def test_copy_to_archive(archiver, tmp_path):
    comic_path = tmp_path / cbz_path.with_suffix("").name

    cbz = comicapi.comicarchive.ComicArchive(cbz_path)
    archive = archiver(comic_path)

    assert archive.copy_from_archive(cbz.archiver)

    comic_archive = comicapi.comicarchive.ComicArchive(comic_path)

    assert comic_archive.seems_to_be_a_comic_archive()
    assert set(cbz.archiver.get_filename_list()) == set(comic_archive.archiver.get_filename_list())

    md = comic_archive.read_cix()
    assert md == comicapi.genericmetadata.md_test

    md = comicapi.genericmetadata.GenericMetadata()
    md.overlay(comicapi.genericmetadata.md_test)
    md.series = "test"

    assert comic_archive.write_cix(md)

    test_md = comic_archive.read_cix()
    assert md == test_md
