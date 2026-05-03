from __future__ import annotations

import os
import pathlib
import platform
import shutil
from contextlib import nullcontext as does_not_raise

import pytest
from importlib_metadata import entry_points

import comicapi.comic.rar
import comicapi.comicarchive
import comicapi.genericmetadata
import comicapi.tags
import comicapi.tags.comicrack
import comictaggerlib.ctversion
from testing.filenames import datadir


@pytest.mark.xfail(not comicapi.comic.rar.rar_support, reason="rar support")
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
    md = cbz.read_tags(comicapi.tags.comicrack.ComicRack())

    assert md.pages[0].type == comicapi.genericmetadata.PageType.FrontCover


def test_read_tags(cbz, md_saved):
    md = cbz.read_tags(comicapi.tags.comicrack.ComicRack())
    assert md == md_saved


def test_write_cr(tmp_comic_path):
    tmp_comic = comicapi.comicarchive.ComicArchive(tmp_comic_path)
    md = tmp_comic.read_tags(comicapi.tags.comicrack.ComicRack())
    md.apply_default_page_list(tmp_comic.get_page_name_list())

    with does_not_raise():
        tmp_comic.write_tags(comictaggerlib.ctversion.version, md, comicapi.tags.comicrack.ComicRack())

    md = tmp_comic.read_tags(comicapi.tags.comicrack.ComicRack())


@pytest.mark.xfail(not (comicapi.comic.rar.rar_support and shutil.which("rar")), reason="rar support")
def test_save_cr_rar(tmp_path, md_saved, md):
    cbr_path = datadir / "fake_cbr.cbr"
    shutil.copy(cbr_path, tmp_path)

    tmp_comic = comicapi.comicarchive.ComicArchive(tmp_path / cbr_path.name)
    assert tmp_comic.seems_to_be_a_comic_archive()
    with does_not_raise():
        tmp_comic.write_tags(comictaggerlib.ctversion.version, md, comicapi.tags.comicrack.ComicRack())

    new_md = tmp_comic.read_tags(comicapi.tags.comicrack.ComicRack())

    # This is a fake CBR we don't need to care about the pages for this test
    new_md.pages = []
    md_saved.pages = []
    assert new_md == md_saved


def test_page_type_write(tmp_comic_path):
    tmp_comic = comicapi.comicarchive.ComicArchive(tmp_comic_path)
    md = tmp_comic.read_tags(comicapi.tags.comicrack.ComicRack())
    t = md.pages[0]
    t.type = ""

    with does_not_raise():
        tmp_comic.write_tags(comictaggerlib.ctversion.version, md, comicapi.tags.comicrack.ComicRack())

    md = tmp_comic.read_tags(comicapi.tags.comicrack.ComicRack())


def test_invalid_zip(tmp_comic_path, md):
    with open(tmp_comic_path, mode="b+r") as f:
        # Corrupting the first file only breaks the first file. If it is never read then no exception will be raised
        f.seek(-30, os.SEEK_END)  # seek to a probably bad place in th Central Directory and write some bytes
        f.write(b"PK\000\000\000\000\000\000\000\000\000\000\000\000\000\000\000\000\000\000\000\000")

    tmp_comic = comicapi.comicarchive.ComicArchive(tmp_comic_path)
    # assert tmp_comic.Archiver is comicapi.comicarchive.UnknownArchiver
    with pytest.raises(Exception, match="tags Not Supported for Comic"):
        tmp_comic.write_tags(
            comictaggerlib.ctversion.version, md, comicapi.tags.comicrack.ComicRack()
        )  # This is not the first file
    assert not tmp_comic.seems_to_be_a_comic_archive()  # Calls archiver.is_valid
    with pytest.raises(comicapi.comic.BadComic, match="^Unable to open zip file"):
        comicapi.comic.ZipComic(tmp_comic_path).validate_comic()


def test_invalid_zip_partial_corruption(tmp_comic_path, md):
    with open(tmp_comic_path, mode="b+r") as f:
        f.seek(-10, os.SEEK_END)  # seek to a probably bad place in th Central Directory and write some bytes
        f.write(b"PK\000\000\000\000\000\000\000\000\000\000\000\000\000\000\000\000\000\000\000\000")

    tmp_comic = comicapi.comicarchive.ComicArchive(tmp_comic_path)
    # assert tmp_comic.Archiver is comicapi.comicarchive.UnknownArchiver
    with pytest.raises(comicapi.comic.BadComic, match="^Error listing files in zip archive"):
        tmp_comic.write_tags(
            comictaggerlib.ctversion.version, md, comicapi.tags.comicrack.ComicRack()
        )  # This is not the first file
    assert not tmp_comic.seems_to_be_a_comic_archive()  # Calls archiver.is_valid
    with pytest.raises(comicapi.comic.BadComic, match="^Unable to open zip file"):
        comicapi.comic.ZipComic(tmp_comic_path).validate_comic()


def test_invalid_zip_file_header_corruption(tmp_comic_path, md):
    with open(tmp_comic_path, mode="b+r") as f:
        f.write(b"PK\000\000\000\000\000\000\000\000\000\000\000\000\000\000\000\000\000\000\000\000")

    tmp_comic = comicapi.comicarchive.ComicArchive(tmp_comic_path)
    # assert tmp_comic.Archiver is comicapi.comicarchive.UnknownArchiver
    with pytest.raises(comicapi.comic.BadComic, match="^Error writing zip archive"):
        tmp_comic.write_tags(
            comictaggerlib.ctversion.version, md, comicapi.tags.comicrack.ComicRack()
        )  # This is not the first file
    assert tmp_comic.seems_to_be_a_comic_archive()  # Calls archiver.is_valid. Does not verify individual files
    with pytest.raises(comicapi.comic.BadComic, match="^Error testing files in zip archive"):
        comicapi.comic.ZipComic(tmp_comic_path).validate_comic()


archivers = []

for x in entry_points(group="comicapi.archiver"):
    archiver: comicapi.comic.ComicFile = x.load()
    supported = archiver.enabled
    exe_found = True
    if archiver.exe != "":
        exe_found = bool(shutil.which(archiver.exe))
    archivers.append(
        pytest.param(archiver, marks=pytest.mark.xfail(not (supported and exe_found), reason="archiver not enabled"))
    )


def export(existing: comicapi.comic.ComicFile, new: comicapi.comic.ComicFile) -> None:
    """
    Copies all content from the current archive to
    """
    new.write_files(files=existing.read_files(existing.get_filename_list()), filenames=existing.get_filename_list())

    if (
        comicapi.tags.TagLocation.COMMENT in new.tag_locations
        and comicapi.tags.TagLocation.COMMENT in existing.tag_locations
    ):
        new.write_comment(existing.read_comment())


@pytest.mark.parametrize("archiver", archivers)
def test_copy_from_archive(archiver, tmp_path, cbz, md_saved):
    comic_path = tmp_path / cbz.path.with_suffix(f".new{archiver.extension}").name

    archive = archiver(comic_path)

    with does_not_raise():
        export(existing=cbz.Archiver(cbz.path), new=archive)

    comic_archive = comicapi.comicarchive.ComicArchive(comic_path)

    assert comic_archive.seems_to_be_a_comic_archive()
    assert set(cbz.Archiver(cbz.path).get_filename_list()) == set(comic_archive.archiver.get_filename_list())

    md = comic_archive.read_tags(comicapi.tags.comicrack.ComicRack)
    assert md == md_saved


def test_rename(tmp_comic_path, tmp_path):
    tmp_comic = comicapi.comicarchive.ComicArchive(tmp_comic_path)
    old_path = tmp_comic.path
    tmp_comic.rename(tmp_path / "test.cbz")
    assert not old_path.exists()
    assert tmp_comic.path.exists()
    assert tmp_comic.path != old_path


def test_rename_ro_dest(tmp_comic_path, tmp_path):
    tmp_comic = comicapi.comicarchive.ComicArchive(tmp_comic_path)

    dest = tmp_path / "tmp"
    dest.mkdir(mode=0o000)
    with pytest.raises(OSError):
        if platform.system() == "Windows":
            raise OSError("Windows sucks")
        tmp_comic.rename(dest / "test.cbz")
    dest.chmod(mode=0o777)
    assert tmp_comic_path.exists()
    assert tmp_comic.path.exists()
    assert tmp_comic.path == tmp_comic_path
