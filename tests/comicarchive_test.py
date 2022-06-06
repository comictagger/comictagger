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


def test_set_default_page_list(tmpdir):
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
    md_dict = md.__dict__
    md_test_dict = comicapi.genericmetadata.md_test.__dict__
    assert md_dict == md_test_dict


def test_save_cix(tmpdir):
    comic_path = tmpdir.mkdir("cbz") / cbz_path.name
    print(comic_path)
    shutil.copy(cbz_path, comic_path)

    c = comicapi.comicarchive.ComicArchive(comic_path)
    md = c.read_cix()
    md.set_default_page_list(c.get_number_of_pages())

    assert c.write_cix(md)

    md = c.read_cix()


def test_page_type_save(tmpdir):
    comic_path = tmpdir.mkdir("cbz") / cbz_path.name
    print(comic_path)

    shutil.copy(cbz_path, comic_path)

    c = comicapi.comicarchive.ComicArchive(comic_path)
    md = c.read_cix()
    t = md.pages[0]
    t["Type"] = ""

    assert c.write_cix(md)

    md = c.read_cix()


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
def test_copy_to_archive(archiver, tmpdir):
    comic_path = tmpdir / cbz_path.with_suffix("").name

    cbz = comicapi.comicarchive.ComicArchive(cbz_path)
    archive = archiver(comic_path)

    assert archive.copy_from_archive(cbz.archiver)

    comic_archive = comicapi.comicarchive.ComicArchive(comic_path)

    assert comic_archive.seems_to_be_a_comic_archive()
    assert set(cbz.archiver.get_filename_list()) == set(comic_archive.archiver.get_filename_list())

    md = comic_archive.read_cix()
    md_dict = md.__dict__
    md_test_dict = comicapi.genericmetadata.md_test.__dict__
    assert md_dict == md_test_dict

    md = comicapi.genericmetadata.GenericMetadata()
    md.overlay(comicapi.genericmetadata.md_test)
    md.series = "test"

    assert comic_archive.write_cix(md)

    test_md = comic_archive.read_cix()
    md_dict = md.__dict__
    test_md_dict = test_md.__dict__
    assert md_dict == test_md_dict
