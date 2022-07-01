from __future__ import annotations

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

    expected_result = {str(foo_png), str(temp_cbr), str(temp_file), str(temp_txt)}
    result = set(comicapi.utils.get_recursive_filelist([tmp_path]))

    assert result == expected_result


values = [
    ({"data": "", "is_int": False, "is_float": False}, None),
    ({"data": None, "is_int": False, "is_float": False}, None),
    ({"data": None, "is_int": True, "is_float": False}, None),
    ({"data": " ", "is_int": True, "is_float": False}, None),
    ({"data": "", "is_int": True, "is_float": False}, None),
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


@pytest.mark.parametrize("value, result", values)
def test_xlate(value, result):
    assert comicapi.utils.xlate(**value) == result
