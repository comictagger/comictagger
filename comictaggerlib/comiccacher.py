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
import logging
import os
import sqlite3 as lite
from typing import Any

from comictaggerlib import ctversion
from comictaggerlib.resulttypes import CVIssuesResults, CVVolumeResults, SelectDetails
from comictaggerlib.settings import ComicTaggerSettings

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
                + "name TEXT,"
                + "start_year INT,"
                + "publisher TEXT,"
                + "count_of_issues INT,"
                + "image_url TEXT,"
                + "description TEXT,"
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
                + "timestamp DATE DEFAULT (datetime('now','localtime')), "
                + "source_name TEXT NOT NULL,"
                + "PRIMARY KEY (id, source_name))"
            )

            cur.execute(
                "CREATE TABLE AltCovers("
                + "issue_id INT NOT NULL,"
                + "url_list TEXT,"
                + "timestamp DATE DEFAULT (datetime('now','localtime')), "
                + "source_name TEXT NOT NULL,"
                + "PRIMARY KEY (issue_id, source_name))"
            )

            cur.execute(
                "CREATE TABLE Issues("
                + "id INT NOT NULL,"
                + "volume_id INT,"
                + "name TEXT,"
                + "issue_number TEXT,"
                + "super_url TEXT,"
                + "thumb_url TEXT,"
                + "cover_date TEXT,"
                + "site_detail_url TEXT,"
                + "description TEXT,"
                + "timestamp DATE DEFAULT (datetime('now','localtime')), "
                + "source_name TEXT NOT NULL,"
                + "PRIMARY KEY (id, source_name))"
            )

    def add_search_results(self, source_name: str, search_term: str, cv_search_results: list[CVVolumeResults]) -> None:

        con = lite.connect(self.db_file)

        with con:
            con.text_factory = str
            cur = con.cursor()

            # remove all previous entries with this search term
            cur.execute("DELETE FROM VolumeSearchCache WHERE search_term = ?", [search_term.casefold()])

            # now add in new results
            for record in cv_search_results:

                if record["publisher"] is None:
                    pub_name = ""
                else:
                    pub_name = record["publisher"]["name"]

                if record["image"] is None:
                    url = ""
                else:
                    url = record["image"]["super_url"]

                cur.execute(
                    "INSERT INTO VolumeSearchCache "
                    + "(source_name, search_term, id, name, start_year, publisher, count_of_issues, image_url, description) "
                    + "VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        source_name,
                        search_term.casefold(),
                        record["id"],
                        record["name"],
                        record["start_year"],
                        pub_name,
                        record["count_of_issues"],
                        url,
                        record["description"],
                    ),
                )

    def get_search_results(self, source_name: str, search_term: str) -> list[CVVolumeResults]:

        results = []
        con = lite.connect(self.db_file)
        with con:
            con.text_factory = str
            cur = con.cursor()

            # purge stale search results
            a_day_ago = datetime.datetime.today() - datetime.timedelta(days=1)
            cur.execute("DELETE FROM VolumeSearchCache WHERE timestamp  < ?", [str(a_day_ago)])

            # fetch
            cur.execute(
                "SELECT * FROM VolumeSearchCache WHERE search_term=? AND source_name=?",
                [search_term.casefold(), source_name],
            )
            rows = cur.fetchall()
            # now process the results
            for record in rows:
                result = CVVolumeResults(
                    {
                        "id": record[1],
                        "name": record[2],
                        "start_year": record[3],
                        "count_of_issues": record[5],
                        "description": record[7],
                        "publisher": {"name": record[4]},
                        "image": {"super_url": record[6]},
                    }
                )

                results.append(result)

        return results

    def add_alt_covers(self, source_name: str, issue_id: int, url_list: list[str]) -> None:

        con = lite.connect(self.db_file)

        with con:
            con.text_factory = str
            cur = con.cursor()

            # remove all previous entries with this search term
            cur.execute("DELETE FROM AltCovers WHERE issue_id=? AND source_name=?", [issue_id, source_name])

            url_list_str = ", ".join(url_list)
            # now add in new record
            cur.execute(
                "INSERT INTO AltCovers (source_name, issue_id, url_list) VALUES(?, ?, ?)",
                (source_name, issue_id, url_list_str),
            )

    def get_alt_covers(self, source_name: str, issue_id: int) -> list[str]:

        con = lite.connect(self.db_file)
        with con:
            cur = con.cursor()
            con.text_factory = str

            # purge stale issue info - probably issue data won't change
            # much....
            a_month_ago = datetime.datetime.today() - datetime.timedelta(days=30)
            cur.execute("DELETE FROM AltCovers WHERE timestamp  < ?", [str(a_month_ago)])

            cur.execute("SELECT url_list FROM AltCovers WHERE issue_id=? AND source_name=?", [issue_id, source_name])
            row = cur.fetchone()
            if row is None:
                return []

            url_list_str = row[0]
            if len(url_list_str) == 0:
                return []
            raw_list = url_list_str.split(",")
            url_list = []
            for item in raw_list:
                url_list.append(str(item).strip())
            return url_list

    def add_volume_info(self, source_name: str, cv_volume_record: CVVolumeResults) -> None:

        con = lite.connect(self.db_file)

        with con:

            cur = con.cursor()

            timestamp = datetime.datetime.now()

            if cv_volume_record["publisher"] is None:
                pub_name = ""
            else:
                pub_name = cv_volume_record["publisher"]["name"]

            data = {
                "id": cv_volume_record["id"],
                "source_name": source_name,
                "name": cv_volume_record["name"],
                "publisher": pub_name,
                "count_of_issues": cv_volume_record["count_of_issues"],
                "start_year": cv_volume_record["start_year"],
                "timestamp": timestamp,
            }
            self.upsert(cur, "volumes", data)

    def add_volume_issues_info(self, source_name: str, volume_id: int, cv_volume_issues: list[CVIssuesResults]) -> None:

        con = lite.connect(self.db_file)

        with con:
            cur = con.cursor()

            timestamp = datetime.datetime.now()

            # add in issues

            for issue in cv_volume_issues:
                data = {
                    "id": issue["id"],
                    "volume_id": volume_id,
                    "source_name": source_name,
                    "name": issue["name"],
                    "issue_number": issue["issue_number"],
                    "site_detail_url": issue["site_detail_url"],
                    "cover_date": issue["cover_date"],
                    "super_url": issue["image"]["super_url"],
                    "thumb_url": issue["image"]["thumb_url"],
                    "description": issue["description"],
                    "timestamp": timestamp,
                }
                self.upsert(cur, "issues", data)

    def get_volume_info(self, volume_id: int, source_name: str) -> CVVolumeResults | None:

        result: CVVolumeResults | None = None

        con = lite.connect(self.db_file)
        with con:
            cur = con.cursor()
            con.text_factory = str

            # purge stale volume info
            a_week_ago = datetime.datetime.today() - datetime.timedelta(days=7)
            cur.execute("DELETE FROM Volumes WHERE timestamp  < ?", [str(a_week_ago)])

            # fetch
            cur.execute(
                "SELECT source_name,id,name,publisher,count_of_issues,start_year FROM Volumes WHERE id=? AND source_name=?",
                [volume_id, source_name],
            )

            row = cur.fetchone()

            if row is None:
                return result

            # since ID is primary key, there is only one row
            result = CVVolumeResults(
                {
                    "id": row[1],
                    "name": row[2],
                    "count_of_issues": row[4],
                    "start_year": row[5],
                    "publisher": {"name": row[3]},
                }
            )

        return result

    def get_volume_issues_info(self, volume_id: int, source_name: str) -> list[CVIssuesResults]:

        con = lite.connect(self.db_file)
        with con:
            cur = con.cursor()
            con.text_factory = str

            # purge stale issue info - probably issue data won't change
            # much....
            a_week_ago = datetime.datetime.today() - datetime.timedelta(days=7)
            cur.execute("DELETE FROM Issues WHERE timestamp  < ?", [str(a_week_ago)])

            # fetch
            results: list[CVIssuesResults] = []

            cur.execute(
                (
                    "SELECT source_name,id,name,issue_number,site_detail_url,cover_date,super_url,thumb_url,description"
                    " FROM Issues WHERE volume_id=? AND source_name=?"
                ),
                [volume_id, source_name],
            )
            rows = cur.fetchall()

            # now process the results
            for row in rows:
                record = CVIssuesResults(
                    {
                        "id": row[1],
                        "name": row[2],
                        "issue_number": row[3],
                        "site_detail_url": row[4],
                        "cover_date": row[5],
                        "image": {"super_url": row[6], "thumb_url": row[7]},
                        "description": row[8],
                    }
                )

                results.append(record)

        return results

    def add_issue_select_details(
        self,
        issue_id: int,
        source_name: str,
        image_url: str,
        thumb_image_url: str,
        cover_date: str,
        site_detail_url: str,
    ) -> None:

        con = lite.connect(self.db_file)

        with con:
            cur = con.cursor()
            con.text_factory = str
            timestamp = datetime.datetime.now()

            data = {
                "id": issue_id,
                "source_name": source_name,
                "super_url": image_url,
                "thumb_url": thumb_image_url,
                "cover_date": cover_date,
                "site_detail_url": site_detail_url,
                "timestamp": timestamp,
            }
            self.upsert(cur, "issues", data)

    def get_issue_select_details(self, issue_id: int, source_name: str) -> SelectDetails:

        con = lite.connect(self.db_file)
        with con:
            cur = con.cursor()
            con.text_factory = str

            cur.execute(
                "SELECT super_url,thumb_url,cover_date,site_detail_url FROM Issues WHERE id=? AND source_name=?",
                [issue_id, source_name],
            )
            row = cur.fetchone()

            details = SelectDetails(
                {
                    "image_url": None,
                    "thumb_image_url": None,
                    "cover_date": None,
                    "site_detail_url": None,
                }
            )
            if row is not None and row[0] is not None:
                details["image_url"] = row[0]
                details["thumb_image_url"] = row[1]
                details["cover_date"] = row[2]
                details["site_detail_url"] = row[3]

            return details

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
