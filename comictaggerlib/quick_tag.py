from __future__ import annotations

import argparse
import contextlib
import itertools
import logging
import pathlib
import sqlite3
import statistics
import threading
from collections.abc import Callable, Iterable
from enum import auto
from functools import cached_property
from io import BytesIO
from typing import TYPE_CHECKING, NamedTuple, TypedDict, overload
from urllib.parse import urljoin

import requests
import settngs

from comicapi import comicarchive, utils
from comicapi.genericmetadata import GenericMetadata
from comicapi.issuestring import IssueString
from comictaggerlib.ctsettings.settngs_namespace import SettngsNS
from comictaggerlib.imagehasher import ImageHasher
from comictalker import ComicTalker

if TYPE_CHECKING:
    from _typeshed import SupportsRichComparison

logger = logging.getLogger(__name__)

__version__ = "0.1"


class HashType(utils.StrEnum):
    # Unknown = 'Unknown'
    PHASH = auto()
    DHASH = auto()
    AHASH = auto()

    def __repr__(self) -> str:
        return str(self)


class Hash(TypedDict):
    Hash: int
    Kind: HashType


class ID_dict(TypedDict):
    Domain: str
    ID: str


class ID(NamedTuple):
    Domain: str
    ID: str


class Result(TypedDict):
    Hash: Hash
    ID: ID_dict
    Distance: int
    EquivalentIDs: list[ID_dict]


class ResultList(NamedTuple):
    distance: int
    results: list[Result]


class Distance(NamedTuple):
    hash: HashType
    distance: int

    def __repr__(self) -> str:
        return f"{self.hash}={self.distance}"


class Hashes:
    hashes: tuple[Result, ...]
    id: ID

    modifier_scoring = {
        3: 64 / 64,
        2: 60 / 64,
        1: 58 / 64,
    }

    def __init__(
        self,
        *,
        hashes: Iterable[Result],
        domain: str | None,
        id: ID | None = None,  # noqa: A002
    ) -> None:
        de_dupe_hashes = {
            (x["Hash"]["Hash"], x["Hash"]["Kind"], x["ID"]["Domain"], x["ID"]["ID"]): x for x in hashes
        }.values()

        self.hashes = tuple(
            sorted(de_dupe_hashes, key=lambda x: list(HashType.__members__.values()).index(HashType(x["Hash"]["Kind"])))
        )
        self.count = len(self.hashes)
        if id is None:
            self.id = ID(**self.hash()["ID"])
        else:
            self.id = id

        if domain and self.id.Domain != domain:
            for _hash in self.hashes:
                for e_id in _hash["EquivalentIDs"]:
                    if e_id["Domain"] == domain:
                        self.id = ID(**e_id)

    @overload
    def hash(self) -> Result: ...
    @overload
    def hash(self, hash_type: HashType) -> Result | None: ...

    def hash(self, hash_type: HashType | None = None) -> Result | None:
        if hash_type:
            for _hash in self.hashes:
                if _hash["Hash"]["Kind"] == hash_type:
                    return _hash
            return None
        return self.hashes[0]

    @cached_property
    def distance(self) -> int:
        return int(statistics.mean(x["Distance"] for x in self.hashes))

    @cached_property
    def score(self) -> int:
        # Get the distances as a value between 0 and 1. Lowest value is 55/64 ~ 0.85
        hashes: list[float] = [(64 - x["Distance"]) / 64 for x in self.hashes][: len(self.modifier_scoring)]
        # Set missing values to the lowest possible match so we are comparing an equal number of values
        hashes.extend((64 - 9) // 64 for _ in range(len(self.modifier_scoring) - len(hashes)))

        mod = self.modifier_scoring[len(self.hashes)]
        # Add an extra mod value to bring the score up if there are more hashes
        hashes.append(mod)
        return int(statistics.mean(int(x * 100) for x in hashes))

    @cached_property
    def kinds(self) -> set[HashType]:
        return {HashType(x["Hash"]["Kind"]) for x in self.hashes}

    @cached_property
    def distances(self) -> tuple[Distance, ...]:
        return tuple(Distance(HashType(x["Hash"]["Kind"]), x["Distance"]) for x in self.hashes)

    @cached_property
    def exact(self) -> bool:
        return self.score >= 95 and len(self.hashes) > 1

    @cached_property
    def key(self) -> tuple[SupportsRichComparison, ...]:
        return (-self.count, tuple(x["Distance"] for x in self.hashes))

    def should_break(self, previous: Hashes) -> bool:
        group_limit = 3
        if (previous.count - self.count) == 1:
            group_limit = 2
        if (previous.count - self.count) == 2:
            group_limit = 0

        if (self.distance - previous.distance) > group_limit:
            return True

        if len(self.hashes) == 1 and self.hashes[0]["Hash"]["Kind"] == HashType.AHASH:
            if previous.count > 1:
                return True
        return False

    def __repr__(self) -> str:
        return f"Hashes(id={self.id!r}, count={self.count!r}, distance={self.distance!r}, score={self.score!r}, 'exact'={self.exact!r})"


class NameMatches(NamedTuple):
    confident_match: tuple[tuple[Hashes, GenericMetadata], ...]
    probable_match: tuple[tuple[Hashes, GenericMetadata], ...]


class IDCache:
    def __init__(self, cache_folder: pathlib.Path, version: str) -> None:
        self.cache_folder = cache_folder
        self.db_file = cache_folder / "bad_ids.db"
        self.version = version
        self.local: threading.Thread | None = None
        self.db: sqlite3.Connection | None = None

        self.create_cache_db()

    def clear_cache(self) -> None:
        try:
            self.close()
        except Exception:
            pass
        try:
            self.db_file.unlink(missing_ok=True)
        except Exception:
            pass

    def connect(self) -> sqlite3.Connection:
        if self.local != threading.current_thread():
            self.db = None
        if self.db is None:
            self.local = threading.current_thread()
            self.db = sqlite3.connect(self.db_file)
            self.db.row_factory = sqlite3.Row
            self.db.text_factory = str
        return self.db

    def close(self) -> None:
        if self.db is not None:
            self.db.close()
            self.db = None

    def create_cache_db(self) -> None:
        # create tables
        with self.connect() as con, contextlib.closing(con.cursor()) as cur:
            cur.execute("""CREATE TABLE IF NOT EXISTS bad_ids(
                domain      TEXT NOT NULL,
                id          TEXT NOT NULL,
                PRIMARY KEY (id, domain))""")

    def add_ids(self, bad_ids: set[ID]) -> None:
        with self.connect() as con, contextlib.closing(con.cursor()) as cur:

            for bad_id in bad_ids:
                cur.execute(
                    """INSERT into bad_ids (domain, ID) VALUES (?, ?) ON CONFLICT DO NOTHING""",
                    (bad_id.Domain, bad_id.ID),
                )

    def get_ids(self) -> dict[str, set[ID]]:
        # purge stale series info
        ids: dict[str, set[ID]] = utils.DefaultDict(default=lambda x: set())
        with self.connect() as con, contextlib.closing(con.cursor()) as cur:
            cur.execute(
                """SELECT * FROM bad_ids""",
            )

            for record in cur.fetchall():
                ids[record["domain"]] |= {ID(Domain=record["domain"], ID=record["id"])}

        return ids


def settings(manager: settngs.Manager) -> None:
    manager.add_setting(
        "--url",
        "-u",
        default="https://comic-hasher.narnian.us",
        type=utils.parse_url,
        help="Server to use for searching cover hashes",
    )
    manager.add_setting(
        "--max",
        default=8,
        type=int,
        help="Maximum score to allow. Lower score means more accurate",
    )
    manager.add_setting(
        "--aggressive-filtering",
        default=False,
        action=argparse.BooleanOptionalAction,
        help="Will filter out matches more aggressively",
    )
    manager.add_setting(
        "--hash",
        default=list(HashType),
        type=HashType,
        nargs="+",
        help="Pick what hashes you want to use to search (default: %(default)s)",
    )
    manager.add_setting(
        "--exact-only",
        default=True,
        action=argparse.BooleanOptionalAction,
        help="Skip non-exact matches if exact matches are found",
    )


KNOWN_BAD_IDS: dict[str, set[ID]] = utils.DefaultDict(
    {
        "comicvine.gamespot.com": {
            ID("comicvine.gamespot.com", "737049"),
            ID("comicvine.gamespot.com", "753078"),
            ID("comicvine.gamespot.com", "390219"),
        }
    },
    default=lambda x: set(),
)


def limit(results: Iterable[Hashes], limit: int) -> list[list[Hashes]]:
    hashes: list[list[Hashes]] = []
    r = list(results)
    for _, result_list in itertools.groupby(r, key=lambda r: r.count):
        result_l = list(result_list)
        hashes.append(sorted(result_l[:limit], key=lambda r: r.key))
        limit -= len(result_l)
        if limit <= 0:
            break
    return hashes


class QuickTag:
    def __init__(
        self, url: utils.Url, domain: str, talker: ComicTalker, config: SettngsNS, output: Callable[..., None]
    ):
        self.output = output
        self.url = url
        self.talker = talker
        self.domain = domain
        self.config = config
        self.bad_ids = IDCache(config.Runtime_Options__config.user_cache_dir, __version__)

        self.known_bad_ids = self.bad_ids.get_ids()
        for domain, bad_ids in KNOWN_BAD_IDS.items():
            self.known_bad_ids[domain] |= bad_ids

    def id_comic(
        self,
        ca: comicarchive.ComicArchive,
        tags: GenericMetadata,
        hashes: set[HashType],
        exact_only: bool,
        interactive: bool,
        aggressive_filtering: bool,
        max_hamming_distance: int,
    ) -> GenericMetadata | None:
        if not ca.seems_to_be_a_comic_archive():
            raise Exception(f"{ca.path} is not an archive")
        from PIL import Image

        cover_index = tags.get_cover_page_index_list()[0]
        cover_image = Image.open(BytesIO(ca.get_page(cover_index)))
        cover_image.load()
        self.limit = 30
        if aggressive_filtering:
            self.limit = 15

        self.output(f"Tagging: {ca.path}")

        self.output("hashing cover")
        phash = dhash = ahash = ""
        hasher = ImageHasher(image=cover_image)
        if HashType.AHASH in hashes:
            ahash = hex(hasher.average_hash())[2:]
        if HashType.DHASH in hashes:
            dhash = hex(hasher.difference_hash())[2:]
        if HashType.PHASH in hashes:
            phash = hex(hasher.perception_hash())[2:]

        self.output("Searching hashes")
        logger.info(
            "Searching with ahash=%s, dhash=%s, phash=%s",
            ahash,
            dhash,
            phash,
        )
        results = self.SearchHashes(max_hamming_distance, ahash, dhash, phash, exact_only)
        logger.debug("results=%s", results)
        if not results:
            self.output("No results found for QuickTag")
            return None

        IDs = [
            Hashes(hashes=(g[1] for g in group), id=i, domain=self.domain)
            for i, group in itertools.groupby(
                sorted(((ID(**r["ID"]), (r)) for r in results), key=lambda r: (r[0], r[1]["Hash"]["Kind"])),
                key=lambda r: r[0],
            )
        ]
        IDs = sorted(IDs, key=lambda r: r.key)
        self.output(f"Total number of IDs found: {len(IDs)}")
        logger.debug("IDs=%s", IDs)

        aggressive_results, display_results = self.match_results(IDs, aggressive_filtering)
        chosen_result = self.display_results(
            aggressive_results, display_results, ca, tags, interactive, aggressive_filtering
        )
        if chosen_result:
            return self.talker.fetch_comic_data(issue_id=chosen_result.ID, on_rate_limit=None)
        return None

    def SearchHashes(
        self, max_hamming_distance: int, ahash: str, dhash: str, phash: str, exact_only: bool
    ) -> list[Result]:

        resp = requests.get(
            urljoin(self.url.url, "/match_cover_hash"),
            params={
                "max": str(max_hamming_distance),
                "ahash": ahash,
                "dhash": dhash,
                "phash": phash,
                "exactOnly": str(exact_only),
            },
        )
        if resp.status_code != 200:
            try:
                text = resp.json()["msg"]
            except Exception:
                text = resp.text
            if text == "No hashes found":
                return []
            logger.error("message from server: %s", text)
            raise Exception(f"Failed to retrieve results from the server: {text}")
        return resp.json()["results"]

    def get_mds(self, ids: Iterable[ID]) -> list[GenericMetadata]:
        md_results: list[GenericMetadata] = []
        ids = set(ids)
        relevant_ids = {md_id for md_id in ids if md_id.Domain == self.domain}

        all_ids = {md_id.ID for md_id in ids if md_id.Domain == self.domain}

        logger.debug("Removed %d ids that are not for %s", len(ids - relevant_ids), self.domain)

        self.output(f"Retrieving basic {self.talker.name} data for {len(relevant_ids)} results")
        # Try to do a bulk fetch of basic issue data, if we have more than 1 id
        if hasattr(self.talker, "fetch_comics") and len(all_ids) > 1:
            md_results = self.talker.fetch_comics(issue_ids=list(all_ids), on_rate_limit=None)
        else:
            for md_id in all_ids:
                md_results.append(self.talker.fetch_comic_data(issue_id=md_id, on_rate_limit=None))

        retrieved_ids = {ID(self.domain, md.issue_id) for md in md_results}  # type: ignore[arg-type]
        bad_ids = relevant_ids - retrieved_ids
        if bad_ids:
            logger.debug("Adding bad IDs to known list: %s", bad_ids)
            self.known_bad_ids[self.domain] |= bad_ids
            self.bad_ids.add_ids(bad_ids)
        return md_results

    def _filter_hash_results(self, results: Iterable[Hashes]) -> list[Hashes]:
        groups: list[Hashes] = []
        previous: dict[HashType, None | int] = dict.fromkeys(HashType)
        skipped: list[Hashes] = []
        for hash_group in sorted(results, key=lambda r: r.key):
            b = []
            if skipped:
                skipped.append(hash_group)
            for _hash in hash_group.hashes:
                prev = previous[_hash["Hash"]["Kind"]]
                b.append(prev is not None and (_hash["Distance"] - prev) > 3)
                previous[_hash["Hash"]["Kind"]] = _hash["Distance"]
            if b and all(b):
                skipped.append(hash_group)

            groups.append(hash_group)
        if skipped:
            logger.debug(
                "Filtering bottom %d of %s results as they seem to all be substantially worse",
                len(skipped),
                len(skipped) + len(groups),
            )
        return groups

    def _filter_hashes(self, hashes: Iterable[Hashes], aggressive_filtering: bool) -> tuple[list[Hashes], list[Hashes]]:
        hashes = list(hashes)
        if not hashes:
            return [], []

        aggressive_skip = False
        skipped: list[Hashes] = []
        hashes = sorted(hashes, key=lambda r: r.key)

        groups: list[Hashes] = [hashes[0]]
        aggressive_groups = [hashes[0]]
        previous = hashes[0]
        for group in hashes[1:]:
            group_limit = 3
            if (group.distance - previous.distance) > group_limit or skipped:
                skipped.append(group)
            elif aggressive_filtering:
                if group.should_break(previous):
                    aggressive_skip = True

            if not aggressive_skip:
                aggressive_groups.append(group)

            groups.append(group)
            previous = group
        if skipped or len(groups) - len(aggressive_groups) > 0:
            logger.debug("skipping (%d|%d)/%d results", len(skipped), len(groups) - len(aggressive_groups), len(hashes))
        return aggressive_groups, groups

    def match_results(self, results: list[Hashes], aggressive_filtering: bool) -> tuple[list[Hashes], list[Hashes]]:
        exact = [r for r in results if r.exact]

        limited = limit(results, self.limit)
        logger.debug("Only looking at the top %d out of %d hash scores", min(len(results), self.limit), len(results))

        # Filter out results if there is a gap > 3 in distance
        for i, hashed_results in enumerate(limited):
            limited[i] = self._filter_hash_results(hashed_results)

        aggressive, normal = self._filter_hashes(itertools.chain.from_iterable(limited), aggressive_filtering)

        if exact:
            self.output(f"{len(exact)} exact result found. Ignoring any others: {exact}")
            aggressive = exact  # I've never seen more than 2 "exact" matches
        logger.debug("Filtering reduced to %d hash scores", len(aggressive))
        return aggressive, normal

    def match_names(self, tags: GenericMetadata, results: list[tuple[Hashes, GenericMetadata]]) -> NameMatches:
        confident_match: list[tuple[Hashes, GenericMetadata]] = []
        probable_match: list[tuple[Hashes, GenericMetadata]] = []
        for result, md in results:
            assert md.issue_id
            assert md.series
            assert md.issue
            titles_match = tags.series and utils.titles_match(tags.series, md.series, threshold=70)
            issues_match = tags.issue and IssueString(tags.issue).as_string() == IssueString(md.issue).as_string()
            if titles_match and issues_match:
                confident_match.append((result, md))
            elif (titles_match or issues_match) and result.distance < 6:
                probable_match.append((result, md))
        return NameMatches(tuple(confident_match), tuple(probable_match))

    def check_matches(
        self,
        results: list[Hashes],
        tags: GenericMetadata,
    ) -> Hashes | None:
        # This matching is only useful with a series name or an issue number
        if not (tags.series or tags.issue):
            return None
        limited = limit((r for r in results if r.id not in KNOWN_BAD_IDS.get(self.domain, set())), self.limit)

        ids = {r.id: r for r in itertools.chain.from_iterable(limited)}

        mds = [(ids[ID(self.domain, md.issue_id)], md) for md in self.get_mds(ids)]  # type: ignore[arg-type]

        matches = self.match_names(tags, mds)

        if len(matches.confident_match) == 1:
            result, md = matches.confident_match[0]
            self.output(f"Found confident {result.distances} match with series name {md.series!r}")
            return result

        elif len(matches.probable_match) == 1:
            result, md = matches.probable_match[0]
            self.output(f"Found probable {result.distances} match with series name {md.series!r}")
            return result
        return None

    def display_results(
        self,
        results: list[Hashes],
        display_results: list[Hashes],
        ca: comicarchive.ComicArchive,
        tags: GenericMetadata,
        interactive: bool,
        aggressive_filtering: bool,
    ) -> ID | None:
        if not results:
            return None
        # we only return early if we don't have a series name or issue as get_mds will pull the full info if there is only one result
        if (
            not (tags.series or tags.issue)
            and not interactive
            and aggressive_filtering
            and len(results) == 1
            and (results[0].distance < 4 or results[0].score >= 95)
        ):
            self.output("Found a single match < 4. Assuming it's correct")
            return results[0].id

        limited = limit((r for r in results if r.id not in KNOWN_BAD_IDS.get(self.domain, set())), self.limit)
        ids = {r.id for r in itertools.chain.from_iterable(limited)}

        matched_result = None
        # if we think we only have 1 result we try to optimize and only use a single request
        # otherwise we benefit from matching the filename against more matches
        if len(results) == 1:
            matched_result = self.check_matches(results, tags)
        if matched_result is None:
            matched_result = self.check_matches(display_results, tags)
            if matched_result is not None:
                return matched_result.id
        if not interactive:
            return None

        limited_interactive = limit(
            (r for r in display_results if r.id not in KNOWN_BAD_IDS.get(self.domain, set())), self.limit
        )
        ids_interactive = {r.id: r for r in itertools.chain.from_iterable(limited_interactive)}

        mds_interactive = [(ids_interactive[ID(self.domain, md.issue_id)], md) for md in self.get_mds(ids_interactive)]  # type: ignore[arg-type]

        interactive_only_ids = set(ids_interactive).difference(ids)

        items = sorted(mds_interactive, key=lambda r: r[0].key)
        self.output(
            f"\nSelect result for {ca.path.name}, page count: {ca.get_number_of_pages()} :\n", force_output=True
        )
        for counter, r in enumerate(items, 1):
            hashes, md = r
            self.output(
                "{}{:2}. {:6} {!s} distance: {}({}) - {} #{} [{}] ({}/{}) - {}".format(
                    " " if hashes.id in interactive_only_ids else "*",
                    counter,
                    hashes.id.ID,
                    hashes.distances,
                    hashes.distance,
                    hashes.score,
                    md.series or "",
                    md.issue or "",
                    md.publisher or "",
                    md.month or "",
                    md.year or "",
                    md.title or "",
                ),
                force_output=True,
            )
        while True:
            i = input(
                f'Please select a result to tag the comic with or "q" to quit: [1-{len(results)}] ',
            ).casefold()
            if i.isdigit() and int(i) in range(1, len(results) + 1):
                break
            if i.startswith("q"):
                self.output("User quit without saving metadata")
                return None
        self.output("")

        return items[int(i) - 1][0].id
