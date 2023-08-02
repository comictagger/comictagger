"""
format is
(
    "filename",
    "reason or unique case",
    {
        "expected": "Dictionary of properties extracted from filename",
    },
    bool(xfail: expected failure on the old parser)
)
"""
from __future__ import annotations

import datetime
import os
import os.path
import pathlib
from contextlib import nullcontext as does_not_raise

import pytest

datadir = pathlib.Path(__file__).parent / "data"
cbz_path = datadir / "Cory Doctorow's Futuristic Tales of the Here and Now #001 - Anda's Game (2007).cbz"

names = [
    (
        "batman #3 title (DC).cbz",
        "honorific and publisher in series",
        {
            "issue": "3",
            "series": "batman",
            "title": "title",
            "publisher": "DC",
            "volume": "",
            "year": "",
            "remainder": "",
            "issue_count": "",
            "alternate": "",
        },
        (False, True),
    ),
    (
        "batman #3 title DC.cbz",
        "honorific and publisher in series",
        {
            "issue": "3",
            "series": "batman",
            "title": "title DC",
            "publisher": "DC",
            "volume": "",
            "year": "",
            "remainder": "",
            "issue_count": "",
            "alternate": "",
        },
        (False, True),
    ),
    (
        "ms. Marvel #3.cbz",
        "honorific and publisher in series",
        {
            "issue": "3",
            "series": "ms. Marvel",
            "title": "",
            "publisher": "Marvel",
            "volume": "",
            "year": "",
            "remainder": "",
            "issue_count": "",
            "alternate": "",
        },
        (False, False),
    ),
    (
        f"action comics #{datetime.datetime.now().year}.cbz",
        "issue number is current year (digits == 4)",
        {
            "issue": f"{datetime.datetime.now().year}",
            "series": "action comics",
            "title": "",
            "publisher": "",
            "volume": "",
            "year": "",
            "remainder": "",
            "issue_count": "",
            "alternate": "",
        },
        (False, False),
    ),
    (
        "january jones #2.cbz",
        "month in series",
        {
            "issue": "2",
            "series": "january jones",
            "title": "",
            "volume": "",
            "year": "",
            "remainder": "",
            "issue_count": "",
            "alternate": "",
        },
        (False, False),
    ),
    (
        "#52.cbz",
        "issue number only",
        {
            "issue": "52",
            "series": "52",
            "title": "",
            "volume": "",
            "year": "",
            "remainder": "",
            "issue_count": "",
            "alternate": "",
        },
        (False, False),
    ),
    (
        "52 Monster_Island_v1_#2__repaired__c2c.cbz",
        "leading alternate",
        {
            "issue": "2",
            "series": "Monster Island",
            "title": "",
            "volume": "1",
            "year": "",
            "remainder": "repaired",
            "issue_count": "",
            "alternate": "52",
            "c2c": True,
        },
        (True, True),
    ),
    (
        "Monster_Island_v1_#2__repaired__c2c.cbz",
        "Example from userguide",
        {
            "issue": "2",
            "series": "Monster Island",
            "title": "",
            "volume": "1",
            "year": "",
            "remainder": "repaired",
            "issue_count": "",
            "c2c": True,
        },
        (False, False),
    ),
    (
        "Monster Island v1 #3 (1957) -- The Revenge Of King Klong (noads).cbz",
        "Example from userguide",
        {
            "issue": "3",
            "series": "Monster Island",
            "title": "",
            "volume": "1",
            "year": "1957",
            "remainder": "The Revenge Of King Klong (noads)",
            "issue_count": "",
        },
        (False, False),
    ),
    (
        "Foobar-Man Annual #121 - The Wrath of Foobar-Man, Part 1 of 2.cbz",
        "Example from userguide",
        {
            "issue": "121",
            "series": "Foobar-Man Annual",
            "title": "The Wrath of Foobar-Man, Part 1 of 2",
            "volume": "",
            "year": "",
            "remainder": "",
            "issue_count": "",
            "annual": True,
        },
        (False, True),
    ),
    (
        "Plastic Man v1 #002 (1942).cbz",
        "Example from userguide",
        {
            "issue": "2",
            "series": "Plastic Man",
            "title": "",
            "volume": "1",
            "year": "1942",
            "remainder": "",
            "issue_count": "",
        },
        (False, False),
    ),
    (
        "Blue Beetle #02.cbr",
        "Example from userguide",
        {
            "issue": "2",
            "series": "Blue Beetle",
            "title": "",
            "volume": "",
            "year": "",
            "remainder": "",
            "issue_count": "",
        },
        (False, False),
    ),
    (
        "Monster Island vol. 2 #2.cbz",
        "Example from userguide",
        {
            "issue": "2",
            "series": "Monster Island",
            "title": "",
            "volume": "2",
            "year": "",
            "remainder": "",
            "issue_count": "",
        },
        (False, False),
    ),
    (
        "Crazy Weird Comics #2 (of 2) (1969).rar",
        "Example from userguide",
        {
            "issue": "2",
            "series": "Crazy Weird Comics",
            "title": "",
            "volume": "",
            "year": "1969",
            "remainder": "",
            "issue_count": "2",
        },
        (False, False),
    ),
    (
        "Super Strange Yarns (1957) #92 (1969).cbz",
        "Example from userguide",
        {
            "issue": "92",
            "series": "Super Strange Yarns",
            "title": "",
            "volume": "1957",
            "year": "1969",
            "remainder": "",
            "issue_count": "",
        },
        (False, False),
    ),
    (
        "Action Spy Tales v1965 #3.cbr",
        "Example from userguide",
        {
            "issue": "3",
            "series": "Action Spy Tales",
            "title": "",
            "volume": "1965",
            "year": "",
            "remainder": "",
            "issue_count": "",
        },
        (False, False),
    ),
    (
        " X-Men-V1-#067.cbr",
        "hyphen separated with hyphen in series",  # only parses correctly because v1 designates the volume
        {
            "issue": "67",
            "series": "X-Men",
            "title": "",
            "volume": "1",
            "year": "",
            "remainder": "",
            "issue_count": "",
        },
        (False, False),
    ),
    (
        "Amazing Spider-Man #078.BEY (2022) (Digital) (Zone-Empire).cbr",
        "number issue with extra",
        {
            "issue": "78.BEY",
            "series": "Amazing Spider-Man",
            "title": "",
            "volume": "",
            "year": "2022",
            "remainder": "(Digital) (Zone-Empire)",
            "issue_count": "",
        },
        (False, False),
    ),
    (
        "Angel Wings #02 - Black Widow (2015) (Scanlation) (phillywilly).cbr",
        "title after #issue",
        {
            "issue": "2",
            "series": "Angel Wings",
            "title": "Black Widow",
            "volume": "",
            "year": "2015",
            "remainder": "(Scanlation) (phillywilly)",
            "issue_count": "",
        },
        (False, True),
    ),
    (
        "Aquaman - Green Arrow - Deep Target #01 (of 07) (2021) (digital) (Son of Ultron-Empire).cbr",
        "issue count",
        {
            "issue": "1",
            "series": "Aquaman - Green Arrow - Deep Target",
            "title": "",
            "volume": "",
            "year": "2021",
            "issue_count": "7",
            "remainder": "(digital) (Son of Ultron-Empire)",
        },
        (False, False),
    ),
    (
        "Aquaman 80th Anniversary 100-Page Super Spectacular (2021) #001 (2021) (Digital) (BlackManta-Empire).cbz",
        "numbers in series",
        {
            "issue": "1",
            "series": "Aquaman 80th Anniversary 100-Page Super Spectacular",
            "title": "",
            "volume": "2021",
            "year": "2021",
            "remainder": "(Digital) (BlackManta-Empire)",
            "issue_count": "",
        },
        (False, False),
    ),
    (
        "Avatar - The Last Airbender - The Legend of Korra (FCBD 2021) (Digital) (mv-DCP).cbr",
        "FCBD date",
        {
            "issue": "",
            "series": "Avatar - The Last Airbender - The Legend of Korra",
            "title": "",
            "volume": "",
            "year": "2021",
            "remainder": "(Digital) (mv-DCP)",
            "issue_count": "",
            "fcbd": True,
        },
        (True, False),
    ),
    (
        "Avengers By Brian Michael Bendis volume 03 (2013) (Digital) (F2) (Kileko-Empire).cbz",
        "volume without issue",
        {
            "issue": "3",
            "series": "Avengers By Brian Michael Bendis",
            "title": "",
            "volume": "3",
            "year": "2013",
            "remainder": "(Digital) (F2) (Kileko-Empire)",
            "issue_count": "",
        },
        (False, False),
    ),
    (
        "Avengers By Brian Michael Bendis v03 (2013) (Digital) (F2) (Kileko-Empire).cbz",
        "volume without issue",
        {
            "issue": "3",
            "series": "Avengers By Brian Michael Bendis",
            "title": "",
            "volume": "3",
            "year": "2013",
            "remainder": "(Digital) (F2) (Kileko-Empire)",
            "issue_count": "",
        },
        (False, False),
    ),
    (
        "Batman '89 (2021) (Webrip) (The Last Kryptonian-DCP).cbr",
        "year in title without issue",
        {
            "issue": "",
            "series": "Batman '89",
            "title": "",
            "volume": "",
            "year": "2021",
            "remainder": "(Webrip) (The Last Kryptonian-DCP)",
            "issue_count": "",
        },
        (False, False),
    ),
    (
        "Batman_-_Superman_#020_(2021)_(digital)_(NeverAngel-Empire).cbr",
        "underscores",
        {
            "issue": "20",
            "series": "Batman - Superman",
            "title": "",
            "volume": "",
            "year": "2021",
            "remainder": "(digital) (NeverAngel-Empire)",
            "issue_count": "",
        },
        (False, False),
    ),
    (
        "Black Widow #009 (2021) (Digital) (Zone-Empire).cbr",
        "standard",
        {
            "issue": "9",
            "series": "Black Widow",
            "title": "",
            "volume": "",
            "year": "2021",
            "remainder": "(Digital) (Zone-Empire)",
            "issue_count": "",
        },
        (False, False),
    ),
    (
        "Blade Runner 2029 #006 (2021) (3 covers) (digital) (Son of Ultron-Empire).cbr",
        "year before issue",
        {
            "issue": "6",
            "series": "Blade Runner 2029",
            "title": "",
            "volume": "",
            "year": "2021",
            "remainder": "(3 covers) (digital) (Son of Ultron-Empire)",
            "issue_count": "",
        },
        (False, False),
    ),
    (
        "Blade Runner Free Comic Book Day 2021 (2021) (digital-Empire).cbr",
        "FCBD year and (year)",
        {
            "issue": "",
            "series": "Blade Runner Free Comic Book Day 2021",
            "title": "",
            "volume": "",
            "year": "2021",
            "remainder": "(digital-Empire)",
            "issue_count": "",
            "fcbd": True,
        },
        (True, False),
    ),
    (
        "Bloodshot Book 03 (2020) (digital) (Son of Ultron-Empire).cbr",
        "book",
        {
            "issue": "3",
            "series": "Bloodshot",
            "title": "Book 03",
            "volume": "3",
            "year": "2020",
            "remainder": "(digital) (Son of Ultron-Empire)",
            "issue_count": "",
        },
        (True, False),
    ),
    (
        "book of eli #1 (2020) (digital) (Son of Ultron-Empire).cbr",
        "book",
        {
            "issue": "1",
            "series": "book of eli",
            "title": "",
            "volume": "",
            "year": "2020",
            "remainder": "(digital) (Son of Ultron-Empire)",
            "issue_count": "",
        },
        (False, False),
    ),
    (
        "Cyberpunk 2077 - You Have My Word #02 (2021) (digital) (Son of Ultron-Empire).cbr",
        "title",
        {
            "issue": "2",
            "series": "Cyberpunk 2077",
            "title": "You Have My Word",
            "volume": "",
            "year": "2021",
            "issue_count": "",
            "remainder": "(digital) (Son of Ultron-Empire)",
        },
        (True, True),
    ),
    (
        "Elephantmen 2259 #008 - Simple Truth 03 (of 06) (2021) (digital) (Son of Ultron-Empire).cbr",
        "volume count",
        {
            "issue": "8",
            "series": "Elephantmen 2259",
            "title": "Simple Truth",
            "volume": "3",
            "year": "2021",
            "volume_count": "6",
            "remainder": "(digital) (Son of Ultron-Empire)",
            "issue_count": "",
        },
        (True, True),
    ),
    (
        "Free Comic Book Day - Avengers.Hulk (2021) (2048px) (db).cbz",
        "'.' in name",
        {
            "issue": "",
            "series": "Free Comic Book Day - Avengers Hulk",
            "title": "",
            "volume": "",
            "year": "2021",
            "remainder": "(2048px) (db)",
            "issue_count": "",
            "fcbd": True,
        },
        (True,),
    ),
    (
        "Goblin (2021) (digital) (Son of Ultron-Empire).cbr",
        "no-issue",
        {
            "issue": "",
            "series": "Goblin",
            "title": "",
            "volume": "",
            "year": "2021",
            "remainder": "(digital) (Son of Ultron-Empire)",
            "issue_count": "",
        },
        (False,),
    ),
    (
        "Marvel Previews #002 (January 2022) (Digital-Empire).cbr",
        "(month year)",
        {
            "issue": "2",
            "series": "Marvel Previews",
            "title": "",
            "publisher": "Marvel",
            "volume": "",
            "year": "2022",
            "remainder": "(Digital-Empire)",
            "issue_count": "",
        },
        (True, True),
    ),
    (
        "Marvel Two In One V1 #090  c2c (Comixbear-DCP).cbr",
        "volume then issue",
        {
            "issue": "90",
            "series": "Marvel Two In One",
            "title": "",
            "publisher": "Marvel",
            "volume": "1",
            "year": "",
            "remainder": "(Comixbear-DCP)",
            "issue_count": "",
            "c2c": True,
        },
        (False, True),
    ),
    (
        "Star Wars - War of the Bounty Hunters - IG-88 (2021) (Digital) (Kileko-Empire).cbz",
        "number ends series, no-issue",
        {
            "issue": "",
            "series": "Star Wars - War of the Bounty Hunters - IG-88",
            "title": "",
            "volume": "",
            "year": "2021",
            "remainder": "(Digital) (Kileko-Empire)",
            "issue_count": "",
        },
        (True,),
    ),
    (
        "Star Wars - War of the Bounty Hunters - IG-88 #1 (2021) (Digital) (Kileko-Empire).cbz",
        "number ends series",
        {
            "issue": "1",
            "series": "Star Wars - War of the Bounty Hunters - IG-88",
            "title": "",
            "volume": "",
            "year": "2021",
            "remainder": "(Digital) (Kileko-Empire)",
            "issue_count": "",
        },
        (False, False),
    ),
    (
        "The Defenders v1 #058 (1978) (digital).cbz",
        "",
        {
            "issue": "58",
            "series": "The Defenders",
            "title": "",
            "volume": "1",
            "year": "1978",
            "remainder": "(digital)",
            "issue_count": "",
        },
        (False, False),
    ),
    (
        "The Defenders v1 Annual #01 (1976) (Digital) (Minutemen-Slayer).cbr",
        " v in series",
        {
            "issue": "1",
            "series": "The Defenders Annual",
            "title": "",
            "volume": "1",
            "year": "1976",
            "remainder": "(Digital) (Minutemen-Slayer)",
            "issue_count": "",
            "annual": True,
        },
        (True, True),
    ),
    (
        "The Magic Order 2 #06 (2022) (Digital) (Zone-Empire)[__913302__].cbz",
        "ending id",
        {
            "issue": "6",
            "series": "The Magic Order 2",
            "title": "",
            "volume": "",
            "year": "2022",
            "remainder": "(Digital) (Zone-Empire)[913302]",  # Don't really care about double underscores
            "issue_count": "",
        },
        (False, False),
    ),
    (
        "Wonder Woman #001 Wonder Woman Day Special Edition (2021) (digital-Empire).cbr",
        "issue separates title",
        {
            "issue": "1",
            "series": "Wonder Woman",
            "title": "Wonder Woman Day Special Edition",
            "volume": "",
            "year": "2021",
            "remainder": "(digital-Empire)",
            "issue_count": "",
        },
        (False, True),
    ),
    (
        "Wonder Woman #49 DC Sep-Oct 1951 digital [downsized, lightened, 4 missing story pages restored] (Shadowcat-Empire).cbz",
        "date-range, no paren, braces",
        {
            "issue": "49",
            "series": "Wonder Woman",
            "title": "digital",  # Don't have a way to get rid of this
            "publisher": "DC",
            "volume": "",
            "year": "1951",
            "remainder": "[downsized, lightened, 4 missing story pages restored] (Shadowcat-Empire)",
            "issue_count": "",
        },
        (True, True),
    ),
    (
        "X-Men, 2021-08-04 (#02) (digital) (Glorith-HD).cbz",
        "full-date, issue in parenthesis",
        {
            "issue": "2",
            "series": "X-Men",
            "title": "",
            "volume": "",
            "year": "2021",
            "remainder": "(digital) (Glorith-HD)",
            "issue_count": "",
        },
        (True, True),
    ),
    (
        "Cory Doctorow's Futuristic Tales of the Here and Now: Anda's Game #001 (2007).cbz",
        "title",
        {
            "issue": "1",
            "series": "Cory Doctorow's Futuristic Tales of the Here and Now",
            "title": "Anda's Game",
            "volume": "",
            "year": "2007",
            "remainder": "",
            "issue_count": "",
        },
        (True, True),
    ),
]

fnames = []
for p in names:
    pp = list(p)
    pp[3] = p[3][0]
    fnames.append(tuple(pp))
    if "#" in p[0]:
        pp[0] = p[0].replace("#", "")
        pp[3] = p[3][1]
        fnames.append(tuple(pp))

rnames = [
    (
        "{series!c} {price} {year}",  # Capitalize
        False,
        "universal",
        "Cory doctorow's futuristic tales of the here and now 2007.cbz",
        does_not_raise(),
    ),
    (
        "{series!t} {price} {year}",  # Title Case
        False,
        "universal",
        "Cory Doctorow'S Futuristic Tales Of The Here And Now 2007.cbz",
        does_not_raise(),
    ),
    (
        "{series!S} {price} {year}",  # Swap Case
        False,
        "universal",
        "cORY dOCTOROW'S fUTURISTIC tALES OF THE hERE AND nOW 2007.cbz",
        does_not_raise(),
    ),
    (
        "{title!l} {price} {year}",  # Lowercase
        False,
        "universal",
        "anda's game 2007.cbz",
        does_not_raise(),
    ),
    (
        "{title!u} {price} {year}",  # Upper Case
        False,
        "universal",
        "ANDA'S GAME 2007.cbz",
        does_not_raise(),
    ),
    (
        "{title} {price} {year+}",  # Empty alternate value
        False,
        "universal",
        "Anda's Game.cbz",
        does_not_raise(),
    ),
    (
        "{title} {price} {year+year!u}",  # Alternate value Upper Case
        False,
        "universal",
        "Anda's Game YEAR.cbz",
        does_not_raise(),
    ),
    (
        "{title} {price} {year+year}",  # Alternate Value
        False,
        "universal",
        "Anda's Game year.cbz",
        does_not_raise(),
    ),
    (
        "{title} {price-0} {year}",  # Default value
        False,
        "universal",
        "Anda's Game 0 2007.cbz",
        does_not_raise(),
    ),
    (
        "{title} {price+0} {year}",  # Alternate Value
        False,
        "universal",
        "Anda's Game 2007.cbz",
        does_not_raise(),
    ),
    (
        "{series} #{issue} - {title} ({year}) ({price})",  # price should be none
        False,
        "universal",
        "Cory Doctorow's Futuristic Tales of the Here and Now #001 - Anda's Game (2007).cbz",
        does_not_raise(),
    ),
    (
        "{series} #{issue} - {title} {volume:02} ({year})",  # Ensure format specifier works
        False,
        "universal",
        "Cory Doctorow's Futuristic Tales of the Here and Now #001 - Anda's Game 01 (2007).cbz",
        does_not_raise(),
    ),
    (
        "{series} #{issue} - {title} ({year})({price})",  # price should be none, test no  space between ')('
        False,
        "universal",
        "Cory Doctorow's Futuristic Tales of the Here and Now #001 - Anda's Game (2007).cbz",
        does_not_raise(),
    ),
    (
        "{series} #{issue} - {title} ({year})  ({price})",  # price should be none, test double space ')  ('
        False,
        "universal",
        "Cory Doctorow's Futuristic Tales of the Here and Now #001 - Anda's Game (2007).cbz",
        does_not_raise(),
    ),
    (
        "{series} #{issue} - {title} ({year})",
        False,
        "universal",
        "Cory Doctorow's Futuristic Tales of the Here and Now #001 - Anda's Game (2007).cbz",
        does_not_raise(),
    ),
    (
        "{title} {web_link}",  # Ensure colon is replaced in metadata
        False,
        "universal",
        "Anda's Game https---comicvine.gamespot.com-cory-doctorows-futuristic-tales-of-the-here-and-no-4000-140529-.cbz",
        does_not_raise(),
    ),
    (
        "{title} {web_link}",  # Ensure slashes are replaced in metadata on linux/macos
        False,
        "Linux",
        "Anda's Game https:--comicvine.gamespot.com-cory-doctorows-futuristic-tales-of-the-here-and-no-4000-140529-.cbz",
        does_not_raise(),
    ),
    (
        "{series}:{title} #{issue} ({year})",  # on windows the ':' is replaced
        False,
        "universal",
        "Cory Doctorow's Futuristic Tales of the Here and Now-Anda's Game #001 (2007).cbz",
        does_not_raise(),
    ),
    (
        "{series}: {title} #{issue} ({year})",  # on windows the ':' is replaced
        False,
        "universal",
        "Cory Doctorow's Futuristic Tales of the Here and Now - Anda's Game #001 (2007).cbz",
        does_not_raise(),
    ),
    (
        "{series}: {title} #{issue} ({year})",  # on linux the ':' is preserved
        False,
        "Linux",
        "Cory Doctorow's Futuristic Tales of the Here and Now: Anda's Game #001 (2007).cbz",
        does_not_raise(),
    ),
    (
        "{publisher}/  {series} #{issue} - {title} ({year})",  # leading whitespace is removed when moving
        True,
        "universal",
        "IDW Publishing/Cory Doctorow's Futuristic Tales of the Here and Now #001 - Anda's Game (2007).cbz",
        does_not_raise(),
    ),
    (
        "{publisher}/  {series} #{issue} - {title} ({year})",  # leading whitespace is removed when only renaming
        False,
        "universal",
        "Cory Doctorow's Futuristic Tales of the Here and Now #001 - Anda's Game (2007).cbz",
        does_not_raise(),
    ),
    (
        r"{publisher}\  {series} #{issue} - {title} ({year})",  # backslashes separate directories
        False,
        "Linux",
        "Cory Doctorow's Futuristic Tales of the Here and Now #001 - Anda's Game (2007).cbz",
        does_not_raise(),
    ),
    (
        "{series} #  {issue} - {title} ({year})",  # double spaces are reduced to one
        False,
        "universal",
        "Cory Doctorow's Futuristic Tales of the Here and Now # 001 - Anda's Game (2007).cbz",
        does_not_raise(),
    ),
    (
        "{series} #{issue} - {locations!j} ({year})",
        False,
        "universal",
        "Cory Doctorow's Futuristic Tales of the Here and Now #001 - lonely cottage (2007).cbz",
        does_not_raise(),
    ),
    (
        "{series} #{issue} - {title} - {WriteR}, {EDITOR} ({year})",  # fields are case in-sensitive
        False,
        "universal",
        "Cory Doctorow's Futuristic Tales of the Here and Now #001 - Anda's Game - Dara Naraghi, Ted Adams (2007).cbz",
        does_not_raise(),
    ),
    (
        "{series} v{price} #{issue} ({year})",  # Remove previous text if value is ""
        False,
        "universal",
        "Cory Doctorow's Futuristic Tales of the Here and Now #001 (2007).cbz",
        does_not_raise(),
    ),
    (
        "{series} {price} #{issue} ({year})",  # Ensure that a single space remains
        False,
        "universal",
        "Cory Doctorow's Futuristic Tales of the Here and Now #001 (2007).cbz",
        does_not_raise(),
    ),
    (
        "{series} - {title}{price} #{issue} ({year})",  # Ensure removal before None values only impacts literal text
        False,
        "universal",
        "Cory Doctorow's Futuristic Tales of the Here and Now - Anda's Game #001 (2007).cbz",
        does_not_raise(),
    ),
    (
        "{series} - {title} {test} #{issue} ({year})",  # Test non-existent key
        False,
        "universal",
        "Cory Doctorow's Futuristic Tales of the Here and Now - Anda's Game {test} #001 (2007).cbz",
        does_not_raise(),
    ),
    (
        "{series} - {title} #{issue} ({year} {price})",  # Test null value in parenthesis with a non-null value
        False,
        "universal",
        "Cory Doctorow's Futuristic Tales of the Here and Now - Anda's Game #001 (2007).cbz",
        does_not_raise(),
    ),
    (
        "{series} - {title} #{issue} (of {price})",  # null value with literal text in parenthesis
        False,
        "universal",
        "Cory Doctorow's Futuristic Tales of the Here and Now - Anda's Game #001.cbz",
        does_not_raise(),
    ),
    (
        "{series} - {title} {1} #{issue} ({year})",  # Test numeric key
        False,
        "universal",
        "Cory Doctorow's Futuristic Tales of the Here and Now - Anda's Game {test} #001 (2007).cbz",
        pytest.raises(ValueError),
    ),
]

rfnames = [
    (None, lambda x: x.path.parent.absolute()),
    ("", lambda x: pathlib.Path(os.getcwd())),
    ("test", lambda x: (pathlib.Path(os.getcwd()) / "test")),
    (pathlib.Path(os.getcwd()) / "test", lambda x: pathlib.Path(os.getcwd()) / "test"),
]
