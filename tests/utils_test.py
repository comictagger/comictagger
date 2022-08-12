from __future__ import annotations

import os

import pytest

import comicapi.utils


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

    expected_result = {str(foo_png), str(temp_cbr), str(temp_file), str(temp_txt), str(temp_txt2)}
    result = set(comicapi.utils.get_recursive_filelist([str(temp_txt2), tmp_path]))

    assert result == expected_result


xlate_values = [
    ({"data": "", "is_int": False, "is_float": False}, None),
    ({"data": None, "is_int": False, "is_float": False}, None),
    ({"data": None, "is_int": True, "is_float": False}, None),
    ({"data": " ", "is_int": True, "is_float": False}, None),
    ({"data": "", "is_int": True, "is_float": False}, None),
    ({"data": "9..", "is_int": True, "is_float": False}, None),
    ({"data": "9", "is_int": False, "is_float": False}, "9"),
    ({"data": 9, "is_int": False, "is_float": False}, "9"),
    ({"data": 9, "is_int": True, "is_float": False}, 9),
    ({"data": "9", "is_int": True, "is_float": False}, 9),
    ({"data": 9.3, "is_int": True, "is_float": False}, 9),
    ({"data": "9.3", "is_int": True, "is_float": False}, 9),
    ({"data": "9.", "is_int": True, "is_float": False}, 9),
    ({"data": " 9 . 3 l", "is_int": True, "is_float": False}, 9),
    ({"data": 9, "is_int": False, "is_float": True}, 9.0),
    ({"data": "9", "is_int": False, "is_float": True}, 9.0),
    ({"data": 9.3, "is_int": False, "is_float": True}, 9.3),
    ({"data": "9.3", "is_int": False, "is_float": True}, 9.3),
    ({"data": "9.", "is_int": False, "is_float": True}, 9.0),
    ({"data": " 9 . 3 l", "is_int": False, "is_float": True}, 9.3),
]


@pytest.mark.parametrize("value, result", xlate_values)
def test_xlate(value, result):
    assert comicapi.utils.xlate(**value) == result


language_values = [
    ("en", "English"),
    ("EN", "English"),
    ("En", "English"),
    ("", None),
    (None, None),
]


@pytest.mark.parametrize("value, result", language_values)
def test_get_language(value, result):
    assert result == comicapi.utils.get_language(value)


def test_unique_file(tmp_path):
    file = tmp_path / "test"
    assert file == comicapi.utils.unique_file(file)

    file.mkdir()
    assert (tmp_path / "test (1)") == comicapi.utils.unique_file(file)


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
