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
import json
import logging
import os
import pathlib
import sqlite3
from typing import Any, cast

from comicapi import utils
from comicapi.genericmetadata import ComicSeries, Credit, Date, GenericMetadata, TagOrigin

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
            # source,name,id,start_year,publisher,image,description,count_of_issues
            cur.execute(
                "CREATE TABLE SeriesSearchCache("
                + "timestamp DATE DEFAULT (datetime('now','localtime')),"
                + "id TEXT NOT NULL,"
                + "source TEXT NOT NULL,"
                + "search_term TEXT,"
                + "PRIMARY KEY (id, source, search_term))"
            )
            cur.execute("CREATE TABLE Source(" + "id TEXT NOT NULL," + "name TEXT NOT NULL," + "PRIMARY KEY (id))")

            cur.execute(
                "CREATE TABLE Series("
                + "timestamp DATE DEFAULT (datetime('now','localtime')), "
                + "id TEXT NOT NULL,"
                + "source TEXT NOT NULL,"
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
                + "PRIMARY KEY (id, source))"
            )

            cur.execute(
                "CREATE TABLE Issues("
                + "timestamp DATE DEFAULT (datetime('now','localtime')), "
                + "id TEXT NOT NULL,"
                + "source TEXT NOT NULL,"
                + "series_id TEXT,"
                + "name TEXT,"
                + "issue_number TEXT,"
                + "image_url TEXT,"
                + "thumb_url TEXT,"
                + "cover_date TEXT,"
                + "store_date TEXT,"
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
                + "PRIMARY KEY (id, source))"
            )

    def add_search_results(self, source: TagOrigin, search_term: str, series_list: list[ComicSeries]) -> None:
        self.add_source(source)

        with sqlite3.connect(self.db_file) as con:
            con.row_factory = sqlite3.Row
            con.text_factory = str
            cur = con.cursor()

            # remove all previous entries with this search term
            cur.execute(
                "DELETE FROM SeriesSearchCache WHERE search_term = ? AND source = ?",
                [search_term.casefold(), source.id],
            )

            # now add in new results
            for record in series_list:
                cur.execute(
                    "INSERT INTO SeriesSearchCache (source, search_term, id) VALUES(?, ?, ?)",
                    (source.id, search_term.casefold(), record.id),
                )

                data = {
                    "id": record.id,
                    "source": source.id,
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

    def add_series_info(self, source: TagOrigin, series: ComicSeries) -> None:
        self.add_source(source)

        with sqlite3.connect(self.db_file) as con:
            con.row_factory = sqlite3.Row
            cur = con.cursor()

            timestamp = datetime.datetime.now()

            data = {
                "id": series.id,
                "source": source.id,
                "name": series.name,
                "publisher": series.publisher,
                "count_of_issues": series.count_of_issues,
                "count_of_volumes": series.count_of_volumes,
                "start_year": series.start_year,
                "image_url": series.image_url,
                "description": series.description,
                "genres": "\n".join(series.genres),
                "format": series.format,
                "timestamp": timestamp,
                "aliases": "\n".join(series.aliases),
            }
            self.upsert(cur, "series", data)

    def add_series_issues_info(self, source: TagOrigin, issues: list[GenericMetadata], complete: bool) -> None:
        self.add_source(source)

        with sqlite3.connect(self.db_file) as con:
            con.row_factory = sqlite3.Row
            cur = con.cursor()

            timestamp = datetime.datetime.now()

            # add in issues

            for issue in issues:
                data = {
                    "id": issue.issue_id,
                    "series_id": issue.series_id,
                    "source": source.id,
                    "name": issue.title,
                    "issue_number": issue.issue,
                    "volume": issue.volume,
                    "site_detail_url": issue.web_link,
                    "cover_date": str(issue.cover_date),
                    "store_date": str(issue.store_date),
                    "image_url": issue.cover_image,
                    "description": issue.description,
                    "timestamp": timestamp,
                    "aliases": "\n".join(issue.title_aliases),
                    "alt_image_urls": "\n".join(issue.alternate_images),
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
                    "credits": json.dumps(issue.credits),
                    "complete": complete,
                }
                self.upsert(cur, "issues", data)

    def add_source(self, source: TagOrigin) -> None:
        with sqlite3.connect(self.db_file) as con:
            con.row_factory = sqlite3.Row
            cur = con.cursor()
            con.text_factory = str

            self.upsert(
                cur,
                "source",
                {
                    "id": source.id,
                    "name": source.name,
                },
            )

    def get_search_results(self, source: TagOrigin, search_term: str) -> list[ComicSeries]:
        results = []
        with sqlite3.connect(self.db_file) as con:
            con.row_factory = sqlite3.Row
            con.text_factory = str
            cur = con.cursor()

            cur.execute(
                "SELECT * FROM SeriesSearchCache INNER JOIN Series on"
                + " SeriesSearchCache.id=Series.id AND SeriesSearchCache.source=Series.source"
                + " WHERE search_term=? AND SeriesSearchCache.source=?",
                [search_term.casefold(), source.id],
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
                    aliases=utils.split(record["aliases"], "\n"),
                    description=record["description"],
                    genres=utils.split(record["genres"], "\n"),
                    format=record["format"],
                )

                results.append(result)

        return results

    def get_series_info(self, series_id: str, source: TagOrigin, expire_stale: bool = True) -> ComicSeries | None:
        result: ComicSeries | None = None

        with sqlite3.connect(self.db_file) as con:
            con.row_factory = sqlite3.Row
            cur = con.cursor()
            con.text_factory = str

            if expire_stale:
                # purge stale series info
                a_week_ago = datetime.datetime.today() - datetime.timedelta(days=7)
                cur.execute("DELETE FROM Series WHERE timestamp  < ?", [str(a_week_ago)])

            # fetch
            cur.execute("SELECT * FROM Series WHERE id=? AND source=?", [series_id, source.id])

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
                aliases=utils.split(row["aliases"], "\n"),
                description=row["description"],
                genres=utils.split(row["genres"], "\n"),
                format=row["format"],
            )

        return result

    def get_series_issues_info(self, series_id: str, source: TagOrigin) -> list[tuple[GenericMetadata, bool]]:
        # get_series_info should only fail if someone is doing something weird
        series = self.get_series_info(series_id, source, False) or ComicSeries(
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

        with sqlite3.connect(self.db_file) as con:
            con.row_factory = sqlite3.Row
            cur = con.cursor()
            con.text_factory = str

            # purge stale issue info - probably issue data won't change
            # much....
            a_week_ago = datetime.datetime.today() - datetime.timedelta(days=7)
            cur.execute("DELETE FROM Issues WHERE timestamp  < ?", [str(a_week_ago)])

            # fetch
            results: list[tuple[GenericMetadata, bool]] = []

            cur.execute("SELECT * FROM Issues WHERE series_id=? AND source=?", [series_id, source.id])
            rows = cur.fetchall()

            # now process the results
            for row in rows:
                record = self.map_row_metadata(row, series, source)

                results.append(record)

        return results

    def get_issue_info(self, issue_id: int, source: TagOrigin) -> tuple[GenericMetadata, bool] | None:
        with sqlite3.connect(self.db_file) as con:
            con.row_factory = sqlite3.Row
            cur = con.cursor()
            con.text_factory = str

            # purge stale issue info - probably issue data won't change
            # much....
            a_week_ago = datetime.datetime.today() - datetime.timedelta(days=7)
            cur.execute("DELETE FROM Issues WHERE timestamp  < ?", [str(a_week_ago)])

            cur.execute("SELECT * FROM Issues WHERE id=? AND source=?", [issue_id, source.id])
            row = cur.fetchone()

            record = None

            if row:
                # get_series_info should only fail if someone is doing something weird
                series = self.get_series_info(row["id"], source, False) or ComicSeries(
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

                record = self.map_row_metadata(row, series, source)

            return record

    def get_source(self, source_id: str) -> TagOrigin:
        con = sqlite3.connect(self.db_file)
        with sqlite3.connect(self.db_file) as con:
            con.row_factory = sqlite3.Row
            cur = con.cursor()
            con.text_factory = str

            cur.execute("SELECT * FROM Source WHERE id=?", [source_id])
            row = cur.fetchone()

        return TagOrigin(row["id"], row["name"])

    def map_row_metadata(
        self, row: sqlite3.Row, series: ComicSeries, source: TagOrigin
    ) -> tuple[GenericMetadata, bool]:
        day, month, year = utils.parse_date_str(row["cover_date"])
        credits = []
        try:
            for credit in json.loads(row["credits"]):
                credits.append(cast(Credit, credit))
        except Exception:
            logger.exception("credits failed")
        return (
            GenericMetadata(
                tag_origin=source,
                alternate_images=utils.split(row["alt_image_urls"], "\n"),
                characters=utils.split(row["characters"], "\n"),
                country=row["country"],
                cover_image=row["image_url"],
                credits=credits,
                critical_rating=row["critical_rating"],
                cover_date=Date.parse_date(row["cover_date"]),
                store_date=Date.parse_date(row["store_date"]),
                description=row["description"],
                genres=utils.split(row["genres"], "\n"),
                issue=row["issue_number"],
                issue_count=series.count_of_issues,
                issue_id=row["id"],
                language=row["language"],
                locations=utils.split(row["locations"], "\n"),
                manga=row["manga"],
                maturity_rating=row["maturity_rating"],
                publisher=series.publisher,
                series=series.name,
                series_aliases=series.aliases,
                series_id=series.id,
                story_arcs=utils.split(row["story_arcs"], "\n"),
                tags=set(utils.split(row["tags"], "\n")),
                teams=utils.split(row["teams"], "\n"),
                title=row["name"],
                title_aliases=utils.split(row["aliases"], "\n"),
                volume=row["volume"],
                volume_count=series.count_of_volumes,
                web_link=row["site_detail_url"],
            ),
            row["complete"],
        )

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
