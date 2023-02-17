"""A class to automatically identify a comic archive"""
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

import io
import logging
import sys
from typing import Any, Callable

import settngs
from typing_extensions import NotRequired, TypedDict

from comicapi import utils
from comicapi.comicarchive import ComicArchive
from comicapi.genericmetadata import GenericMetadata
from comicapi.issuestring import IssueString
from comictaggerlib.imagefetcher import ImageFetcher, ImageFetcherException
from comictaggerlib.imagehasher import ImageHasher
from comictaggerlib.resulttypes import IssueResult
from comictalker.comictalker import ComicTalker, TalkerError

logger = logging.getLogger(__name__)

try:
    from PIL import Image, ImageChops

    pil_available = True
except ImportError:
    pil_available = False


class SearchKeys(TypedDict):
    series: str | None
    issue_number: str | None
    month: int | None
    year: int | None
    issue_count: int | None
    page_count: int | None


class Score(TypedDict):
    score: NotRequired[int]
    url: str
    hash: int


class IssueIdentifierNetworkError(Exception):
    ...


class IssueIdentifierCancelled(Exception):
    ...


class IssueIdentifier:
    result_no_matches = 0
    result_found_match_but_bad_cover_score = 1
    result_found_match_but_not_first_page = 2
    result_multiple_matches_with_bad_image_scores = 3
    result_one_good_match = 4
    result_multiple_good_matches = 5

    def __init__(self, comic_archive: ComicArchive, config: settngs.Namespace, talker: ComicTalker) -> None:
        self.config = config
        self.talker = talker
        self.comic_archive: ComicArchive = comic_archive
        self.image_hasher = 1

        self.only_use_additional_meta_data = False

        # a decent hamming score, good enough to call it a match
        self.min_score_thresh: int = 16

        # for alternate covers, be more stringent, since we're a bit more
        # scattershot in comparisons
        self.min_alternate_score_thresh = 12

        # the min distance a hamming score must be to separate itself from
        # closest neighbor
        self.min_score_distance = 4

        # a very strong hamming score, almost certainly the same image
        self.strong_score_thresh = 8

        # used to eliminate series names that are too long based on our search
        # string
        self.series_match_thresh = config.identifier_series_match_identify_thresh

        # used to eliminate unlikely publishers
        self.publisher_filter = [s.strip().casefold() for s in config.identifier_publisher_filter]

        self.tpb_detection = config.identifier_tpb_detection

        self.additional_metadata = GenericMetadata()
        self.output_function: Callable[[str], None] = IssueIdentifier.default_write_output
        self.callback: Callable[[int, int], None] | None = None
        self.cover_url_callback: Callable[[bytes], None] | None = None
        self.search_result = self.result_no_matches
        self.cover_page_index = 0
        self.cancel = False

        self.match_list: list[IssueResult] = []

    def set_score_min_threshold(self, thresh: int) -> None:
        self.min_score_thresh = thresh

    def set_score_min_distance(self, distance: int) -> None:
        self.min_score_distance = distance

    def set_additional_metadata(self, md: GenericMetadata) -> None:
        self.additional_metadata = md

    def set_name_series_match_threshold(self, delta: int) -> None:
        self.series_match_thresh = delta

    def set_publisher_filter(self, flt: list[str]) -> None:
        self.publisher_filter = flt

    def set_hasher_algorithm(self, algo: int) -> None:
        self.image_hasher = algo

    def set_output_function(self, func: Callable[[str], None]) -> None:
        self.output_function = func

    def calculate_hash(self, image_data: bytes) -> int:
        if self.image_hasher == 3:
            return -1  # ImageHasher(data=image_data).dct_average_hash()
        if self.image_hasher == 2:
            return -1  # ImageHasher(data=image_data).average_hash2()

        return ImageHasher(data=image_data).average_hash()

    def get_aspect_ratio(self, image_data: bytes) -> float:
        try:
            im = Image.open(io.BytesIO(image_data))
            w, h = im.size
            return float(h) / float(w)
        except Exception:
            return 1.5

    def crop_cover(self, image_data: bytes) -> bytes:
        im = Image.open(io.BytesIO(image_data))
        w, h = im.size

        try:
            cropped_im = im.crop((int(w / 2), 0, w, h))
        except Exception:
            logger.exception("cropCover() error")
            return b""

        output = io.BytesIO()
        cropped_im.convert("RGB").save(output, format="PNG")
        cropped_image_data = output.getvalue()
        output.close()

        return cropped_image_data

    # Adapted from https://stackoverflow.com/a/10616717/20629671
    def crop_border(self, image_data: bytes, ratio: int) -> bytes | None:
        im = Image.open(io.BytesIO(image_data))

        # RGBA doesn't work????
        tmp = im.convert("RGB")

        bg = Image.new("RGB", tmp.size, "black")
        diff = ImageChops.difference(tmp, bg)
        diff = ImageChops.add(diff, diff, 2.0, -100)

        bbox = diff.getbbox()

        width_percent = 0
        height_percent = 0

        # If bbox is None that should mean it's solid black
        if bbox:
            width = bbox[2] - bbox[0]
            height = bbox[3] - bbox[1]

            # Convert to percent
            width_percent = int(100 - ((width / im.width) * 100))
            height_percent = int(100 - ((height / im.height) * 100))
            logger.debug(
                "Width: %s Height: %s, ratio: %s  %s ratio met: %s",
                im.width,
                im.height,
                width_percent,
                height_percent,
                width_percent > ratio or height_percent > ratio,
            )

        # If there is a difference return the image otherwise return None
        if width_percent > ratio or height_percent > ratio:
            output = io.BytesIO()
            im.crop(bbox).save(output, format="PNG")
            cropped_image_data = output.getvalue()
            output.close()
            return cropped_image_data
        return None

    def set_progress_callback(self, cb_func: Callable[[int, int], None]) -> None:
        self.callback = cb_func

    def set_cover_url_callback(self, cb_func: Callable[[bytes], None]) -> None:
        self.cover_url_callback = cb_func

    def get_search_keys(self) -> SearchKeys:
        ca = self.comic_archive

        search_keys: SearchKeys
        if self.only_use_additional_meta_data:
            search_keys = SearchKeys(
                series=self.additional_metadata.series,
                issue_number=self.additional_metadata.issue,
                year=self.additional_metadata.year,
                month=self.additional_metadata.month,
                issue_count=self.additional_metadata.issue_count,
                page_count=None,
            )
            return search_keys

        # see if the archive has any useful meta data for searching with
        try:
            if ca.has_cix():
                internal_metadata = ca.read_cix()
            else:
                internal_metadata = ca.read_cbi()
        except Exception as e:
            internal_metadata = GenericMetadata()
            logger.error("Failed to load metadata for %s: %s", ca.path, e)

        # try to get some metadata from filename
        md_from_filename = ca.metadata_from_filename(
            self.config.filename_complicated_parser,
            self.config.filename_remove_c2c,
            self.config.filename_remove_fcbd,
            self.config.filename_remove_publisher,
        )

        working_md = md_from_filename.copy()

        working_md.overlay(internal_metadata)
        working_md.overlay(self.additional_metadata)

        # preference order:
        # 1. Additional metadata
        # 1. Internal metadata
        # 1. Filename metadata
        search_keys = SearchKeys(
            series=working_md.series,
            issue_number=working_md.issue,
            year=working_md.year,
            month=working_md.month,
            issue_count=working_md.issue_count,
            page_count=len(working_md.pages),
        )

        return search_keys

    @staticmethod
    def default_write_output(text: str) -> None:
        sys.stdout.write(text)
        sys.stdout.flush()

    def log_msg(self, msg: Any, newline: bool = True) -> None:
        msg = str(msg)
        if newline:
            msg += "\n"
        self.output_function(msg)

    def get_issue_cover_match_score(
        self,
        issue_id: str,
        primary_img_url: str,
        alt_urls: list[str],
        local_cover_hash_list: list[int],
        use_remote_alternates: bool = False,
        use_log: bool = True,
    ) -> Score:
        # local_cover_hash_list is a list of pre-calculated hashes.
        # use_remote_alternates - indicates to use alternate covers from CV

        # If there is no URL return 0
        if not primary_img_url:
            return Score(score=0, url="", hash=0)

        try:
            url_image_data = ImageFetcher(self.config.runtime_config.user_cache_dir).fetch(
                primary_img_url, blocking=True
            )
        except ImageFetcherException as e:
            self.log_msg("Network issue while fetching cover image from Comic Vine. Aborting...")
            raise IssueIdentifierNetworkError from e

        if self.cancel:
            raise IssueIdentifierCancelled

        # alert the GUI, if needed
        if self.cover_url_callback is not None:
            self.cover_url_callback(url_image_data)

        remote_cover_list = [Score(url=primary_img_url, hash=self.calculate_hash(url_image_data))]

        if self.cancel:
            raise IssueIdentifierCancelled

        if use_remote_alternates:
            for alt_url in alt_urls:
                try:
                    alt_url_image_data = ImageFetcher(self.config.runtime_config.user_cache_dir).fetch(
                        alt_url, blocking=True
                    )
                except ImageFetcherException as e:
                    self.log_msg("Network issue while fetching alt. cover image from Comic Vine. Aborting...")
                    raise IssueIdentifierNetworkError from e

                if self.cancel:
                    raise IssueIdentifierCancelled

                # alert the GUI, if needed
                if self.cover_url_callback is not None:
                    self.cover_url_callback(alt_url_image_data)

                remote_cover_list.append(Score(url=alt_url, hash=self.calculate_hash(alt_url_image_data)))

                if self.cancel:
                    raise IssueIdentifierCancelled

        if use_log and use_remote_alternates:
            self.log_msg(f"[{len(remote_cover_list) - 1} alt. covers]", False)
        if use_log:
            self.log_msg("[ ", False)

        score_list = []
        done = False
        for local_cover_hash in local_cover_hash_list:
            for remote_cover_item in remote_cover_list:
                score = ImageHasher.hamming_distance(local_cover_hash, remote_cover_item["hash"])
                score_list.append(Score(score=score, url=remote_cover_item["url"], hash=remote_cover_item["hash"]))
                if use_log:
                    self.log_msg(score, False)

                if score <= self.strong_score_thresh:
                    # such a good score, we can quit now, since for sure we have a winner
                    done = True
                    break
            if done:
                break

        if use_log:
            self.log_msg(" ]", False)

        best_score_item = min(score_list, key=lambda x: x["score"])

        return best_score_item

    def search(self) -> list[IssueResult]:
        ca = self.comic_archive
        self.match_list = []
        self.cancel = False
        self.search_result = self.result_no_matches

        if not pil_available:
            self.log_msg("Python Imaging Library (PIL) is not available and is needed for issue identification.")
            return self.match_list

        if not ca.seems_to_be_a_comic_archive():
            self.log_msg(f"Sorry, but {ca.path} is not a comic archive!")
            return self.match_list

        cover_image_data = ca.get_page(self.cover_page_index)
        cover_hash = self.calculate_hash(cover_image_data)

        # check the aspect ratio
        # if it's wider than it is high, it's probably a two page spread
        # if so, crop it and calculate a second hash
        narrow_cover_hash = None
        aspect_ratio = self.get_aspect_ratio(cover_image_data)
        if aspect_ratio < 1.0:
            right_side_image_data = self.crop_cover(cover_image_data)
            if right_side_image_data is not None:
                narrow_cover_hash = self.calculate_hash(right_side_image_data)

        keys = self.get_search_keys()
        # normalize the issue number, None will return as ""
        keys["issue_number"] = IssueString(keys["issue_number"]).as_string()

        # we need, at minimum, a series and issue number
        if not (keys["series"] and keys["issue_number"]):
            self.log_msg("Not enough info for a search!")
            return []

        self.log_msg("Going to search for:")
        self.log_msg("\tSeries: " + keys["series"])
        self.log_msg("\tIssue:  " + keys["issue_number"])
        if keys["issue_count"] is not None:
            self.log_msg("\tCount:  " + str(keys["issue_count"]))
        if keys["year"] is not None:
            self.log_msg("\tYear:   " + str(keys["year"]))
        if keys["month"] is not None:
            self.log_msg("\tMonth:  " + str(keys["month"]))

        self.log_msg(f"Searching for {keys['series']} #{keys['issue_number']} ...")
        try:
            ct_search_results = self.talker.search_for_series(keys["series"])
        except TalkerError as e:
            self.log_msg(f"Error searching for series.\n{e}")
            return []

        if self.cancel:
            return []

        if ct_search_results is None:
            return []

        series_second_round_list = []

        for item in ct_search_results:
            length_approved = False
            publisher_approved = True
            date_approved = True

            # remove any series that starts after the issue year
            if keys["year"] is not None and item.start_year is not None:
                if keys["year"] < item.start_year:
                    date_approved = False

            for name in [item.name, *item.aliases]:
                if utils.titles_match(keys["series"], name, self.series_match_thresh):
                    length_approved = True
                    break
            # remove any series from publishers on the filter
            if item.publisher is not None:
                publisher = item.publisher
                if publisher is not None and publisher.casefold() in self.publisher_filter:
                    publisher_approved = False

            if length_approved and publisher_approved and date_approved:
                series_second_round_list.append(item)

        self.log_msg("Searching in " + str(len(series_second_round_list)) + " series")

        if self.callback is not None:
            self.callback(0, len(series_second_round_list))

        # now sort the list by name length
        series_second_round_list.sort(key=lambda x: len(x.name), reverse=False)

        series_by_id = {series.id: series for series in series_second_round_list}

        issue_list = None
        try:
            if len(series_by_id) > 0:
                issue_list = self.talker.fetch_issues_by_series_issue_num_and_year(
                    list(series_by_id.keys()), keys["issue_number"], keys["year"]
                )
        except TalkerError as e:
            self.log_msg(f"Issue with while searching for series details. Aborting...\n{e}")
            return []

        if issue_list is None:
            return []

        shortlist = []
        # now re-associate the issues and series
        # is this really needed?
        for issue in issue_list:
            if issue.series.id in series_by_id:
                shortlist.append((series_by_id[issue.series.id], issue))

        if keys["year"] is None:
            self.log_msg(f"Found {len(shortlist)} series that have an issue #{keys['issue_number']}")
        else:
            self.log_msg(
                f"Found {len(shortlist)} series that have an issue #{keys['issue_number']} from {keys['year']}"
            )

        # now we have a shortlist of series with the desired issue number
        # Do first round of cover matching
        counter = len(shortlist)
        for series, issue in shortlist:
            if self.callback is not None:
                self.callback(counter, len(shortlist) * 3)
                counter += 1

            self.log_msg(
                f"Examining covers for  ID: {series.id} {series.name} ({series.start_year}) ...",
                newline=False,
            )

            # parse out the cover date
            _, month, year = utils.parse_date_str(issue.cover_date)

            # Now check the cover match against the primary image
            hash_list = [cover_hash]
            if narrow_cover_hash is not None:
                hash_list.append(narrow_cover_hash)

            cropped_border = self.crop_border(cover_image_data, self.config.identifier_border_crop_percent)
            if cropped_border is not None:
                hash_list.append(self.calculate_hash(cropped_border))
                logger.info("Adding cropped cover to the hashlist")

            try:
                image_url = issue.image_url
                alt_urls = issue.alt_image_urls

                score_item = self.get_issue_cover_match_score(
                    issue.id, image_url, alt_urls, hash_list, use_remote_alternates=False
                )
            except Exception:
                logger.exception("Scoring series failed")
                self.match_list = []
                return self.match_list

            match: IssueResult = {
                "series": f"{series.name} ({series.start_year})",
                "distance": score_item["score"],
                "issue_number": keys["issue_number"],
                "cv_issue_count": series.count_of_issues,
                "url_image_hash": score_item["hash"],
                "issue_title": issue.name,
                "issue_id": issue.id,
                "series_id": series.id,
                "month": month,
                "year": year,
                "publisher": None,
                "image_url": image_url,
                "alt_image_urls": alt_urls,
                "description": issue.description,
            }
            if series.publisher is not None:
                match["publisher"] = series.publisher

            self.match_list.append(match)

            self.log_msg(f" --> {match['distance']}", newline=False)

            self.log_msg("")

        if len(self.match_list) == 0:
            self.log_msg(":-( no matches!")
            self.search_result = self.result_no_matches
            return self.match_list

        # sort list by image match scores
        self.match_list.sort(key=lambda k: k["distance"])

        lst = []
        for i in self.match_list:
            lst.append(i["distance"])

        self.log_msg(f"Compared to covers in {len(self.match_list)} issue(s):", newline=False)
        self.log_msg(str(lst))

        def print_match(item: IssueResult) -> None:
            self.log_msg(
                "-----> {} #{} {} ({}/{}) -- score: {}".format(
                    item["series"],
                    item["issue_number"],
                    item["issue_title"],
                    item["month"],
                    item["year"],
                    item["distance"],
                )
            )

        best_score: int = self.match_list[0]["distance"]

        if best_score >= self.min_score_thresh:
            # we have 1 or more low-confidence matches (all bad cover scores)
            # look at a few more pages in the archive, and also alternate covers online
            self.log_msg("Very weak scores for the cover. Analyzing alternate pages and covers...")
            hash_list = [cover_hash]
            if narrow_cover_hash is not None:
                hash_list.append(narrow_cover_hash)
            for page_index in range(1, min(3, ca.get_number_of_pages())):
                image_data = ca.get_page(page_index)
                page_hash = self.calculate_hash(image_data)
                hash_list.append(page_hash)

            second_match_list = []
            counter = 2 * len(self.match_list)
            for m in self.match_list:
                if self.callback is not None:
                    self.callback(counter, len(self.match_list) * 3)
                    counter += 1
                self.log_msg(f"Examining alternate covers for ID: {m['series_id']} {m['series']} ...", newline=False)
                try:
                    score_item = self.get_issue_cover_match_score(
                        m["issue_id"],
                        m["image_url"],
                        m["alt_image_urls"],
                        hash_list,
                        use_remote_alternates=True,
                    )
                except Exception:
                    logger.exception("failed examining alt covers")
                    self.match_list = []
                    return self.match_list
                self.log_msg(f"--->{score_item['score']}")
                self.log_msg("")

                if score_item["score"] < self.min_alternate_score_thresh:
                    second_match_list.append(m)
                    m["distance"] = score_item["score"]

            if len(second_match_list) == 0:
                if len(self.match_list) == 1:
                    self.log_msg("No matching pages in the issue.")
                    self.log_msg("--------------------------------------------------------------------------")
                    print_match(self.match_list[0])
                    self.log_msg("--------------------------------------------------------------------------")
                    self.search_result = self.result_found_match_but_bad_cover_score
                else:
                    self.log_msg("--------------------------------------------------------------------------")
                    self.log_msg("Multiple bad cover matches!  Need to use other info...")
                    self.log_msg("--------------------------------------------------------------------------")
                    self.search_result = self.result_multiple_matches_with_bad_image_scores
                return self.match_list

            # We did good, found something!
            self.log_msg("Success in secondary/alternate cover matching!")

            self.match_list = second_match_list
            # sort new list by image match scores
            self.match_list.sort(key=lambda k: k["distance"])
            best_score = self.match_list[0]["distance"]
            self.log_msg("[Second round cover matching: best score = {best_score}]")
            # now drop down into the rest of the processing

        if self.callback is not None:
            self.callback(99, 100)

        # now pare down list, remove any item more than specified distant from the top scores
        for match_item in reversed(self.match_list):
            if match_item["distance"] > best_score + self.min_score_distance:
                self.match_list.remove(match_item)

        # One more test for the case choosing limited series first issue vs a trade with the same cover:
        # if we have an issue count == 1 or a page count > 100, we only include TPBs
        if len(self.match_list) >= 2 and (keys["issue_count"] is not None or keys["page_count"] is not None):
            issue_count = keys["issue_count"] or 0
            page_count = keys["page_count"] or 0
            if issue_count == 1:
                if self.tpb_detection and page_count > 100:
                    new_list = []
                    for match in self.match_list:
                        if "tpb" in match["issue_title"].casefold():
                            new_list.append(match)
                        else:
                            self.log_msg(
                                f"Removing series {match['series']} [{match['series_id']}] from consideration (not a tpb)"
                            )
            # if we have a given issue count > 1 and the series from CV has count==1, remove it from match list
            else:
                new_list = []
                for match in self.match_list:
                    if match["cv_issue_count"] == 1:
                        self.log_msg(
                            f"Removing series {match['series']} [{match['series_id']}] from consideration (only 1 issue)"
                        )
                    else:
                        new_list.append(match)

                if len(new_list) > 0:
                    self.match_list = new_list

        if len(self.match_list) == 1:
            self.log_msg("--------------------------------------------------------------------------")
            print_match(self.match_list[0])
            self.log_msg("--------------------------------------------------------------------------")
            self.search_result = self.result_one_good_match

        elif len(self.match_list) == 0:
            self.log_msg("--------------------------------------------------------------------------")
            self.log_msg("No matches found :(")
            self.log_msg("--------------------------------------------------------------------------")
            self.search_result = self.result_no_matches
        else:
            # we've got multiple good matches:
            self.log_msg("More than one likely candidate.")
            self.search_result = self.result_multiple_good_matches
            self.log_msg("--------------------------------------------------------------------------")
            for match_item in self.match_list:
                print_match(match_item)
            self.log_msg("--------------------------------------------------------------------------")

        return self.match_list
