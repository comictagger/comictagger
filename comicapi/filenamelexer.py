# Extracted and mutilated from https://github.com/lordwelch/wsfmt
# Which was extracted and mutilated from https://github.com/golang/go/tree/master/src/text/template/parse
from __future__ import annotations

import calendar
import os
import unicodedata
from enum import Enum, auto
from typing import Any, Callable


class ItemType(Enum):
    Error = auto()  # Error occurred; value is text of error
    EOF = auto()
    Text = auto()  # Text
    LeftParen = auto()
    Number = auto()  # Simple number
    IssueNumber = auto()  # Preceded by a # Symbol
    RightParen = auto()
    Space = auto()  # Run of spaces separating arguments
    Dot = auto()
    LeftBrace = auto()
    RightBrace = auto()
    LeftSBrace = auto()
    RightSBrace = auto()
    Symbol = auto()
    Skip = auto()  # __ or -- no title, issue or series information beyond
    Operator = auto()
    Calendar = auto()
    InfoSpecifier = auto()  # Specifies type of info e.g. v1 for 'volume': 1
    ArchiveType = auto()
    Honorific = auto()
    Publisher = auto()
    Keywords = auto()
    FCBD = auto()
    ComicType = auto()
    C2C = auto()


braces = [
    ItemType.LeftBrace,
    ItemType.LeftParen,
    ItemType.LeftSBrace,
    ItemType.RightBrace,
    ItemType.RightParen,
    ItemType.RightSBrace,
]

eof = chr(0)

key = {
    "fcbd": ItemType.FCBD,
    "freecomicbookday": ItemType.FCBD,
    "cbr": ItemType.ArchiveType,
    "cbz": ItemType.ArchiveType,
    "cbt": ItemType.ArchiveType,
    "cb7": ItemType.ArchiveType,
    "rar": ItemType.ArchiveType,
    "zip": ItemType.ArchiveType,
    "tar": ItemType.ArchiveType,
    "7z": ItemType.ArchiveType,
    "annual": ItemType.ComicType,
    "volume": ItemType.InfoSpecifier,
    "vol.": ItemType.InfoSpecifier,
    "vol": ItemType.InfoSpecifier,
    "v": ItemType.InfoSpecifier,
    "of": ItemType.InfoSpecifier,
    "dc": ItemType.Publisher,
    "marvel": ItemType.Publisher,
    "covers": ItemType.InfoSpecifier,
    "c2c": ItemType.C2C,
    "mr": ItemType.Honorific,
    "ms": ItemType.Honorific,
    "mrs": ItemType.Honorific,
    "dr": ItemType.Honorific,
}


class Item:
    def __init__(self, typ: ItemType, pos: int, val: str) -> None:
        self.typ: ItemType = typ
        self.pos: int = pos
        self.val: str = val
        self.no_space = False

    def __repr__(self) -> str:
        return f"{self.val}: index: {self.pos}: {self.typ}"


class Lexer:
    def __init__(self, string: str, allow_issue_start_with_letter: bool = False) -> None:
        self.input: str = string  # The string being scanned
        # The next lexing function to enter
        self.state: Callable[[Lexer], Callable | None] | None = None  # type: ignore[type-arg]
        self.pos: int = -1  # Current position in the input
        self.start: int = 0  # Start position of this item
        self.lastPos: int = 0  # Position of most recent item returned by nextItem
        self.paren_depth: int = 0  # Nesting depth of ( ) exprs
        self.brace_depth: int = 0  # Nesting depth of { }
        self.sbrace_depth: int = 0  # Nesting depth of [ ]
        self.items: list[Item] = []
        self.allow_issue_start_with_letter = allow_issue_start_with_letter

    # Next returns the next rune in the input.
    def get(self) -> str:
        if int(self.pos) >= len(self.input) - 1:
            self.pos += 1
            return eof

        self.pos += 1
        return self.input[self.pos]

    # Peek returns but does not consume the next rune in the input.
    def peek(self) -> str:
        if int(self.pos) >= len(self.input) - 1:
            return eof

        return self.input[self.pos + 1]

    def backup(self) -> None:
        self.pos -= 1

    # Emit passes an item back to the client.
    def emit(self, t: ItemType) -> None:
        self.items.append(Item(t, self.start, self.input[self.start : self.pos + 1]))
        self.start = self.pos + 1

    # Ignore skips over the pending input before this point.
    def ignore(self) -> None:
        self.start = self.pos

    # Accept consumes the next rune if it's from the valid se:
    def accept(self, valid: str) -> bool:
        if self.get() in valid:
            return True

        self.backup()
        return False

    # AcceptRun consumes a run of runes from the valid set.
    def accept_run(self, valid: str) -> None:
        while self.get() in valid:
            continue

        self.backup()

    def scan_number(self) -> bool:
        digits = "0123456789.,"

        self.accept_run(digits)
        if self.input[self.pos] == ".":
            self.backup()
        while self.get().isalpha():
            ...
        self.backup()

        return True

    # Runs the state machine for the lexer.
    def run(self) -> None:
        self.state = lex_filename
        while self.state is not None:
            self.state = self.state(self)


# Errorf returns an error token and terminates the scan by passing
# Back a nil pointer that will be the next state, terminating self.nextItem.
def errorf(lex: Lexer, message: str) -> Callable[[Lexer], Callable | None] | None:  # type: ignore[type-arg]
    lex.items.append(Item(ItemType.Error, lex.start, message))
    return None


# Scans the elements inside action delimiters.
def lex_filename(lex: Lexer) -> Callable[[Lexer], Callable | None] | None:  # type: ignore[type-arg]
    r = lex.get()
    if r == eof:
        if lex.paren_depth != 0:
            return errorf(lex, "unclosed left paren")

        if lex.brace_depth != 0:
            return errorf(lex, "unclosed left paren")
        lex.emit(ItemType.EOF)
        return None
    elif is_space(r):
        if r == "_" and lex.peek() == "_":
            lex.get()
            lex.emit(ItemType.Skip)
        else:
            return lex_space
    elif r == ".":
        r = lex.peek()
        if r.isnumeric() and lex.pos > 0 and is_space(lex.input[lex.pos - 1]):
            return lex_number
        lex.emit(ItemType.Dot)
        return lex_filename
    elif r == "'":
        r = lex.peek()
        if r.isdigit():
            return lex_number
        lex.emit(ItemType.Text)  # TODO: Change to Text
    elif r.isnumeric():
        lex.backup()
        return lex_number
    elif r == "#":
        if lex.allow_issue_start_with_letter and is_alpha_numeric(lex.peek()):
            return lex_issue_number
        elif lex.peek().isdigit() or lex.peek() in "-+.":
            return lex_issue_number
        lex.emit(ItemType.Symbol)
    elif is_operator(r):
        if r == "-" and lex.peek() == "-":
            lex.get()
            lex.emit(ItemType.Skip)
        else:
            return lex_operator
    elif is_alpha_numeric(r):
        lex.backup()
        return lex_text
    elif r == "(":
        lex.emit(ItemType.LeftParen)
        lex.paren_depth += 1
    elif r == ")":
        lex.emit(ItemType.RightParen)
        lex.paren_depth -= 1
        if lex.paren_depth < 0:
            return errorf(lex, "unexpected right paren " + r)

    elif r == "{":
        lex.emit(ItemType.LeftBrace)
        lex.brace_depth += 1
    elif r == "}":
        lex.emit(ItemType.RightBrace)
        lex.brace_depth -= 1
        if lex.brace_depth < 0:
            return errorf(lex, "unexpected right brace " + r)

    elif r == "[":
        lex.emit(ItemType.LeftSBrace)
        lex.sbrace_depth += 1
    elif r == "]":
        lex.emit(ItemType.RightSBrace)
        lex.sbrace_depth -= 1
        if lex.sbrace_depth < 0:
            return errorf(lex, "unexpected right brace " + r)
    elif is_symbol(r):
        if unicodedata.category(r) == "Sc":
            return lex_currency
        lex.emit(ItemType.Symbol)
    else:
        return errorf(lex, "unrecognized character in action: " + r)

    return lex_filename


def lex_currency(lex: Lexer) -> Callable:
    orig = lex.pos
    while is_space(lex.peek()):
        lex.get()
    if lex.peek().isnumeric():
        return lex_number
    else:
        lex.pos = orig
    # We don't have a number with this currency symbol. Don't treat it special
    lex.emit(ItemType.Symbol)
    return lex_filename


def lex_operator(lex: Lexer) -> Callable:  # type: ignore[type-arg]
    lex.accept_run("-|:;")
    lex.emit(ItemType.Operator)
    return lex_filename


# LexSpace scans a run of space characters.
# One space has already been seen.
def lex_space(lex: Lexer) -> Callable:  # type: ignore[type-arg]
    while is_space(lex.peek()):
        lex.get()

    lex.emit(ItemType.Space)
    return lex_filename


# Lex_text scans an alphanumeric.
def lex_text(lex: Lexer) -> Callable:  # type: ignore[type-arg]
    while True:
        r = lex.get()
        if is_alpha_numeric(r):
            if r.isnumeric():  # E.g. v1
                word = lex.input[lex.start : lex.pos]
                if word.casefold() in key and key[word.casefold()] == ItemType.InfoSpecifier:
                    lex.backup()
                    lex.emit(key[word.casefold()])
                    return lex_filename
        else:
            if r == "'" and lex.peek() == "s":
                lex.get()
            else:
                lex.backup()
            word = lex.input[lex.start : lex.pos + 1]
            if word.casefold() == "vol" and lex.peek() == ".":
                lex.get()
            word = lex.input[lex.start : lex.pos + 1]

            if word.casefold() in key:
                lex.emit(key[word.casefold()])
            elif cal(word):
                lex.emit(ItemType.Calendar)
            else:
                lex.emit(ItemType.Text)
            break

    return lex_filename


def cal(value: str) -> set[Any]:
    month_abbr = [i for i, x in enumerate(calendar.month_abbr) if x == value.title()]
    month_name = [i for i, x in enumerate(calendar.month_name) if x == value.title()]
    day_abbr = [i for i, x in enumerate(calendar.day_abbr) if x == value.title()]
    day_name = [i for i, x in enumerate(calendar.day_name) if x == value.title()]
    return set(month_abbr + month_name + day_abbr + day_name)


def lex_number(lex: Lexer) -> Callable[[Lexer], Callable | None] | None:  # type: ignore[type-arg]
    if not lex.scan_number():
        return errorf(lex, "bad number syntax: " + lex.input[lex.start : lex.pos])
    # Complex number logic removed. Messes with math operations without space

    if lex.input[lex.start] == "#":
        lex.emit(ItemType.IssueNumber)
    elif not lex.input[lex.pos].isdigit():
        # Assume that 80th is just text and not a number
        lex.emit(ItemType.Text)
    else:
        orig = lex.pos
        while is_space(lex.peek()):
            lex.get()
        if "Sc" == unicodedata.category(lex.get()):
            lex.emit(ItemType.Text)
        else:
            lex.pos = orig
            if "Sc" == unicodedata.category(lex.input[lex.start]):
                lex.emit(ItemType.Text)
            else:
                lex.emit(ItemType.Number)

    return lex_filename


def lex_issue_number(lex: Lexer) -> Callable[[Lexer], Callable | None] | None:  # type: ignore[type-arg]
    # Only called when lex.input[lex.start] == "#"
    original_start = lex.pos
    found_number = False
    while True:
        r = lex.get()
        if is_alpha_numeric(r):
            if r.isnumeric():
                found_number = True
        else:
            lex.backup()
            break

    if not found_number:
        lex.pos = original_start
        lex.emit(ItemType.Symbol)
    else:
        lex.emit(ItemType.IssueNumber)

    return lex_filename


def is_space(character: str) -> bool:
    return character in "_ \t"


# IsAlphaNumeric reports whether r is an alphabetic, digit, or underscore.
def is_alpha_numeric(character: str) -> bool:
    return character.isalpha() or character.isnumeric()


def is_operator(character: str) -> bool:
    return character in "-|:;/\\"


def is_symbol(character: str) -> bool:
    return unicodedata.category(character)[0] in "PS"


def Lex(filename: str, allow_issue_start_with_letter: bool = False) -> Lexer:
    lex = Lexer(os.path.basename(filename), allow_issue_start_with_letter)
    lex.run()
    return lex
