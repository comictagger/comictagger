"""A python class to manage caching of data from Comic Vine"""
#
# Copyright 2012-2014 Anthony Beville
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
import sqlite3 as lite
from typing import Any

from comictaggerlib import ctversion
from comictaggerlib.settings import ComicTaggerSettings
from comictalker.resulttypes import ComicIssue, ComicVolume

logger = logging.getLogger(__name__)


class ComicCacher:
    def __init__(self) -> None:
        self.settings_folder = ComicTaggerSettings.get_settings_folder()
        self.db_file = os.path.join(self.settings_folder, "comic_cache.db")
        self.version_file = os.path.join(self.settings_folder, "cache_version.txt")

        # verify that cache is from same version as this one
        data = ""
        try:
            with open(self.version_file, "rb") as f:
                data = f.read().decode("utf-8")
                f.close()
        except Exception:
            pass
        if data != ctversion.version:
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
            f.write(ctversion.version)

        # this will wipe out any existing version
        open(self.db_file, "wb").close()

        con = lite.connect(self.db_file)

        # create tables
        with con:
            cur = con.cursor()
            # source_name,name,id,start_year,publisher,image,description,count_of_issues
            cur.execute(
                "CREATE TABLE VolumeSearchCache("
                + "search_term TEXT,"
                + "id INT NOT NULL,"
                + "timestamp DATE DEFAULT (datetime('now','localtime')),"
                + "source_name TEXT NOT NULL)"
            )

            cur.execute(
                "CREATE TABLE Volumes("
                + "id INT NOT NULL,"
                + "name TEXT,"
                + "publisher TEXT,"
                + "count_of_issues INT,"
                + "start_year INT,"
                + "image_url TEXT,"
                + "aliases TEXT,"  # Newline separated
                + "description TEXT,"
                + "timestamp DATE DEFAULT (datetime('now','localtime')), "
                + "source_name TEXT NOT NULL,"
                + "PRIMARY KEY (id, source_name))"
            )

            cur.execute(
                "CREATE TABLE Issues("
                + "id INT NOT NULL,"
                + "volume_id INT,"
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
                + "alt_images_url TEXT,"  # Comma separated URLs
                + "characters TEXT,"  # Newline separated
                + "locations TEXT,"  # Newline separated
                + "credits TEXT,"  # JSON: "{"name": "Bob Shakespeare", "role": "Writer"}"
                + "teams TEXT,"  # Newline separated
                + "story_arcs TEXT,"  # Newline separated
                + "complete BOOL,"  # Is the data complete? Includes characters, locations, credits.
                + "PRIMARY KEY (id, source_name))"
            )

    def add_search_results(self, source_name: str, search_term: str, ct_search_results: list[ComicVolume]) -> None:
        con = lite.connect(self.db_file)

        with con:
            con.text_factory = str
            cur = con.cursor()

            # remove all previous entries with this search term
            cur.execute(
                "DELETE FROM VolumeSearchCache WHERE search_term = ? AND source_name = ?",
                [search_term.casefold(), source_name],
            )

            # now add in new results
            for record in ct_search_results:
                cur.execute(
                    "INSERT INTO VolumeSearchCache " + "(source_name, search_term, id) " + "VALUES(?, ?, ?)",
                    (
                        source_name,
                        search_term.casefold(),
                        record["id"],
                    ),
                )

                data = {
                    "source_name": source_name,
                    "timestamp": datetime.datetime.now(),
                }
                data.update(record)
                self.upsert(cur, "volumes", data)

    def get_search_results(self, source_name: str, search_term: str) -> list[ComicVolume]:
        results = []
        con = lite.connect(self.db_file)
        with con:
            con.text_factory = str
            cur = con.cursor()

            cur.execute(
                "SELECT * FROM VolumeSearchCache INNER JOIN Volumes on"
                " VolumeSearchCache.id=Volumes.id AND VolumeSearchCache.source_name=Volumes.source_name"
                " WHERE search_term=? AND VolumeSearchCache.source_name=?",
                [search_term.casefold(), source_name],
            )

            rows = cur.fetchall()
            # now process the results
            for record in rows:
                result = ComicVolume(
                    id=record[4],
                    name=record[5],
                    publisher=record[6],
                    count_of_issues=record[7],
                    start_year=record[8],
                    image_url=record[9],
                    aliases=record[10],
                    description=record[11],
                )

                results.append(result)

        return results

    def add_volume_info(self, source_name: str, volume_record: ComicVolume) -> None:
        con = lite.connect(self.db_file)

        with con:

            cur = con.cursor()

            timestamp = datetime.datetime.now()

            data = {
                "id": volume_record["id"],
                "source_name": source_name,
                "name": volume_record["name"],
                "publisher": volume_record["publisher"],
                "count_of_issues": volume_record["count_of_issues"],
                "start_year": volume_record["start_year"],
                "timestamp": timestamp,
                "aliases": volume_record["aliases"],
            }
            self.upsert(cur, "volumes", data)

    def add_volume_issues_info(self, source_name: str, volume_issues: list[ComicIssue]) -> None:
        con = lite.connect(self.db_file)

        with con:
            cur = con.cursor()

            timestamp = datetime.datetime.now()

            # add in issues

            for issue in volume_issues:
                data = {
                    "id": issue["id"],
                    "volume_id": issue["volume"]["id"],
                    "source_name": source_name,
                    "name": issue["name"],
                    "issue_number": issue["issue_number"],
                    "site_detail_url": issue["site_detail_url"],
                    "cover_date": issue["cover_date"],
                    "image_url": issue["image_url"],
                    "thumb_url": issue["image_thumb_url"],
                    "description": issue["description"],
                    "timestamp": timestamp,
                    "aliases": issue["aliases"],
                    "alt_images_url": issue["alt_images_url"],
                    "characters": "\n".join(issue["characters"]),
                    "locations": "\n".join(issue["locations"]),
                    "teams": "\n".join(issue["teams"]),
                    "story_arcs": "\n".join(issue["story_arcs"]),
                    "credits": json.dumps(issue["credits"]),
                    "complete": issue["complete"],
                }
                self.upsert(cur, "issues", data)

    def get_volume_info(self, volume_id: int, source_name: str, purge: bool = True) -> ComicVolume | None:
        result: ComicVolume | None = None

        con = lite.connect(self.db_file)
        with con:
            cur = con.cursor()
            con.text_factory = str

            if purge:
                # purge stale volume info
                a_week_ago = datetime.datetime.today() - datetime.timedelta(days=7)
                cur.execute("DELETE FROM Volumes WHERE timestamp  < ?", [str(a_week_ago)])

            # fetch
            cur.execute(
                "SELECT * FROM Volumes" " WHERE id=? AND source_name=?",
                [volume_id, source_name],
            )

            row = cur.fetchone()

            if row is None:
                return result

            # since ID is primary key, there is only one row
            result = ComicVolume(
                id=row[0],
                name=row[1],
                publisher=row[2],
                count_of_issues=row[3],
                start_year=row[4],
                image_url=row[5],
                aliases=row[6],
                description=row[7],
            )

        return result

    def get_volume_issues_info(self, volume_id: int, source_name: str) -> list[ComicIssue]:
        # get_volume_info should only fail if someone is doing something weird
        volume = self.get_volume_info(volume_id, source_name, False) or ComicVolume(id=volume_id, name="")
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
                    "SELECT source_name,id,name,issue_number,site_detail_url,cover_date,image_url,thumb_url,description,aliases,alt_images_url,characters,locations,credits,teams,story_arcs,complete"
                    " FROM Issues WHERE volume_id=? AND source_name=?"
                ),
                [volume_id, source_name],
            )
            rows = cur.fetchall()

            # now process the results
            for row in rows:
                record = ComicIssue(
                    id=row[1],
                    name=row[2],
                    issue_number=row[3],
                    site_detail_url=row[4],
                    cover_date=row[5],
                    image_url=row[6],
                    description=row[8],
                    volume=volume,
                    aliases=row[9],
                    alt_images_url=row[10],
                    characters=row[11].split("\n"),
                    locations=row[12].split("\n"),
                    credits=json.loads(row[13]),
                    teams=row[14].split("\n"),
                    story_arcs=row[15].split("\n"),
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
                    "SELECT source_name,id,name,issue_number,site_detail_url,cover_date,image_url,thumb_url,description,aliases,volume_id,alt_images_url,characters,locations,credits,teams,story_arcs,complete"
                    " FROM Issues WHERE id=? AND source_name=?"
                ),
                [issue_id, source_name],
            )
            row = cur.fetchone()

            record = None

            if row:
                # get_volume_info should only fail if someone is doing something weird
                volume = self.get_volume_info(row[10], source_name, False) or ComicVolume(id=row[10], name="")

                # now process the results

                record = ComicIssue(
                    id=row[1],
                    name=row[2],
                    issue_number=row[3],
                    site_detail_url=row[4],
                    cover_date=row[5],
                    image_url=row[6],
                    image_thumb_url=row[7],
                    description=row[8],
                    volume=volume,
                    aliases=row[9],
                    alt_images_url=row[11],
                    characters=row[12].split("\n"),
                    locations=row[13].split("\n"),
                    credits=json.loads(row[14]),
                    teams=row[15].split("\n"),
                    story_arcs=row[16].split("\n"),
                    complete=bool(row[17]),
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
