# How to contribute

If your not sure what you can do or you need to ask a question or just want to talk about ComicTagger head over to the [discussions tab](https://github.com/comictagger/comictagger/discussions/categories/general) and start a discussion

## Tests

We have tests written using pytest! Some of them even pass! If you are contributing code any tests you can write are appreciated.

A great place to start is extending the tests that are already made.

For example the file tests/filenames.py has lists of filenames to be parsed in the format:
```py
    pytest.param(
        "Star Wars - War of the Bounty Hunters - IG-88 (2021) (Digital) (Kileko-Empire).cbz",
        "number ends series, no-issue",
        {
            "issue": "",
            "series": "Star Wars - War of the Bounty Hunters - IG-88",
            "volume": "",
            "year": "2021",
            "remainder": "(Digital) (Kileko-Empire)",
            "issue_count": "",
        },
        marks=pytest.mark.xfail,
    )
```

A test consists of 3-4 parts
1. The filename to be parsed
2. The reason it might fail
3. What the result of parsing the filename should be
4. `marks=pytest.mark.xfail` This marks the test as expected to fail

If you are not comfortable creating a pull request you can [open an issue](https://github.com/comictagger/comictagger/issues/new/choose) or [start a discussion](https://github.com/comictagger/comictagger/discussions/new)

## Submitting changes

Please open a [GitHub Pull Request](https://github.com/comictagger/comictagger/pull/new/develop) with a clear list of what you've done (read more about [pull requests](http://help.github.com/pull-requests/)). When you send a pull request, we will love you forever if you include tests. We can always use more test coverage. Please run the code tools below and make sure all of your commits are atomic (one feature per commit).

## Contributing Code

Currently only python 3.9 is supported however 3.10 will probably work if you try it

Those on linux should install `Pillow` from the system package manager if possible and if the GUI and/or the CBR/RAR comicbooks are going to be used `pyqt5` and `unrar-cffi` should be installed from the system package manager

Those on macOS will need to ensure that you are using python3 in x86 mode either by installing an x86 only version of python or using the universal installer and using `python3-intel64` instead of `python3`

1. Clone the repository
```
git clone https://github.com/comictagger/comictagger.git
```

2. It is preferred to use a virtual env for running from source, adding the `--system-site-packages` allows packages already installed via the system package manager to be used:

```
python3 -m venv --system-site-packages venv
```

3. Activate the virtual env:
```
. venv/bin/activate
```
or if on windows PowerShell
```
. venv/bin/activate.ps1
```

4. install dependencies:
```bash
pip install -r requirements_dev.txt -r requirements.txt
# if installing optional dependencies
pip install -r requirements-GUI.txt -r requirements-CBR.txt
```

5. install ComicTagger
```
pip install .
```

6. (optionall) run pytest to ensure that their are no failures (xfailed means expected failure)
```
$ pytest
============================= test session starts ==============================
platform darwin -- Python 3.9.12, pytest-7.1.1, pluggy-1.0.0
rootdir: /Users/timmy/build/source/comictagger
collected 61 items

tests/test_FilenameParser.py ..x......x.xxx.xx....xxxxxx.xx.x..xxxxxxx   [ 67%]
tests/test_comicarchive.py x...                                          [ 73%]
tests/test_rename.py ..xxx.xx..XXX.XX                                    [100%]

================== 27 passed, 29 xfailed, 5 xpassed in 2.68s ===================
```

7. Make your changes
8. run code tools and correct any issues
```bash
black .
isort .
flake8 .
pytest
```

black: formats all of the code consistently so there are no surprises<br>
isort: sorts imports so that you can always find where an import is located<br>
flake8: checks for code quality and style (warns for unused imports and similar issues)<br>
pytest: runs tests for ComicTagger functionality


if on mac or linux most of this can be accomplished by running
```
make install
# or make PYTHON=python3-intel64 install
. venv/bin/activate
make CI
```
There is also `make check` which will run all of the code tools in a read-only capacity
```
$ make check
venv/bin/black --check .
All done! ✨ 🍰 ✨
52 files would be left unchanged.
venv/bin/isort --check .
Skipped 6 files
venv/bin/flake8 .
venv/bin/pytest
============================= test session starts ==============================
platform darwin -- Python 3.9.12, pytest-7.1.1, pluggy-1.0.0
rootdir: /Users/timmy/build/source/comictagger
collected 61 items

tests/test_FilenameParser.py ..x......x.xxx.xx....xxxxxx.xx.x..xxxxxxx   [ 67%]
tests/test_comicarchive.py x...                                          [ 73%]
tests/test_rename.py ..xxx.xx..XXX.XX                                    [100%]

================== 27 passed, 29 xfailed, 5 xpassed in 2.68s ===================
```
