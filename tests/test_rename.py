import re

import pytest
from filenames import rnames

from comicapi.genericmetadata import md_test
from comictaggerlib.filerenamer import FileRenamer, FileRenamer2


@pytest.mark.parametrize("template,result", rnames)
def test_rename_old(template, result):
    fr = FileRenamer(md_test)
    fr.set_template(re.sub(r"{(\w+)}", r"%\1%", template))
    assert fr.determine_name(".cbz") == result


@pytest.mark.parametrize("template,result", rnames)
def test_rename_new(template, result):
    fr = FileRenamer2(md_test)
    fr.set_template(template)
    assert fr.determine_name(".cbz") == result
