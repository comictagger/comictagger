from __future__ import annotations

import pytest

import comicapi.issuestring

issues = [
    ("¼", 0.25, "¼"),
    ("1½", 1.5, "001½"),
    ("0.5", 0.5, "000.5"),
    ("0", 0.0, "000"),
    ("1", 1.0, "001"),
    ("22.BEY", 22.0, "022.BEY"),
    ("22A", 22.0, "022A"),
    ("22-A", 22.0, "022-A"),
]


@pytest.mark.parametrize("issue, expected_float, expected_pad_str", issues)
def test_issue_string_as_float(issue, expected_float, expected_pad_str):
    issue_float = comicapi.issuestring.IssueString(issue).as_float()
    assert issue_float == expected_float


@pytest.mark.parametrize("issue, expected_float, expected_pad_str", issues)
def test_issue_string_as_string(issue, expected_float, expected_pad_str):
    issue_str = comicapi.issuestring.IssueString(issue).as_string()
    issue_str_pad = comicapi.issuestring.IssueString(issue).as_string(3)
    assert issue_str == issue
    assert issue_str_pad == expected_pad_str
