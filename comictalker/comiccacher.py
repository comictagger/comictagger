"""A python class to manage caching of data from Comic Vine"""
#
# Copyright 2012-2014 ComicTagger Authors
#
# Licensed under the Apache License, Version 2.0 (the "License;
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
import sqlite3 as lite
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

        con = lite.connect(self.db_file)

        # create tables
        with con:
            cur = con.cursor()
            # source_name,name,id,start_year,publisher,image,description,count_of_issues
            cur.execute(
                "CREATE TABLE SeriesSearchCache("
                + "search_term TEXT,"
                + "id TEXT NOT NULL,"
                + "timestamp DATE DEFAULT (datetime('now','localtime')),"
                + "source_name TEXT NOT NULL)"
            )

            cur.execute(
                "CREATE TABLE Series("
                + "id TEXT NOT NULL,"
                + "name TEXT,"
                + "publisher TEXT,"
                + "count_of_issues INT,"
                + "start_year INT,"
                + "image_url TEXT,"
                + "aliases TEXT,"  # Newline separated
                + "description TEXT,"
                + "complete BOOL,"  # Is the series complete. No more data available from the source for series
                + "timestamp DATE DEFAULT (datetime('now','localtime')), "
                + "source_name TEXT NOT NULL,"
                + "PRIMARY KEY (id, source_name))"
            )

            cur.execute(
                "CREATE TABLE Issues("
                + "id TEXT NOT NULL,"
                + "series_id TEXT,"
                + "name TEXT,"
                + "issue_number TEXT,"
                + "image_url TEXT,"
                + "thumb_url TEXT,"
                + "cover_date TEXT,"
                + "site_detail_url TEXT,"
                + "description TEXT,"
                + "timestamp DATE DEFAULT (datetime('now','localtime')), "
                + "source_name TEXT NOT NULL,"
                + "aliases TEXT,"  # Newline separated
                + "alt_image_urls TEXT,"  # Newline separated URLs
                + "characters TEXT,"  # Newline separated
                + "locations TEXT,"  # Newline separated
                + "credits TEXT,"  # JSON: "{"name": "Bob Shakespeare", "role": "Writer"}"
                + "teams TEXT,"  # Newline separated
                + "story_arcs TEXT,"  # Newline separated
                + "complete BOOL,"  # Is the data complete? Includes characters, locations, credits.
                + "PRIMARY KEY (id, source_name))"
            )

    def add_search_results(self, source_name: str, search_term: str, ct_search_results: list[ComicSeries]) -> None:
        con = lite.connect(self.db_file)

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
                    "INSERT INTO SeriesSearchCache " + "(source_name, search_term, id) " + "VALUES(?, ?, ?)",
                    (source_name, search_term.casefold(), record.id),
                )

                data = {
                    "id": record.id,
                    "source_name": source_name,
                    "name": record.name,
                    "publisher": record.publisher,
                    "count_of_issues": record.count_of_issues,
                    "start_year": record.start_year,
                    "image_url": record.image_url,
                    "description": record.description,
                    "complete": record.complete,
                    "timestamp": datetime.datetime.now(),
                    "aliases": "\n".join(record.aliases),
                }
                self.upsert(cur, "series", data)

    def get_search_results(self, source_name: str, search_term: str) -> list[ComicSeries]:
        results = []
        con = lite.connect(self.db_file)
        with con:
            con.text_factory = str
            cur = con.cursor()

            cur.execute(
                "SELECT * FROM SeriesSearchCache INNER JOIN Series on"
                " SeriesSearchCache.id=Series.id AND SeriesSearchCache.source_name=Series.source_name"
                " WHERE search_term=? AND SeriesSearchCache.source_name=?",
                [search_term.casefold(), source_name],
            )

            rows = cur.fetchall()
            # now process the results
            for record in rows:
                result = ComicSeries(
                    id=record[4],
                    name=record[5],
                    publisher=record[6],
                    count_of_issues=record[7],
                    start_year=record[8],
                    image_url=record[9],
                    aliases=record[10].strip().splitlines(),
                    description=record[11],
                    complete=bool(record[12]),
                )

                results.append(result)

        return results

    def add_series_info(self, source_name: str, series_record: ComicSeries) -> None:
        con = lite.connect(self.db_file)

        with con:
            cur = con.cursor()

            timestamp = datetime.datetime.now()

            data = {
                "id": series_record.id,
                "source_name": source_name,
                "name": series_record.name,
                "publisher": series_record.publisher,
                "count_of_issues": series_record.count_of_issues,
                "start_year": series_record.start_year,
                "image_url": series_record.image_url,
                "description": series_record.description,
                "complete": series_record.complete,
                "timestamp": timestamp,
                "aliases": "\n".join(series_record.aliases),
            }
            self.upsert(cur, "series", data)

    def add_series_issues_info(self, source_name: str, series_issues: list[ComicIssue]) -> None:
        con = lite.connect(self.db_file)

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
                    "credits": json.dumps([dataclasses.asdict(x) for x in issue.credits]),
                    "complete": issue.complete,
                }
                self.upsert(cur, "issues", data)

    def get_series_info(self, series_id: str, source_name: str, purge: bool = True) -> ComicSeries | None:
        result: ComicSeries | None = None

        con = lite.connect(self.db_file)
        with con:
            cur = con.cursor()
            con.text_factory = str

            if purge:
                # purge stale series info
                a_week_ago = datetime.datetime.today() - datetime.timedelta(days=7)
                cur.execute("DELETE FROM Series WHERE timestamp  < ?", [str(a_week_ago)])

            # fetch
            cur.execute("SELECT * FROM Series" " WHERE id=? AND source_name=?", [series_id, source_name])

            row = cur.fetchone()

            if row is None:
                return result

            # since ID is primary key, there is only one row
            result = ComicSeries(
                id=row[0],
                name=row[1],
                publisher=row[2],
                count_of_issues=row[3],
                start_year=row[4],
                image_url=row[5],
                aliases=row[6].strip().splitlines(),
                description=row[7],
                complete=bool(row[8]),
            )

        return result

    def get_series_issues_info(self, series_id: str, source_name: str) -> list[ComicIssue]:
        # get_series_info should only fail if someone is doing something weird
        series = self.get_series_info(series_id, source_name, False) or ComicSeries(
            id=series_id,
            name="",
            description="",
            image_url="",
            publisher="",
            start_year=None,
            aliases=[],
            count_of_issues=None,
            complete=False,
        )
        con = lite.connect(self.db_file)
        with con:
            cur = con.cursor()
            con.text_factory = str

            # purge stale issue info - probably issue data won't change
            # much....
            a_week_ago = datetime.datetime.today() - datetime.timedelta(days=7)
            cur.execute("DELETE FROM Issues WHERE timestamp  < ?", [str(a_week_ago)])

            # fetch
            results: list[ComicIssue] = []

            cur.execute(
                (
                    "SELECT source_name,id,name,issue_number,site_detail_url,cover_date,image_url,thumb_url,description,aliases,alt_image_urls,characters,locations,credits,teams,story_arcs,complete"
                    " FROM Issues WHERE series_id=? AND source_name=?"
                ),
                [series_id, source_name],
            )
            rows = cur.fetchall()

            # now process the results
            for row in rows:
                credits = []
                try:
                    for credit in json.loads(row[13]):
                        credits.append(Credit(**credit))
                except Exception:
                    logger.exception("credits failed")
                record = ComicIssue(
                    id=row[1],
                    name=row[2],
                    issue_number=row[3],
                    site_detail_url=row[4],
                    cover_date=row[5],
                    image_url=row[6],
                    description=row[8],
                    series=series,
                    aliases=row[9].strip().splitlines(),
                    alt_image_urls=row[10].strip().splitlines(),
                    characters=row[11].strip().splitlines(),
                    locations=row[12].strip().splitlines(),
                    credits=credits,
                    teams=row[14].strip().splitlines(),
                    story_arcs=row[15].strip().splitlines(),
                    complete=bool(row[16]),
                )

                results.append(record)

        return results

    def get_issue_info(self, issue_id: int, source_name: str) -> ComicIssue | None:
        con = lite.connect(self.db_file)
        with con:
            cur = con.cursor()
            con.text_factory = str

            # purge stale issue info - probably issue data won't change
            # much....
            a_week_ago = datetime.datetime.today() - datetime.timedelta(days=7)
            cur.execute("DELETE FROM Issues WHERE timestamp  < ?", [str(a_week_ago)])

            cur.execute(
                (
                    "SELECT source_name,id,name,issue_number,site_detail_url,cover_date,image_url,description,aliases,series_id,alt_image_urls,characters,locations,credits,teams,story_arcs,complete"
                    " FROM Issues WHERE id=? AND source_name=?"
                ),
                [issue_id, source_name],
            )
            row = cur.fetchone()

            record = None

            if row:
                # get_series_info should only fail if someone is doing something weird
                series = self.get_series_info(row[10], source_name, False) or ComicSeries(
                    id=row[10],
                    name="",
                    description="",
                    image_url="",
                    publisher="",
                    start_year=None,
                    aliases=[],
                    count_of_issues=None,
                    complete=False,
                )

                # now process the results
                credits = []
                try:
                    for credit in json.loads(row[13]):
                        credits.append(Credit(**credit))
                except Exception:
                    logger.exception("credits failed")
                record = ComicIssue(
                    id=row[1],
                    name=row[2],
                    issue_number=row[3],
                    site_detail_url=row[4],
                    cover_date=row[5],
                    image_url=row[6],
                    description=row[7],
                    series=series,
                    aliases=row[8].strip().splitlines(),
                    alt_image_urls=row[10].strip().splitlines(),
                    characters=row[11].strip().splitlines(),
                    locations=row[12].strip().splitlines(),
                    credits=credits,
                    teams=row[14].strip().splitlines(),
                    story_arcs=row[15].strip().splitlines(),
                    complete=bool(row[16]),
                )

            return record

    def upsert(self, cur: lite.Cursor, tablename: str, data: dict[str, Any]) -> None:
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
