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

Those on linux should install `Pillow` from the system package manager if possible and if the GUI `pyqt5` should be installed from the system package manager

Those on macOS will need to ensure that you are using python3 in x86 mode either by installing an x86 only version of python or using the universal installer and using `python3-intel64` instead of `python3`

1. Clone the repository
```
git clone https://github.com/comictagger/comictagger.git
```

2. It is preferred to use a virtual env for running from source:

```
python3 -m venv venv
```

3. Activate the virtual env:
```
. venv/bin/activate
```
or if on windows PowerShell
```
. venv/bin/activate.ps1
```

4. Install tox:
```bash
pip install tox
```

5. If you are on an M1 Mac you will need to export two environment variables for tests to pass.
```
export tox_python=python3.9-intel64
export tox_env=m1env
```

6. install ComicTagger
```
tox run -e venv
```

7. Make your changes
8. Build to ensure that your changes work: this will produce a binary build in the dist folder
```bash
tox run -m build
```

The build runs these formatters and linters automatically

setup-cfg-fmt: Formats the setup.cfg file
autoflake: Removes unused imports
isort: sorts imports so that you can always find where an import is located<br>
black: formats all of the code consistently so there are no surprises<br>
flake8: checks for code quality and style (warns for unused imports and similar issues)<br>
mypy: checks the types of variables and functions to catch errors
pytest: runs tests for ComicTagger functionality
