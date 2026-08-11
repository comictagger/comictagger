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

import contextlib
import datetime
import logging
import os
import pathlib
import sqlite3
import threading
from typing import Any, Generic, TypeVar

from typing_extensions import NamedTuple

logger = logging.getLogger(__name__)


class Series(NamedTuple):
    id: str
    data: bytes
    expiration: datetime.datetime


class Issue(NamedTuple):
    id: str
    series_id: str
    data: bytes
    expiration: datetime.datetime


T = TypeVar("T", Issue, Series)


class CacheResult(NamedTuple, Generic[T]):
    data: T
    complete: bool


class ComicCacher:
    def __init__(self, cache_folder: pathlib.Path, version: str) -> None:
        self.cache_folder = cache_folder
        self.db_file = cache_folder / "comic_cache.db"
        self.version_file = cache_folder / "cache_version.txt"
        self.version = version
        self.local: threading.Thread | None = None
        self.db: sqlite3.Connection | None = None

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

        self.create_cache_db()

    def a_week(self) -> datetime.datetime:
        return datetime.datetime.today() + datetime.timedelta(days=7)

    def a_year(self) -> datetime.datetime:
        return datetime.datetime.today() + datetime.timedelta(days=365)

    def clear_cache(self) -> None:
        try:
            self.close()
        except Exception:
            pass
        try:
            os.unlink(self.db_file)
        except Exception:
            pass
        try:
            os.unlink(self.version_file)
        except Exception:
            pass
        self.create_cache_db()

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
        # create the version file
        with open(self.version_file, "w", encoding="utf-8") as f:
            f.write(self.version)

        # create tables
        with self.connect() as con, contextlib.closing(con.cursor()) as cur:
            cur.execute("""CREATE TABLE IF NOT EXISTS SeriesSearchCache(
                expiration DATE DEFAULT (datetime('now', '+7 days','localtime')),
                id          TEXT NOT NULL,
                source      TEXT NOT NULL,
                search_term TEXT,
                PRIMARY KEY (id, source, search_term))""")
            cur.execute("CREATE TABLE IF NOT EXISTS Source(id TEXT NOT NULL, name TEXT NOT NULL, PRIMARY KEY (id))")

            cur.execute("""CREATE TABLE IF NOT EXISTS Series(
                expiration DATE DEFAULT (datetime('now', '+365 days', 'localtime')),
                id       TEXT NOT NULL,
                source   TEXT NOT NULL,
                data     BLOB,
                complete BOOL,
                PRIMARY KEY (id, source))""")

            cur.execute("""CREATE TABLE IF NOT EXISTS Issues(
                expiration DATE DEFAULT (datetime('now', '+365 days', 'localtime')),
                id        TEXT NOT NULL,
                source    TEXT NOT NULL,
                series_id TEXT,
                data      BLOB,
                complete  BOOL,
                PRIMARY KEY (id, source))""")

    def expire_stale_records(self, cur: sqlite3.Cursor, table: str) -> None:
        if "'" in table:
            raise ValueError("Single quotes not allowed in table names")
        cur.execute(f"DELETE FROM '{table}' WHERE expiration  < datetime('now')")

    def add_search_results(self, source: str, search_term: str, series_list: list[Series], complete: bool) -> None:
        with self.connect() as con, contextlib.closing(con.cursor()) as cur:

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
        with self.connect() as con, contextlib.closing(con.cursor()) as cur:

            data = {
                "id": series.id,
                "source": source,
                "data": series.data,
                "complete": complete,
                "expiration": series.expiration,
            }
            self.upsert(cur, "series", data)

    def add_all_series_info(self, source: str, series_list: list[Series], complete: bool) -> None:
        with self.connect() as con, contextlib.closing(con.cursor()) as cur:

            for series in series_list:
                data = {
                    "id": series.id,
                    "source": source,
                    "data": series.data,
                    "complete": complete,
                    "expiration": series.expiration,
                }
                self.upsert(cur, "series", data)

    def add_all_issues_info(self, source: str, issues: list[Issue], complete: bool) -> None:
        with self.connect() as con, contextlib.closing(con.cursor()) as cur:

            for issue in issues:
                data = {
                    "id": issue.id,
                    "series_id": issue.series_id,
                    "data": issue.data,
                    "source": source,
                    "complete": complete,
                    "expiration": issue.expiration,
                }
                self.upsert(cur, "issues", data)

    def get_search_results(self, source: str, search_term: str, expire_stale: bool = True) -> list[CacheResult[Series]]:
        results = []
        with self.connect() as con, contextlib.closing(con.cursor()) as cur:

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
                result = Series(id=record["id"], data=record["data"], expiration=record["expiration"])

                results.append(CacheResult(result, record["complete"]))

        return results

    def get_series_info(self, series_id: str, source: str, expire_stale: bool = True) -> CacheResult[Series] | None:
        with self.connect() as con, contextlib.closing(con.cursor()) as cur:

            if expire_stale:
                self.expire_stale_records(cur, "Series")

            # fetch
            cur.execute("SELECT * FROM Series WHERE id=? AND source=?", [series_id, source])

            row = cur.fetchone()

            if row is None:
                return None

            result = Series(id=row["id"], data=row["data"], expiration=row["expiration"])

            return CacheResult(result, row["complete"])

    def get_series_issues_info(
        self, series_id: str, source: str, expire_stale: bool = True
    ) -> list[CacheResult[Issue]]:
        with self.connect() as con, contextlib.closing(con.cursor()) as cur:

            if expire_stale:
                self.expire_stale_records(cur, "Issues")

            # fetch
            results: list[CacheResult[Issue]] = []

            cur.execute("SELECT * FROM Issues WHERE series_id=? AND source=?", [series_id, source])
            rows = cur.fetchall()

            # now process the results
            for row in rows:
                record = CacheResult(
                    Issue(id=row["id"], series_id=row["series_id"], data=row["data"], expiration=row["expiration"]),
                    row["complete"],
                )

                results.append(record)

        return results

    def get_issue_info(self, issue_id: str, source: str, expire_stale: bool = True) -> CacheResult[Issue] | None:
        with self.connect() as con, contextlib.closing(con.cursor()) as cur:

            if expire_stale:
                self.expire_stale_records(cur, "Issues")

            cur.execute("SELECT * FROM Issues WHERE id=? AND source=?", [issue_id, source])
            row = cur.fetchone()

            record = None

            if row:
                record = CacheResult(
                    Issue(id=row["id"], series_id=row["series_id"], data=row["data"], expiration=row["expiration"]),
                    row["complete"],
                )

            return record

    def upsert(self, cur: sqlite3.Cursor, tablename: str, data: dict[str, Any]) -> None:
        """This does an insert if the given PK doesn't exist, and an
        update it if does
        """

        keys = ""
        vals = []
        ins_slots = ""
        set_slots = ""

        for key in data:
            if data[key] is None:
                continue

            if keys:
                keys += ", "
            if ins_slots:
                ins_slots += ", "
            if set_slots:
                set_slots += ", "

            keys += key
            vals.append(data[key])
            ins_slots += "?"
            set_slots += key + " = ?"

        sql_ins = f"INSERT OR REPLACE INTO {tablename} ({keys}) VALUES ({ins_slots})"
        if not data.get("complete", True):
            # If the data to upsert is not complete only overwrite cached data that is also not complete
            sql_ins += f" ON CONFLICT DO UPDATE SET {set_slots} WHERE complete != TRUE"
            vals.extend(vals.copy())

        cur.execute(sql_ins, vals)


def adapt_datetime_iso(val: datetime.datetime) -> str:
    """Adapt datetime.datetime to timezone-naive ISO 8601 date."""
    return val.isoformat()


def convert_datetime(val: bytes) -> datetime.datetime:
    """Convert ISO 8601 datetime to datetime.datetime object."""
    return datetime.datetime.fromisoformat(val.decode())


sqlite3.register_adapter(datetime.datetime, adapt_datetime_iso)
sqlite3.register_converter("datetime", convert_datetime)
