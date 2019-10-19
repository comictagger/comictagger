from os.path import dirname, abspath, join
from comicapi.comicarchive import ComicArchive

__dir__ = dirname(abspath(__file__))

def test_getPageNameList():
    ComicArchive.logo_data = b''
    c = ComicArchive(join(__dir__, "fake_cbr.cbr"))
    pageNameList = c.getPageNameList()

    assert pageNameList == [
        "page0.jpg",
        "Page1.jpeg",
        "Page2.png",
        "Page3.gif",
        "page4.webp",
        "page10.jpg"
    ]