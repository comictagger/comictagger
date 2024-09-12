from __future__ import annotations

import argparse
import itertools
import logging
from enum import auto
from io import BytesIO
from typing import Callable, TypedDict, cast
from urllib.parse import urljoin

import requests
import settngs

from comicapi import comicarchive, utils
from comicapi.genericmetadata import GenericMetadata
from comicapi.issuestring import IssueString
from comictaggerlib.ctsettings.settngs_namespace import SettngsNS
from comictaggerlib.imagehasher import ImageHasher
from comictalker import ComicTalker

logger = logging.getLogger(__name__)

__version__ = "0.1"


class HashType(utils.StrEnum):
    AHASH = auto()
    DHASH = auto()
    PHASH = auto()


class SimpleResult(TypedDict):
    Distance: int
    # Mapping of domains (eg comicvine.gamespot.com) to IDs
    IDList: dict[str, list[str]]


class Hash(TypedDict):
    Hash: int
    Kind: str


class Result(TypedDict):
    # Mapping of domains (eg comicvine.gamespot.com) to IDs
    IDs: dict[str, list[str]]
    Distance: int
    Hash: Hash


def ihash(types: str) -> list[HashType]:
    result: list[HashType] = []
    types = types.casefold()
    choices = ", ".join(HashType)
    for typ in utils.split(types, ","):
        if typ not in list(HashType):
            raise argparse.ArgumentTypeError(f"invalid choice: {typ} (choose from {choices.upper()})")
        result.append(HashType[typ.upper()])

    if not result:
        raise argparse.ArgumentTypeError(f"invalid choice: {types} (choose from {choices.upper()})")
    return result


def settings(manager: settngs.Manager) -> None:
    manager.add_setting(
        "--url",
        "-u",
        default="https://comic-hasher.narnian.us",
        type=utils.parse_url,
        help="Website to use for searching cover hashes",
    )
    manager.add_setting(
        "--max",
        default=8,
        type=int,
        help="Maximum score to allow. Lower score means more accurate",
    )
    manager.add_setting(
        "--simple",
        default=False,
        action=argparse.BooleanOptionalAction,
        help="Whether to retrieve simple results or full results",
    )
    manager.add_setting(
        "--aggressive-filtering",
        default=False,
        action=argparse.BooleanOptionalAction,
        help="Will filter out worse matches if better matches are found",
    )
    manager.add_setting(
        "--hash",
        default="ahash, dhash, phash",
        type=ihash,
        help="Pick what hashes you want to use to search (default: %(default)s)",
    )
    manager.add_setting(
        "--exact-only",
        default=True,
        action=argparse.BooleanOptionalAction,
        help="Skip non-exact matches if we have exact matches",
    )


class QuickTag:
    def __init__(
        self, url: utils.Url, domain: str, talker: ComicTalker, config: SettngsNS, output: Callable[[str], None]
    ):
        self.output = output
        self.url = url
        self.talker = talker
        self.domain = domain
        self.config = config

    def id_comic(
        self,
        ca: comicarchive.ComicArchive,
        tags: GenericMetadata,
        simple: bool,
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

        self.output(f"Tagging: {ca.path}")

        self.output("hashing cover")
        phash = dhash = ahash = ""
        hasher = ImageHasher(image=cover_image)
        if HashType.AHASH in hashes:
            ahash = hex(hasher.average_hash())[2:]
        if HashType.DHASH in hashes:
            dhash = hex(hasher.difference_hash())[2:]
        if HashType.PHASH in hashes:
            phash = hex(hasher.p_hash())[2:]

        logger.info(f"Searching with {ahash=}, {dhash=}, {phash=}")

        self.output("Searching hashes")
        results = self.SearchHashes(simple, max_hamming_distance, ahash, dhash, phash, exact_only)
        logger.debug(f"{results=}")

        if simple:
            filtered_simple_results = self.filter_simple_results(
                cast(list[SimpleResult], results), interactive, aggressive_filtering
            )
            metadata_simple_results = self.get_simple_results(filtered_simple_results)
            chosen_result = self.display_simple_results(metadata_simple_results, tags, interactive)
        else:
            filtered_results = self.filter_results(cast(list[Result], results), interactive, aggressive_filtering)
            metadata_results = self.get_results(filtered_results)
            chosen_result = self.display_results(metadata_results, tags, interactive)

        return self.talker.fetch_comic_data(issue_id=chosen_result.issue_id)

    def SearchHashes(
        self, simple: bool, max_hamming_distance: int, ahash: str, dhash: str, phash: str, exact_only: bool
    ) -> list[SimpleResult] | list[Result]:

        resp = requests.get(
            urljoin(self.url.url, "/match_cover_hash"),
            params={
                "simple": str(simple),
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

    def get_mds(self, results: list[SimpleResult] | list[Result]) -> list[GenericMetadata]:
        md_results: list[GenericMetadata] = []
        results.sort(key=lambda r: r["Distance"])
        all_ids = set()
        for res in results:
            all_ids.update(res.get("IDList", res.get("IDs", {})).get(self.domain, []))  # type: ignore[attr-defined]

        self.output(f"Retrieving basic {self.talker.name} data")
        # Try to do a bulk feth of basic issue data
        if hasattr(self.talker, "fetch_comics"):
            md_results = self.talker.fetch_comics(issue_ids=list(all_ids))
        else:
            for md_id in all_ids:
                md_results.append(self.talker.fetch_comic_data(issue_id=md_id))
        return md_results

    def get_simple_results(self, results: list[SimpleResult]) -> list[tuple[int, GenericMetadata]]:
        md_results = []
        mds = self.get_mds(results)

        # Re-associate the md to the distance
        for res in results:
            for md in mds:
                if md.issue_id in res["IDList"].get(self.domain, []):
                    md_results.append((res["Distance"], md))
        return md_results

    def get_results(self, results: list[Result]) -> list[tuple[int, Hash, GenericMetadata]]:
        md_results = []
        mds = self.get_mds(results)

        # Re-associate the md to the distance
        for res in results:
            for md in mds:
                if md.issue_id in res["IDs"].get(self.domain, []):
                    md_results.append((res["Distance"], res["Hash"], md))
        return md_results

    def filter_simple_results(
        self, results: list[SimpleResult], interactive: bool, aggressive_filtering: bool
    ) -> list[SimpleResult]:
        # If there is a single exact match return it
        exact = [r for r in results if r["Distance"] == 0]
        if len(exact) == 1:
            logger.info("Exact result found. Ignoring any others")
            return exact

        # If ther are more than 4 results and any are better than 6 return the first group of results
        if len(results) > 4:
            dist: list[tuple[int, list[SimpleResult]]] = []
            filtered_results: list[SimpleResult] = []
            for distance, group in itertools.groupby(results, key=lambda r: r["Distance"]):
                dist.append((distance, list(group)))
            if aggressive_filtering and dist[0][0] < 6:
                logger.info(f"Aggressive filtering is enabled. Dropping matches above {dist[0]}")
                for _, res in dist[:1]:
                    filtered_results.extend(res)
                logger.debug(f"{filtered_results=}")
                return filtered_results
        return results

    def filter_results(self, results: list[Result], interactive: bool, aggressive_filtering: bool) -> list[Result]:
        ahash_results = sorted([r for r in results if r["Hash"]["Kind"] == "ahash"], key=lambda r: r["Distance"])
        dhash_results = sorted([r for r in results if r["Hash"]["Kind"] == "dhash"], key=lambda r: r["Distance"])
        phash_results = sorted([r for r in results if r["Hash"]["Kind"] == "phash"], key=lambda r: r["Distance"])
        hash_results = [phash_results, dhash_results, ahash_results]

        # If any of the hash types have a single exact match return it. Prefer phash for no particular reason
        for hashed_result in hash_results:
            exact = [r for r in hashed_result if r["Distance"] == 0]
            if len(exact) == 1:
                logger.info(f"Exact {exact[0]['Hash']['Kind']} result found. Ignoring any others")
                return exact

        results_filtered = False
        # If any of the hash types have more than 4 results and they have results better than 6 return the first group of results for each hash type
        for i, hashed_results in enumerate(hash_results):
            filtered_results: list[Result] = []
            if len(hashed_results) > 4:
                dist: list[tuple[int, list[Result]]] = []
                for distance, group in itertools.groupby(hashed_results, key=lambda r: r["Distance"]):
                    dist.append((distance, list(group)))
                if aggressive_filtering and dist[0][0] < 6:
                    logger.info(
                        f"Aggressive filtering is enabled. Dropping {dist[0][1][0]['Hash']['Kind']} matches above {dist[0][0]}"
                    )
                    for _, res in dist[:1]:
                        filtered_results.extend(res)

            if filtered_results:
                hash_results[i] = filtered_results
                results_filtered = True
        if results_filtered:
            logger.debug(f"filtered_results={list(itertools.chain(*hash_results))}")
        return list(itertools.chain(*hash_results))

    def display_simple_results(
        self, md_results: list[tuple[int, GenericMetadata]], tags: GenericMetadata, interactive: bool
    ) -> GenericMetadata:
        if len(md_results) < 1:
            return GenericMetadata()
        if len(md_results) == 1 and md_results[0][0] <= 4:
            self.output("Found a single match <=4. Assuming it's correct")
            return md_results[0][1]
        series_match: list[GenericMetadata] = []
        for score, md in md_results:
            if (
                score < 10
                and tags.series
                and md.series
                and utils.titles_match(tags.series, md.series)
                and IssueString(tags.issue).as_string() == IssueString(md.issue).as_string()
            ):
                series_match.append(md)
        if len(series_match) == 1:
            self.output(f"Found match with series name {series_match[0].series!r}")
            return series_match[0]

        if not interactive:
            return GenericMetadata()

        md_results.sort(key=lambda r: (r[0], len(r[1].publisher or "")))
        for counter, r in enumerate(md_results, 1):
            self.output(
                "    {:2}. score: {} [{:15}] ({:02}/{:04}) - {} #{} - {}".format(
                    counter,
                    r[0],
                    r[1].publisher,
                    r[1].month or 0,
                    r[1].year or 0,
                    r[1].series,
                    r[1].issue,
                    r[1].title,
                ),
            )
        while True:
            i = input(
                f'Please select a result to tag the comic with or "q" to quit: [1-{len(md_results)}] ',
            ).casefold()
            if i.isdigit() and int(i) in range(1, len(md_results) + 1):
                break
            if i == "q":
                logger.warning("User quit without saving metadata")
                return GenericMetadata()

        return md_results[int(i) - 1][1]

    def display_results(
        self,
        md_results: list[tuple[int, Hash, GenericMetadata]],
        tags: GenericMetadata,
        interactive: bool,
    ) -> GenericMetadata:
        if len(md_results) < 1:
            return GenericMetadata()
        if len(md_results) == 1 and md_results[0][0] <= 4:
            self.output("Found a single match <=4. Assuming it's correct")
            return md_results[0][2]
        series_match: dict[str, tuple[int, Hash, GenericMetadata]] = {}
        for score, cover_hash, md in md_results:
            if (
                score < 10
                and tags.series
                and md.series
                and utils.titles_match(tags.series, md.series)
                and IssueString(tags.issue).as_string() == IssueString(md.issue).as_string()
            ):
                assert md.issue_id
                series_match[md.issue_id] = (score, cover_hash, md)

        if len(series_match) == 1:
            score, cover_hash, md = list(series_match.values())[0]
            self.output(f"Found {cover_hash['Kind']} {score=} match with series name {md.series!r}")
            return md
        if not interactive:
            return GenericMetadata()
        md_results.sort(key=lambda r: (r[0], len(r[2].publisher or ""), r[1]["Kind"]))
        for counter, r in enumerate(md_results, 1):
            self.output(
                "    {:2}. score: {} {}: {:064b} [{:15}] ({:02}/{:04}) - {} #{} - {}".format(
                    counter,
                    r[0],
                    r[1]["Kind"],
                    r[1]["Hash"],
                    r[2].publisher or "",
                    r[2].month or 0,
                    r[2].year or 0,
                    r[2].series or "",
                    r[2].issue or "",
                    r[2].title or "",
                ),
            )
        while True:
            i = input(
                f'Please select a result to tag the comic with or "q" to quit: [1-{len(md_results)}] ',
            ).casefold()
            if i.isdigit() and int(i) in range(1, len(md_results) + 1):
                break
            if i == "q":
                self.output("User quit without saving metadata")
                return GenericMetadata()

        return md_results[int(i) - 1][2]
