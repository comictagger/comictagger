from __future__ import annotations

import platform
import shutil

import pytest

import comicapi.comicarchive
import comicapi.genericmetadata
from testing.filenames import datadir


@pytest.mark.xfail(not comicapi.comicarchive.rar_support, reason="rar support")
def test_getPageNameList():
    c = comicapi.comicarchive.ComicArchive(datadir / "fake_cbr.cbr")
    pageNameList = c.get_page_name_list()

    assert pageNameList == [
        "!cover.jpg",
        "00.jpg",
        "page0.jpg",
        "Page1.jpeg",
        "Page2.png",
        "Page3.gif",
        "page4.webp",
        "page10.jpg",
    ]


def test_page_type_read(cbz):
    md = cbz.read_cix()

    assert isinstance(md.pages[0]["Type"], str)


def test_metadata_read(cbz):
    md = cbz.read_cix()
    assert md == comicapi.genericmetadata.md_test


def test_save_cix(tmp_comic):
    md = tmp_comic.read_cix()
    md.set_default_page_list(tmp_comic.get_number_of_pages())

    assert tmp_comic.write_cix(md)

    md = tmp_comic.read_cix()


def test_save_cbi(tmp_comic):
    md = tmp_comic.read_cix()
    md.set_default_page_list(tmp_comic.get_number_of_pages())

    assert tmp_comic.write_cbi(md)

    md = tmp_comic.read_cbi()


def test_save_cix_rar(tmp_path):
    cbr_path = datadir / "fake_cbr.cbr"
    shutil.copy(cbr_path, tmp_path)

    tmp_comic = comicapi.comicarchive.ComicArchive(tmp_path / cbr_path.name)
    assert tmp_comic.write_cix(comicapi.genericmetadata.md_test)

    md = tmp_comic.read_cix()
    assert md.replace(pages=[]) == comicapi.genericmetadata.md_test.replace(pages=[])


def test_save_cbi_rar(tmp_path):
    cbr_path = datadir / "fake_cbr.cbr"
    shutil.copy(cbr_path, tmp_path)

    tmp_comic = comicapi.comicarchive.ComicArchive(tmp_path / cbr_path.name)
    assert tmp_comic.write_cbi(comicapi.genericmetadata.md_test)

    md = tmp_comic.read_cbi()
    assert md.replace(pages=[]) == comicapi.genericmetadata.md_test.replace(
        pages=[],
        day=None,
        alternate_series=None,
        alternate_number=None,
        alternate_count=None,
        imprint=None,
        notes=None,
        web_link=None,
        format=None,
        manga=None,
        page_count=None,
        maturity_rating=None,
        story_arc=None,
        series_group=None,
        scan_info=None,
        characters=None,
        teams=None,
        locations=None,
    )


def test_page_type_save(tmp_comic):
    md = tmp_comic.read_cix()
    t = md.pages[0]
    t["Type"] = ""

    assert tmp_comic.write_cix(md)

    md = tmp_comic.read_cix()


def test_invalid_zip(tmp_comic):
    with open(tmp_comic.path, mode="b+r") as f:
        f.write(b"PK\000\000")

    result = tmp_comic.write_cix(comicapi.genericmetadata.md_test)
    assert not result


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
def test_copy_from_archive(archiver, tmp_path, cbz):
    comic_path = tmp_path / cbz.path.with_suffix("").name

    archive = archiver(comic_path)

    assert archive.copy_from_archive(cbz.archiver)

    comic_archive = comicapi.comicarchive.ComicArchive(comic_path)

    assert comic_archive.seems_to_be_a_comic_archive()
    assert set(cbz.archiver.get_filename_list()) == set(comic_archive.archiver.get_filename_list())

    md = comic_archive.read_cix()
    assert md == comicapi.genericmetadata.md_test


def test_rename(tmp_comic, tmp_path):
    old_path = tmp_comic.path
    tmp_comic.rename(tmp_path / "test.cbz")
    assert not old_path.exists()
    assert tmp_comic.path.exists()
    assert tmp_comic.path != old_path


def test_rename_ro_dest(tmp_comic, tmp_path):
    old_path = tmp_comic.path
    dest = tmp_path / "tmp"
    dest.mkdir(mode=0o000)
    with pytest.raises(OSError):
        if platform.system() == "Windows":
            raise OSError("Windows sucks")
        tmp_comic.rename(dest / "test.cbz")
    dest.chmod(mode=0o777)
    assert old_path.exists()
    assert tmp_comic.path.exists()
    assert tmp_comic.path == old_path
