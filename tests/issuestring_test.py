import pytest

import comicapi.issuestring

issues = [
    ("¼", 0.25),
    ("1½", 1.5),
    ("0.5", 0.5),
    ("0", 0.0),
    ("1", 1.0),
    ("22.BEY", 22.0),
    ("22A", 22.0),
    ("22-A", 22.0),
]


@pytest.mark.parametrize("issue, expected", issues)
def test_issue_string_as_float(issue, expected):
    issue_float = comicapi.issuestring.IssueString(issue).as_float()
    assert issue_float == expected
