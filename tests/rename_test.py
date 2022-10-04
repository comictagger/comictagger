from __future__ import annotations

import pathlib

import pytest

from comicapi.genericmetadata import md_test
from comictaggerlib import filerenamer
from testing.filenames import rfnames, rnames


@pytest.mark.parametrize("template, move, platform, expected, exception", rnames)
def test_rename(template, platform, move, expected, exception):
    fr = filerenamer.FileRenamer(md_test, platform=platform)
    fr.move = move
    fr.set_template(template)
    with exception:
        assert str(pathlib.PureWindowsPath(fr.determine_name(".cbz"))) == str(pathlib.PureWindowsPath(expected))


@pytest.mark.parametrize("inp, result", rfnames)
def test_get_rename_dir(inp, result, cbz):
    assert result(cbz) == filerenamer.get_rename_dir(cbz, inp)
