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

import datetime
import logging
import os
import pathlib
import sqlite3
from typing import Any

from typing_extensions import NamedTuple

logger = logging.getLogger(__name__)


class Series(NamedTuple):
    id: str
    data: bytes


class Issue(NamedTuple):
    id: str
    series_id: str
    data: bytes


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
            cur.execute(
                """CREATE TABLE SeriesSearchCache(
                timestamp DATE DEFAULT (datetime('now','localtime')),
                id          TEXT NOT NULL,
                source      TEXT NOT NULL,
                search_term TEXT,
                PRIMARY KEY (id, source, search_term))"""
            )
            cur.execute("CREATE TABLE Source(id TEXT NOT NULL, name TEXT NOT NULL, PRIMARY KEY (id))")

            cur.execute(
                """CREATE TABLE Series(
                timestamp DATE DEFAULT (datetime('now','localtime')),
                id       TEXT NOT NULL,
                source   TEXT NOT NULL,
                data     BLOB,
                complete BOOL,
                PRIMARY KEY (id, source))"""
            )

            cur.execute(
                """CREATE TABLE Issues(
                timestamp DATE DEFAULT (datetime('now','localtime')),
                id        TEXT NOT NULL,
                source    TEXT NOT NULL,
                series_id TEXT,
                data      BLOB,
                complete  BOOL,
                PRIMARY KEY (id, source))"""
            )

    def expire_stale_records(self, cur: sqlite3.Cursor, table: str) -> None:
        # purge stale series info
        a_week_ago = datetime.datetime.today() - datetime.timedelta(days=7)
        cur.execute("DELETE FROM Series WHERE timestamp  < ?", [str(a_week_ago)])

    def add_search_results(self, source: str, search_term: str, series_list: list[Series], complete: bool) -> None:
        with sqlite3.connect(self.db_file) as con:
            con.row_factory = sqlite3.Row
            con.text_factory = str
            cur = con.cursor()

            # remove all previous entries with this search term
            cur.execute(
                "DELETE FROM SeriesSearchCache WHERE search_term = ? AND source = ?",
                [search_term.casefold(), source],
            )

            # now add in new results
            for series in series_list:
                cur.execute(
                    "INSERT INTO SeriesSearchCache (source, search_term, id) VALUES(?, ?, ?)",
                    (source, search_term.casefold(), series.id),
                )
                data = {
                    "id": series.id,
                    "source": source,
                    "data": series.data,
                    "complete": complete,
                }
                self.upsert(cur, "series", data)

    def add_series_info(self, source: str, series: Series, complete: bool) -> None:
        with sqlite3.connect(self.db_file) as con:
            con.row_factory = sqlite3.Row
            cur = con.cursor()

            data = {
                "id": series.id,
                "source": source,
                "data": series.data,
                "complete": complete,
            }
            self.upsert(cur, "series", data)

    def add_issues_info(self, source: str, issues: list[Issue], complete: bool) -> None:
        with sqlite3.connect(self.db_file) as con:
            con.row_factory = sqlite3.Row
            cur = con.cursor()

            for issue in issues:
                data = {
                    "id": issue.id,
                    "series_id": issue.series_id,
                    "data": issue.data,
                    "source": source,
                    "complete": complete,
                }
                self.upsert(cur, "issues", data)

    def get_search_results(self, source: str, search_term: str, expire_stale: bool = True) -> list[tuple[Series, bool]]:
        results = []
        with sqlite3.connect(self.db_file) as con:
            con.row_factory = sqlite3.Row
            con.text_factory = str
            cur = con.cursor()

            if expire_stale:
                self.expire_stale_records(cur, "SeriesSearchCache")
                self.expire_stale_records(cur, "Series")

            cur.execute(
                """SELECT * FROM SeriesSearchCache INNER JOIN Series on
                 SeriesSearchCache.id=Series.id AND SeriesSearchCache.source=Series.source
                 WHERE search_term=? AND SeriesSearchCache.source=?""",
                [search_term.casefold(), source],
            )

            rows = cur.fetchall()

            for record in rows:
                result = Series(id=record["id"], data=record["data"])

                results.append((result, record["complete"]))

        return results

    def get_series_info(self, series_id: str, source: str, expire_stale: bool = True) -> tuple[Series, bool] | None:
        result: Series | None = None

        with sqlite3.connect(self.db_file) as con:
            con.row_factory = sqlite3.Row
            cur = con.cursor()
            con.text_factory = str

            if expire_stale:
                self.expire_stale_records(cur, "Series")

            # fetch
            cur.execute("SELECT * FROM Series WHERE id=? AND source=?", [series_id, source])

            row = cur.fetchone()

            if row is None:
                return None

            result = Series(id=row["id"], data=row["data"])

            return (result, row["complete"])

    def get_series_issues_info(
        self, series_id: str, source: str, expire_stale: bool = True
    ) -> list[tuple[Issue, bool]]:
        with sqlite3.connect(self.db_file) as con:
            con.row_factory = sqlite3.Row
            cur = con.cursor()
            con.text_factory = str

            if expire_stale:
                self.expire_stale_records(cur, "Issues")

            # fetch
            results: list[tuple[Issue, bool]] = []

            cur.execute("SELECT * FROM Issues WHERE series_id=? AND source=?", [series_id, source])
            rows = cur.fetchall()

            # now process the results
            for row in rows:
                record = (Issue(id=row["id"], series_id=row["series_id"], data=row["data"]), row["complete"])

                results.append(record)

        return results

    def get_issue_info(self, issue_id: int, source: str, expire_stale: bool = True) -> tuple[Issue, bool] | None:
        with sqlite3.connect(self.db_file) as con:
            con.row_factory = sqlite3.Row
            cur = con.cursor()
            con.text_factory = str

            if expire_stale:
                self.expire_stale_records(cur, "Issues")

            cur.execute("SELECT * FROM Issues WHERE id=? AND source=?", [issue_id, source])
            row = cur.fetchone()

            record = None

            if row:
                record = (Issue(id=row["id"], series_id=row["series_id"], data=row["data"]), row["complete"])

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
