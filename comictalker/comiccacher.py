"""A python class to manage caching of metadata from comic sources"""
#
# Copyright 2012-2014 ComicTagger Authors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
from __future__ import annotations

import dataclasses
import datetime
import json
import logging
import os
import pathlib
import sqlite3
from typing import Any

from comictalker.resulttypes import ComicIssue, ComicSeries, Credit

logger = logging.getLogger(__name__)


class ComicCacher:
    def __init__(self, cache_folder: pathlib.Path, version: str) -> None:
        self.cache_folder = cache_folder
        self.db_file = cache_folder / "comic_cache.db"
        self.version_file = cache_folder / "cache_version.txt"
        self.version = version

        # verify that cache is from same version as this one
        data = ""
        try:
            with open(self.version_file, "rb") as f:
                data = f.read().decode("utf-8")
                f.close()
        except Exception:
            pass
        if data != version:
            self.clear_cache()

        if not os.path.exists(self.db_file):
            self.create_cache_db()

    def clear_cache(self) -> None:
        try:
            os.unlink(self.db_file)
        except Exception:
            pass
        try:
            os.unlink(self.version_file)
        except Exception:
            pass

    def create_cache_db(self) -> None:
        # create the version file
        with open(self.version_file, "w", encoding="utf-8") as f:
            f.write(self.version)

        # this will wipe out any existing version
        open(self.db_file, "wb").close()

        con = sqlite3.connect(self.db_file)
        con.row_factory = sqlite3.Row

        # create tables
        with con:
            cur = con.cursor()
            # source_name,name,id,start_year,publisher,image,description,count_of_issues
            cur.execute(
                "CREATE TABLE SeriesSearchCache("
                + "timestamp DATE DEFAULT (datetime('now','localtime')),"
                + "id TEXT NOT NULL,"
                + "source_name TEXT NOT NULL,"
                + "search_term TEXT,"
                + "PRIMARY KEY (id, source_name, search_term))"
            )

            cur.execute(
                "CREATE TABLE Series("
                + "timestamp DATE DEFAULT (datetime('now','localtime')), "
                + "id TEXT NOT NULL,"
                + "source_name TEXT NOT NULL,"
                + "name TEXT,"
                + "publisher TEXT,"
                + "count_of_issues INT,"
                + "count_of_volumes INT,"
                + "start_year INT,"
                + "image_url TEXT,"
                + "aliases TEXT,"  # Newline separated
                + "description TEXT,"
                + "genres TEXT,"  # Newline separated. For filtering etc.
                + "format TEXT,"
                + "PRIMARY KEY (id, source_name))"
            )

            cur.execute(
                "CREATE TABLE Issues("
                + "timestamp DATE DEFAULT (datetime('now','localtime')), "
                + "id TEXT NOT NULL,"
                + "source_name TEXT NOT NULL,"
                + "series_id TEXT,"
                + "name TEXT,"
                + "issue_number TEXT,"
                + "image_url TEXT,"
                + "thumb_url TEXT,"
                + "cover_date TEXT,"
                + "site_detail_url TEXT,"
                + "description TEXT,"
                + "aliases TEXT,"  # Newline separated
                + "alt_image_urls TEXT,"  # Newline separated URLs
                + "characters TEXT,"  # Newline separated
                + "locations TEXT,"  # Newline separated
                + "credits TEXT,"  # JSON: "{"name": "Bob Shakespeare", "role": "Writer"}"
                + "teams TEXT,"  # Newline separated
                + "story_arcs TEXT,"  # Newline separated
                + "genres TEXT,"  # Newline separated
                + "tags TEXT,"  # Newline separated
                + "critical_rating FLOAT,"
                + "manga TEXT,"  # Yes/YesAndRightToLeft/No
                + "maturity_rating TEXT,"
                + "language TEXT,"
                + "country TEXT,"
                + "volume TEXT,"
                + "complete BOOL,"  # Is the data complete? Includes characters, locations, credits.
                + "PRIMARY KEY (id, source_name))"
            )

    def add_search_results(self, source_name: str, search_term: str, ct_search_results: list[ComicSeries]) -> None:
        con = sqlite3.connect(self.db_file)
        con.row_factory = sqlite3.Row

        with con:
            con.text_factory = str
            cur = con.cursor()

            # remove all previous entries with this search term
            cur.execute(
                "DELETE FROM SeriesSearchCache WHERE search_term = ? AND source_name = ?",
                [search_term.casefold(), source_name],
            )

            # now add in new results
            for record in ct_search_results:
                cur.execute(
                    "INSERT INTO SeriesSearchCache (source_name, search_term, id) VALUES(?, ?, ?)",
                    (source_name, search_term.casefold(), record.id),
                )

                data = {
                    "id": record.id,
                    "source_name": source_name,
                    "name": record.name,
                    "publisher": record.publisher,
                    "count_of_issues": record.count_of_issues,
                    "count_of_volumes": record.count_of_volumes,
                    "start_year": record.start_year,
                    "image_url": record.image_url,
                    "description": record.description,
                    "genres": "\n".join(record.genres),
                    "format": record.format,
                    "timestamp": datetime.datetime.now(),
                    "aliases": "\n".join(record.aliases),
                }
                self.upsert(cur, "series", data)

    def get_search_results(self, source_name: str, search_term: str) -> list[ComicSeries]:
        results = []
        con = sqlite3.connect(self.db_file)
        con.row_factory = sqlite3.Row
        with con:
            con.text_factory = str
            cur = con.cursor()

            cur.execute(
                "SELECT * FROM SeriesSearchCache INNER JOIN Series on"
                + " SeriesSearchCache.id=Series.id AND SeriesSearchCache.source_name=Series.source_name"
                + " WHERE search_term=? AND SeriesSearchCache.source_name=?",
                [search_term.casefold(), source_name],
            )

            rows = cur.fetchall()
            # now process the results
            for record in rows:
                result = ComicSeries(
                    id=record["id"],
                    name=record["name"],
                    publisher=record["publisher"],
                    count_of_issues=record["count_of_issues"],
                    count_of_volumes=record["count_of_volumes"],
                    start_year=record["start_year"],
                    image_url=record["image_url"],
                    aliases=record["aliases"].strip().splitlines(),
                    description=record["description"],
                    genres=record["genres"].strip().splitlines(),
                    format=record["format"],
                )

                results.append(result)

        return results

    def add_series_info(self, source_name: str, series_record: ComicSeries) -> None:
        con = sqlite3.connect(self.db_file)
        con.row_factory = sqlite3.Row

        with con:
            cur = con.cursor()

            timestamp = datetime.datetime.now()

            data = {
                "id": series_record.id,
                "source_name": source_name,
                "name": series_record.name,
                "publisher": series_record.publisher,
                "count_of_issues": series_record.count_of_issues,
                "count_of_volumes": series_record.count_of_volumes,
                "start_year": series_record.start_year,
                "image_url": series_record.image_url,
                "description": series_record.description,
                "genres": "\n".join(series_record.genres),
                "format": series_record.format,
                "timestamp": timestamp,
                "aliases": "\n".join(series_record.aliases),
            }
            self.upsert(cur, "series", data)

    def add_series_issues_info(self, source_name: str, series_issues: list[ComicIssue]) -> None:
        con = sqlite3.connect(self.db_file)
        con.row_factory = sqlite3.Row

        with con:
            cur = con.cursor()

            timestamp = datetime.datetime.now()

            # add in issues

            for issue in series_issues:
                data = {
                    "id": issue.id,
                    "series_id": issue.series.id,
                    "source_name": source_name,
                    "name": issue.name,
                    "issue_number": issue.issue_number,
                    "volume": issue.volume,
                    "site_detail_url": issue.site_detail_url,
                    "cover_date": issue.cover_date,
                    "image_url": issue.image_url,
                    "description": issue.description,
                    "timestamp": timestamp,
                    "aliases": "\n".join(issue.aliases),
                    "alt_image_urls": "\n".join(issue.alt_image_urls),
                    "characters": "\n".join(issue.characters),
                    "locations": "\n".join(issue.locations),
                    "teams": "\n".join(issue.teams),
                    "story_arcs": "\n".join(issue.story_arcs),
                    "genres": "\n".join(issue.genres),
                    "tags": "\n".join(issue.tags),
                    "critical_rating": issue.critical_rating,
                    "manga": issue.manga,
                    "maturity_rating": issue.maturity_rating,
                    "language": issue.language,
                    "country": issue.country,
                    "credits": json.dumps([dataclasses.asdict(x) for x in issue.credits]),
                    "complete": issue.complete,
                }
                self.upsert(cur, "issues", data)

    def get_series_info(self, series_id: str, source_name: str, purge: bool = True) -> ComicSeries | None:
        result: ComicSeries | None = None

        con = sqlite3.connect(self.db_file)
        con.row_factory = sqlite3.Row
        with con:
            cur = con.cursor()
            con.text_factory = str

            if purge:
                # purge stale series info
                a_week_ago = datetime.datetime.today() - datetime.timedelta(days=7)
                cur.execute("DELETE FROM Series WHERE timestamp  < ?", [str(a_week_ago)])

            # fetch
            cur.execute("SELECT * FROM Series WHERE id=? AND source_name=?", [series_id, source_name])

            row = cur.fetchone()

            if row is None:
                return result

            # since ID is primary key, there is only one row
            result = ComicSeries(
                id=row["id"],
                name=row["name"],
                publisher=row["publisher"],
                count_of_issues=row["count_of_issues"],
                count_of_volumes=row["count_of_volumes"],
                start_year=row["start_year"],
                image_url=row["image_url"],
                aliases=row["aliases"].strip().splitlines(),
                description=row["description"],
                genres=row["genres"].strip().splitlines(),
                format=row["format"],
            )

        return result

    def get_series_issues_info(self, series_id: str, source_name: str) -> list[ComicIssue]:
        # get_series_info should only fail if someone is doing something weird
        series = self.get_series_info(series_id, source_name, False) or ComicSeries(
            id=series_id,
            name="",
            description="",
            genres=[],
            image_url="",
            publisher="",
            start_year=None,
            aliases=[],
            count_of_issues=None,
            count_of_volumes=None,
            format=None,
        )
        con = sqlite3.connect(self.db_file)
        con.row_factory = sqlite3.Row
        with con:
            cur = con.cursor()
            con.text_factory = str

            # purge stale issue info - probably issue data won't change
            # much....
            a_week_ago = datetime.datetime.today() - datetime.timedelta(days=7)
            cur.execute("DELETE FROM Issues WHERE timestamp  < ?", [str(a_week_ago)])

            # fetch
            results: list[ComicIssue] = []

            cur.execute("SELECT * FROM Issues WHERE series_id=? AND source_name=?", [series_id, source_name])
            rows = cur.fetchall()

            # now process the results
            for row in rows:
                credits = []
                try:
                    for credit in json.loads(row["credits"]):
                        credits.append(Credit(**credit))
                except Exception:
                    logger.exception("credits failed")
                record = ComicIssue(
                    series=series,
                    credits=credits,
                    id=row["id"],
                    name=row["name"],
                    issue_number=row["issue_number"],
                    image_url=row["image_url"],
                    cover_date=row["cover_date"],
                    site_detail_url=row["site_detail_url"],
                    description=row["description"],
                    aliases=row["aliases"].strip().splitlines(),
                    alt_image_urls=row["alt_image_urls"].strip().splitlines(),
                    characters=row["characters"].strip().splitlines(),
                    locations=row["locations"].strip().splitlines(),
                    teams=row["teams"].strip().splitlines(),
                    story_arcs=row["story_arcs"].strip().splitlines(),
                    genres=row["genres"].strip().splitlines(),
                    tags=row["tags"].strip().splitlines(),
                    critical_rating=row["critical_rating"],
                    manga=row["manga"],
                    maturity_rating=row["maturity_rating"],
                    language=row["language"],
                    country=row["country"],
                    volume=row["volume"],
                    complete=bool(["complete"]),
                )

                results.append(record)

        return results

    def get_issue_info(self, issue_id: int, source_name: str) -> ComicIssue | None:
        con = sqlite3.connect(self.db_file)
        con.row_factory = sqlite3.Row
        with con:
            cur = con.cursor()
            con.text_factory = str

            # purge stale issue info - probably issue data won't change
            # much....
            a_week_ago = datetime.datetime.today() - datetime.timedelta(days=7)
            cur.execute("DELETE FROM Issues WHERE timestamp  < ?", [str(a_week_ago)])

            cur.execute("SELECT * FROM Issues WHERE id=? AND source_name=?", [issue_id, source_name])
            row = cur.fetchone()

            record = None

            if row:
                # get_series_info should only fail if someone is doing something weird
                series = self.get_series_info(row["id"], source_name, False) or ComicSeries(
                    id=row["id"],
                    name="",
                    description="",
                    genres=[],
                    image_url="",
                    publisher="",
                    start_year=None,
                    aliases=[],
                    count_of_issues=None,
                    count_of_volumes=None,
                    format=None,
                )

                # now process the results
                credits = []
                try:
                    for credit in json.loads(row["credits"]):
                        credits.append(Credit(**credit))
                except Exception:
                    logger.exception("credits failed")
                record = ComicIssue(
                    series=series,
                    credits=credits,
                    id=row["id"],
                    name=row["name"],
                    issue_number=row["issue_number"],
                    image_url=row["image_url"],
                    cover_date=row["cover_date"],
                    site_detail_url=row["site_detail_url"],
                    description=row["description"],
                    aliases=row["aliases"].strip().splitlines(),
                    alt_image_urls=row["alt_image_urls"].strip().splitlines(),
                    characters=row["characters"].strip().splitlines(),
                    locations=row["locations"].strip().splitlines(),
                    teams=row["teams"].strip().splitlines(),
                    story_arcs=row["story_arcs"].strip().splitlines(),
                    genres=row["genres"].strip().splitlines(),
                    tags=row["tags"].strip().splitlines(),
                    critical_rating=row["critical_rating"],
                    manga=row["manga"],
                    maturity_rating=row["maturity_rating"],
                    language=row["language"],
                    country=row["country"],
                    volume=row["volume"],
                    complete=bool(row["complete"]),
                )

            return record

    def upsert(self, cur: sqlite3.Cursor, tablename: str, data: dict[str, Any]) -> None:
        """This does an insert if the given PK doesn't exist, and an
        update it if does

        TODO: should the cursor be created here, and not up the stack?
        """

        keys = ""
        vals = []
        ins_slots = ""
        set_slots = ""

        for key in data:
            if data[key] is None:
                continue

            if keys != "":
                keys += ", "
            if ins_slots != "":
                ins_slots += ", "
            if set_slots != "":
                set_slots += ", "

            keys += key
            vals.append(data[key])
            ins_slots += "?"
            set_slots += key + " = ?"

        sql_ins = f"INSERT OR REPLACE INTO {tablename} ({keys}) VALUES ({ins_slots})"
        cur.execute(sql_ins, vals)
