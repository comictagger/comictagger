from __future__ import annotations

import comictaggerlib.ui.talkeruigenerator


def test_format_internal_name():
    assert comictaggerlib.ui.talkeruigenerator.format_internal_name("talker_comicvine_cv_test_name") == "Test name"
