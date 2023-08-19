from __future__ import annotations

import os

import pytest

import comicapi.utils
import comictalker.talker_utils


def test_os_sorted():
    page_name_list = [
        "cover.jpg",
        "Page1.jpeg",
        "!cover.jpg",
        "page4.webp",
        "test/!cover.tar.gz",
        "!cover.tar.gz",
        "00.jpg",
        "ignored.txt",
        "page0.jpg",
        "test/00.tar.gz",
        ".ignored.jpg",
        "Page3.gif",
        "!cover.tar.gz",
        "Page2.png",
        "page10.jpg",
        "!cover",
    ]

    assert comicapi.utils.os_sorted(page_name_list) == [
        "!cover",
        "!cover.jpg",
        "!cover.tar.gz",
        "!cover.tar.gz",  # Depending on locale punctuation or numbers might come first (Linux, MacOS)
        ".ignored.jpg",
        "00.jpg",
        "cover.jpg",
        "ignored.txt",
        "page0.jpg",
        "Page1.jpeg",
        "Page2.png",
        "Page3.gif",
        "page4.webp",
        "page10.jpg",
        "test/!cover.tar.gz",
        "test/00.tar.gz",
    ]


def test_recursive_list_with_file(tmp_path) -> None:
    foo_png = tmp_path / "foo.png"
    foo_png.write_text("not a png")

    temp_folder = tmp_path / "bar"
    temp_folder.mkdir()
    temp_file = temp_folder / "test.cbz"
    temp_file.write_text("not a zip")

    temp_folder2 = tmp_path / "bar" / "baz" / "something else"
    temp_folder2.mkdir(parents=True)
    temp_cbr = temp_folder2 / "bar.cbr"
    temp_cbr.write_text("not a rar")

    temp_txt = tmp_path / "info.txt"
    temp_txt.write_text("this is here")

    temp_txt2 = tmp_path / "info2.txt"
    temp_txt2.write_text("this is here")

    glob_in_name = tmp_path / "[e-b]"
    glob_in_name.mkdir()

    expected_result = {str(foo_png), str(temp_cbr), str(temp_file), str(temp_txt), str(temp_txt2)}
    result = set(comicapi.utils.get_recursive_filelist([str(temp_txt2), tmp_path, str(glob_in_name)]))

    assert result == expected_result


xlate_values = [
    ("", None),
    (None, None),
    ("9", "9"),
    (9, "9"),
]
xlate_int_values = [
    (None, None),
    (" ", None),
    ("", None),
    ("9..", None),
    (9, 9),
    ("9", 9),
    (9.3, 9),
    ("9.3", 9),
    ("9.", 9),
    (" 9 . 3 l", 9),
]
xlate_float_values = [
    (9, 9.0),
    ("9", 9.0),
    (9.3, 9.3),
    ("9.3", 9.3),
    ("9.", 9.0),
    (" 9 . 3 l", 9.3),
]


@pytest.mark.parametrize("value, result", xlate_values)
def test_xlate(value, result):
    assert comicapi.utils.xlate(value) == result


@pytest.mark.parametrize("value, result", xlate_float_values)
def test_xlate_float(value, result):
    assert comicapi.utils.xlate_float(value) == result


@pytest.mark.parametrize("value, result", xlate_int_values)
def test_xlate_int(value, result):
    assert comicapi.utils.xlate_int(value) == result


language_values = [
    ("english", "en"),
    ("ENGLISH", "en"),
    ("EnglisH", "en"),
    ("", ""),
    ("aaa", None),  # does not have a 2-letter code
    (None, None),
]


@pytest.mark.parametrize("value, result", language_values)
def test_get_language_iso(value, result):
    assert result == comicapi.utils.get_language_iso(value)


combine_values = [
    ("hello", "english", "en", "hello\nenglish"),
    ("hello en", "english", "en", "hello english"),
    ("hello en goodbye", "english", "en", "hello english"),
    ("hello en en goodbye", "english", "en", "hello en english"),
    ("", "english", "en", "english"),
    (None, "english", "en", "english"),
    ("hello", "", "en", "hello"),
    ("hello", None, "en", "hello"),
    ("hello", "hello", "hel", "hello"),
]


@pytest.mark.parametrize("existing_notes, new_notes, split, result", combine_values)
def test_combine_notes(existing_notes, new_notes, split, result):
    assert result == comicapi.utils.combine_notes(existing_notes, new_notes, split)


def test_unique_file(tmp_path):
    file = tmp_path / "test.cbz"
    assert file == comicapi.utils.unique_file(file)

    file.mkdir()
    assert (tmp_path / "test (1).cbz") == comicapi.utils.unique_file(file)


def test_add_to_path(monkeypatch):
    monkeypatch.setenv("PATH", os.path.abspath("/usr/bin"))
    comicapi.utils.add_to_path("/bin")
    assert os.environ["PATH"] == (os.path.abspath("/bin") + os.pathsep + os.path.abspath("/usr/bin"))

    comicapi.utils.add_to_path("/usr/bin")
    comicapi.utils.add_to_path("/usr/bin/")
    assert os.environ["PATH"] == (os.path.abspath("/bin") + os.pathsep + os.path.abspath("/usr/bin"))


titles = [
    (("", ""), True),
    (("Conan el Barbaro", "Conan el Bárbaro"), True),
    (("鋼の錬金術師", "鋼の錬金術師"), True),
    (("钢之炼金术师", "鋼の錬金術師"), False),
    (("batmans grave", "The Batman's Grave"), True),
    (("batman grave", "The Batman's Grave"), True),
    (("bats grave", "The Batman's Grave"), False),
]


@pytest.mark.parametrize("value, result", titles)
def test_titles_match(value, result):
    assert comicapi.utils.titles_match(value[0], value[1]) == result


titles_2 = [
    ("", ""),
    ("鋼の錬金術師", "鋼の錬金術師"),
    ("Conan el Bárbaro", "Conan el Barbaro"),
    ("The Batman's Grave", "batmans grave"),
    ("A+X", "ax"),
    ("ms. marvel", "ms marvel"),
    ("spider-man/deadpool", "spider man deadpool"),
]


@pytest.mark.parametrize("value, result", titles_2)
def test_sanitize_title(value, result):
    assert comicapi.utils.sanitize_title(value) == result.casefold()


urls = [
    ("", ""),
    ("http://test.test", "http://test.test/"),
    ("http://test.test/", "http://test.test/"),
    ("http://test.test/..", "http://test.test/"),
    ("http://test.test/../hello", "http://test.test/hello/"),
    ("http://test.test/../hello/", "http://test.test/hello/"),
    ("http://test.test/../hello/..", "http://test.test/"),
    ("http://test.test/../hello/../", "http://test.test/"),
]


@pytest.mark.parametrize("value, result", urls)
def test_fix_url(value, result):
    assert comictalker.talker_utils.fix_url(value) == result


split = [
    (("1,2,,3", ","), ["1", "2", "3"]),
    (("1 ,2,,3", ","), ["1", "2", "3"]),
    (("1 ,2,,3 ", ","), ["1", "2", "3"]),
    (("\n1 \n2\n\n3 ", ","), ["1 \n2\n\n3"]),
    (("\n1 \n2\n\n3 ", "\n"), ["1", "2", "3"]),
    ((None, ","), []),
]


@pytest.mark.parametrize("value, result", split)
def test_split(value, result):
    assert comicapi.utils.split(*value) == result
