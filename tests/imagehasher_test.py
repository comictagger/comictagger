from __future__ import annotations

from comicapi.comicarchive import ComicArchive
from comicapi.tags.comicrack import ComicRack
from comictaggerlib.imagehasher import ImageHasher


def test_ahash(cbz: ComicArchive):
    md = cbz.read_tags(ComicRack())
    covers = md.get_cover_page_index_list()
    assert covers
    cover = cbz.get_page(covers[0])
    assert cover

    ih = ImageHasher(data=cover)
    assert bin(212201432349720) == bin(ih.average_hash())


def test_dhash(cbz: ComicArchive):
    md = cbz.read_tags(ComicRack())
    covers = md.get_cover_page_index_list()
    assert covers
    cover = cbz.get_page(covers[0])
    assert cover

    ih = ImageHasher(data=cover)
    assert bin(11278294082955047009) == bin(ih.difference_hash())


def test_phash(cbz: ComicArchive):
    md = cbz.read_tags(ComicRack())
    covers = md.get_cover_page_index_list()
    assert covers
    cover = cbz.get_page(covers[0])
    assert cover

    ih = ImageHasher(data=cover)
    assert bin(15307782992485167995) == bin(ih.perception_hash())
