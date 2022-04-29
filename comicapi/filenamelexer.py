import calendar
import os
import unicodedata
from enum import Enum, auto


class ItemType(Enum):
    Error = auto()  # Error occurred; value is text of error
    EOF = auto()
    Text = auto()  # Text
    LeftParen = auto()  # '(' inside action
    Number = auto()  # Simple number
    IssueNumber = auto()  # Preceded by a # Symbol
    RightParen = auto()  # ')' inside action
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
    Keywords = auto()
    FCBD = auto()
    ComicType = auto()
    Publisher = auto()
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
    "book": ItemType.ComicType,
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
    def __init__(self, typ: ItemType, pos: int, val: str):
        self.typ: ItemType = typ
        self.pos: int = pos
        self.val: str = val

    def __repr__(self):
        return f"{self.val}: index: {self.pos}: {self.typ}"


class Lexer:
    def __init__(self, string):
        self.input: str = string  # The string being scanned
        self.state = None  # The next lexing function to enter
        self.pos: int = -1  # Current position in the input
        self.start: int = 0  # Start position of this item
        self.lastPos: int = 0  # Position of most recent item returned by nextItem
        self.paren_depth: int = 0  # Nesting depth of ( ) exprs
        self.brace_depth: int = 0  # Nesting depth of { }
        self.sbrace_depth: int = 0  # Nesting depth of [ ]
        self.items = []

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

    def backup(self):
        self.pos -= 1

    # Emit passes an item back to the client.
    def emit(self, t: ItemType):
        self.items.append(Item(t, self.start, self.input[self.start : self.pos + 1]))
        self.start = self.pos + 1

    # Ignore skips over the pending input before this point.
    def ignore(self):
        self.start = self.pos

    # Accept consumes the next rune if it's from the valid se:
    def accept(self, valid: str):
        if self.get() in valid:
            return True

        self.backup()
        return False

    # AcceptRun consumes a run of runes from the valid set.
    def accept_run(self, valid: str):
        while self.get() in valid:
            pass

        self.backup()

    # Errorf returns an error token and terminates the scan by passing
    # Back a nil pointer that will be the next state, terminating self.nextItem.
    def errorf(self, message: str):
        self.items.append(Item(ItemType.Error, self.start, message))

    # NextItem returns the next item from the input.
    # Called by the parser, not in the lexing goroutine.
    # def next_item(self) -> Item:
    #     item: Item = self.items.get()
    #     self.lastPos = item.pos
    #     return item

    def scan_number(self):
        digits = "0123456789"

        self.accept_run(digits)
        if self.accept("."):
            if self.accept(digits):
                self.accept_run(digits)
            else:
                self.backup()
        if self.accept("s"):
            if not self.accept("t"):
                self.backup()
        elif self.accept("nr"):
            if not self.accept("d"):
                self.backup()
        elif self.accept("t"):
            if not self.accept("h"):
                self.backup()

        return True

    # Runs the state machine for the lexer.
    def run(self):
        self.state = lex_filename
        while self.state is not None:
            self.state = self.state(self)


# Scans the elements inside action delimiters.
def lex_filename(lex: Lexer):
    r = lex.get()
    if r == eof:
        if lex.paren_depth != 0:
            return lex.errorf("unclosed left paren")

        if lex.brace_depth != 0:
            return lex.errorf("unclosed left paren")
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
        if r < "0" or "9" < r:
            lex.emit(ItemType.Dot)
            return lex_filename

        lex.backup()
        return lex_number
    elif r == "'":
        r = lex.peek()
        if r in "0123456789":
            return lex_number
        lex.emit(ItemType.Text)  # TODO: Change to Text
    elif "0" <= r <= "9":
        lex.backup()
        return lex_number
    elif r == "#":
        if "0" <= lex.peek() <= "9":
            return lex_number
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
            return lex.errorf("unexpected right paren " + r)

    elif r == "{":
        lex.emit(ItemType.LeftBrace)
        lex.brace_depth += 1
    elif r == "}":
        lex.emit(ItemType.RightBrace)
        lex.brace_depth -= 1
        if lex.brace_depth < 0:
            return lex.errorf("unexpected right brace " + r)

    elif r == "[":
        lex.emit(ItemType.LeftSBrace)
        lex.sbrace_depth += 1
    elif r == "]":
        lex.emit(ItemType.RightSBrace)
        lex.sbrace_depth -= 1
        if lex.sbrace_depth < 0:
            return lex.errorf("unexpected right brace " + r)
    elif is_symbol(r):
        # L.backup()
        lex.emit(ItemType.Symbol)
    else:
        return lex.errorf("unrecognized character in action: " + r)

    return lex_filename


def lex_operator(lex: Lexer):
    lex.accept_run("-|:;")
    lex.emit(ItemType.Operator)
    return lex_filename


# LexSpace scans a run of space characters.
# One space has already been seen.
def lex_space(lex: Lexer):
    while is_space(lex.peek()):
        lex.get()

    lex.emit(ItemType.Space)
    return lex_filename


# Lex_text scans an alphanumeric.
def lex_text(lex: Lexer):
    while True:
        r = lex.get()
        if is_alpha_numeric(r):
            if r.isnumeric():  # E.g. v1
                word = lex.input[lex.start : lex.pos]
                if word.lower() in key and key[word.lower()] == ItemType.InfoSpecifier:
                    lex.backup()
                    lex.emit(key[word.lower()])
                    return lex_filename
        else:
            if r == "'" and lex.peek() == "s":
                lex.get()
            else:
                lex.backup()
            word = lex.input[lex.start : lex.pos + 1]
            if word.lower() == "vol" and lex.peek() == ".":
                lex.get()
            word = lex.input[lex.start : lex.pos + 1]

            if word.lower() in key:
                lex.emit(key[word.lower()])
            elif cal(word):
                lex.emit(ItemType.Calendar)
            else:
                lex.emit(ItemType.Text)
            break

    return lex_filename


def cal(value: str):
    month_abbr = [i for i, x in enumerate(calendar.month_abbr) if x == value.title()]
    month_name = [i for i, x in enumerate(calendar.month_name) if x == value.title()]
    day_abbr = [i for i, x in enumerate(calendar.day_abbr) if x == value.title()]
    day_name = [i for i, x in enumerate(calendar.day_name) if x == value.title()]
    return set(month_abbr + month_name + day_abbr + day_name)


def lex_number(lex: Lexer):
    if not lex.scan_number():
        return lex.errorf("bad number syntax: " + lex.input[lex.start : lex.pos])
    # Complex number logic removed. Messes with math operations without space

    if lex.input[lex.start] == "#":
        lex.emit(ItemType.IssueNumber)
    elif not lex.input[lex.pos].isdigit():
        # Assume that 80th is just text and not a number
        lex.emit(ItemType.Text)
    else:
        lex.emit(ItemType.Number)

    return lex_filename


def is_space(character: str):
    return character in "_ \t"


# IsAlphaNumeric reports whether r is an alphabetic, digit, or underscore.
def is_alpha_numeric(character: str):
    return character.isalpha() or character.isnumeric()


def is_operator(character: str):
    return character in "-|:;/\\"


def is_symbol(character: str):
    return unicodedata.category(character)[0] in "PS"


def Lex(filename: str):
    lex = Lexer(string=os.path.basename(filename))
    lex.run()
    return lex
