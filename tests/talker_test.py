from __future__ import annotations

import pytest

import comictaggerlib.ui.talkeruigenerator

test_names = [
    ("cv_test_name", "Test name"),
    ("cv2_test_name", "Test name"),
]


@pytest.mark.parametrize("int_name, expected", test_names)
def test_format_internal_name(int_name, expected):
    results = comictaggerlib.ui.talkeruigenerator.format_internal_name(int_name)
    assert results == expected
