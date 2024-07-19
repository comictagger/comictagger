from __future__ import annotations

import pathlib
import platform
import shutil

import pytest
from importlib_metadata import entry_points

import comicapi.archivers.rar
import comicapi.comicarchive
import comicapi.genericmetadata
from testing.filenames import datadir


@pytest.mark.xfail(not comicapi.archivers.rar.rar_support, reason="rar support")
def test_getPageNameList():
    c = comicapi.comicarchive.ComicArchive(pathlib.Path(str(datadir)) / "fake_cbr.cbr")
    assert c.seems_to_be_a_comic_archive()
    pageNameList = c.get_page_name_list()

    assert pageNameList == [
        "!cover.jpg",  # Depending on locale punctuation or numbers might come first (Linux)
        "00.jpg",
        "page0.jpg",
        "Page1.jpeg",
        "Page2.png",
        "Page3.gif",
        "page4.webp",
        "page10.jpg",
    ]


def test_page_type_read(cbz):
    md = cbz.read_tags("cr")

    assert md.pages[0].type == comicapi.genericmetadata.PageType.FrontCover


def test_read_tags(cbz, md_saved):
    md = cbz.read_tags("cr")
    assert md == md_saved


def test_write_cr(tmp_comic):
    md = tmp_comic.read_tags("cr")
    md.apply_default_page_list(tmp_comic.get_page_name_list())

    assert tmp_comic.write_tags(md, "cr")

    md = tmp_comic.read_tags("cr")


def test_write_cbi(tmp_comic):
    md = tmp_comic.read_tags("cr")
    md.apply_default_page_list(tmp_comic.get_page_name_list())

    assert tmp_comic.write_tags(md, "cbi")

    md = tmp_comic.read_tags("cbi")


@pytest.mark.xfail(not (comicapi.archivers.rar.rar_support and shutil.which("rar")), reason="rar support")
def test_save_cr_rar(tmp_path, md_saved):
    cbr_path = datadir / "fake_cbr.cbr"
    shutil.copy(cbr_path, tmp_path)

    tmp_comic = comicapi.comicarchive.ComicArchive(tmp_path / cbr_path.name)
    assert tmp_comic.seems_to_be_a_comic_archive()
    assert tmp_comic.write_tags(comicapi.genericmetadata.md_test, "cr")

    md = tmp_comic.read_tags("cr")

    # This is a fake CBR we don't need to care about the pages for this test
    md.pages = []
    md_saved.pages = []
    assert md == md_saved


@pytest.mark.xfail(not (comicapi.archivers.rar.rar_support and shutil.which("rar")), reason="rar support")
def test_save_cbi_rar(tmp_path, md_saved):
    cbr_path = pathlib.Path(str(datadir)) / "fake_cbr.cbr"
    shutil.copy(cbr_path, tmp_path)

    tmp_comic = comicapi.comicarchive.ComicArchive(tmp_path / cbr_path.name)
    assert tmp_comic.seems_to_be_a_comic_archive()
    assert tmp_comic.write_tags(comicapi.genericmetadata.md_test, "cbi")

    md = tmp_comic.read_tags("cbi")
    supported_attributes = comicapi.comicarchive.tags["cbi"].supported_attributes
    assert md.get_clean_metadata(*supported_attributes) == md_saved.get_clean_metadata(*supported_attributes)


def test_page_type_write(tmp_comic):
    md = tmp_comic.read_tags("cr")
    t = md.pages[0]
    t.type = ""

    assert tmp_comic.write_tags(md, "cr")

    md = tmp_comic.read_tags("cr")


def test_invalid_zip(tmp_comic):
    with open(tmp_comic.path, mode="b+r") as f:
        f.write(b"PK\000\000")

    result = tmp_comic.write_tags(comicapi.genericmetadata.md_test, "cr")
    assert not result


archivers = []

for x in entry_points(group="comicapi.archiver"):
    archiver = x.load()
    supported = archiver.enabled
    exe_found = True
    if archiver.exe != "":
        exe_found = bool(shutil.which(archiver.exe))
    archivers.append(
        pytest.param(archiver, marks=pytest.mark.xfail(not (supported and exe_found), reason="archiver not enabled"))
    )


@pytest.mark.parametrize("archiver", archivers)
def test_copy_from_archive(archiver, tmp_path, cbz, md_saved):
    comic_path = tmp_path / cbz.path.with_suffix("").name

    archive = archiver.open(comic_path)

    assert archive.copy_from_archive(cbz.archiver)

    comic_archive = comicapi.comicarchive.ComicArchive(comic_path)

    assert comic_archive.seems_to_be_a_comic_archive()
    assert set(cbz.archiver.get_filename_list()) == set(comic_archive.archiver.get_filename_list())

    md = comic_archive.read_tags("cr")
    assert md == md_saved


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
