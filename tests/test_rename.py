import re

import pytest
from filenames import rnames

from comicapi.genericmetadata import md_test
from comictaggerlib.filerenamer import FileRenamer, FileRenamer2


@pytest.mark.parametrize("template, move, platform, expected", rnames)
def test_rename_old(template, platform, move, expected):
    _ = platform
    _ = move
    fr = FileRenamer(md_test)
    fr.set_template(re.sub(r"{(\w+)}", r"%\1%", template))
    assert fr.determine_name(".cbz") == expected


@pytest.mark.parametrize("template, move, platform, expected", rnames)
def test_rename_new(template, platform, move, expected):
    fr = FileRenamer2(md_test, platform=platform)
    fr.move = move
    fr.set_template(template)
    assert fr.determine_name(".cbz") == expected
