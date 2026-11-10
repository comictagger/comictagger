from __future__ import annotations

import builtins
import pathlib
from types import SimpleNamespace

from comictaggerlib.cli import CLI
from comictaggerlib.resulttypes import Action, IssueResult, Result, Score, Status


def make_cli(interactive=True) -> CLI:
    config = SimpleNamespace(
        Runtime_Options__interactive=interactive,
        Runtime_Options__json=False,
        Runtime_Options__verbose=0,
        Runtime_Options__quiet=True,
    )
    return CLI(config, {})


def make_match_set() -> Result:
    issue = IssueResult(
        score=Score(score=100, url="", remote_hash=0, local_hash_name="", local_hash=0),
        series=SimpleNamespace(name="Test Series", publisher="Test Publisher"),
        md=SimpleNamespace(year=2020, issue="1", month=1, title="Test Title"),
    )
    return Result(Action.save, Status.success, pathlib.Path("test.cbz"), online_results=[issue])


def test_display_match_eof_skips(monkeypatch, capsys) -> None:
    """Closed stdin during an interactive match choice skips instead of crashing."""

    def raise_eof(prompt=""):
        raise EOFError

    monkeypatch.setattr(builtins, "input", raise_eof)
    cli = make_cli()
    match_set = make_match_set()

    # must not raise
    cli.display_match_set_for_choice("Multiple high-confidence matches", match_set)

    assert match_set.md is None


def test_display_match_skip_still_works(monkeypatch) -> None:
    """An explicit 's' still skips without touching anything."""
    monkeypatch.setattr(builtins, "input", lambda prompt="": "s")
    cli = make_cli()
    match_set = make_match_set()

    cli.display_match_set_for_choice("Multiple high-confidence matches", match_set)

    assert match_set.md is None


def test_display_match_not_interactive_asks_nothing(monkeypatch) -> None:
    """Non-interactive mode never prompts, even with multiple matches."""
    called = []

    def fail_input(prompt=""):
        called.append(prompt)
        raise AssertionError("input must not be called")

    monkeypatch.setattr(builtins, "input", fail_input)
    cli = make_cli(interactive=False)

    cli.display_match_set_for_choice("Multiple high-confidence matches", make_match_set())

    assert called == []
