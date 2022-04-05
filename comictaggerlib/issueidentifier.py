"""A class to automatically identify a comic archive"""

# Copyright 2012-2014 Anthony Beville

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at

#     http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import io
import logging
import sys
from typing import List, TypedDict

from comicapi import utils
from comicapi.comicarchive import ComicArchive
from comicapi.genericmetadata import GenericMetadata
from comicapi.issuestring import IssueString
from comictaggerlib.comicvinetalker import ComicVineTalker, ComicVineTalkerException
from comictaggerlib.imagefetcher import ImageFetcher, ImageFetcherException
from comictaggerlib.imagehasher import ImageHasher
from comictaggerlib.resulttypes import IssueResult

logger = logging.getLogger(__name__)

try:
    from PIL import Image

    pil_available = True
except ImportError:
    pil_available = False


class SearchKeys(TypedDict):
    series: str
    issue_number: str
    month: int
    year: int
    issue_count: int


class IssueIdentifierNetworkError(Exception):
    pass


class IssueIdentifierCancelled(Exception):
    pass


class IssueIdentifier:
    result_no_matches = 0
    result_found_match_but_bad_cover_score = 1
    result_found_match_but_not_first_page = 2
    result_multiple_matches_with_bad_image_scores = 3
    result_one_good_match = 4
    result_multiple_good_matches = 5

    def __init__(self, comic_archive: ComicArchive, settings):
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
        self.length_delta_thresh = settings.id_length_delta_thresh

        # used to eliminate unlikely publishers
        self.publisher_filter = [s.strip().lower() for s in settings.id_publisher_filter.split(",")]

        self.additional_metadata = GenericMetadata()
        self.output_function = IssueIdentifier.default_write_output
        self.callback = None
        self.cover_url_callback = None
        self.search_result = self.result_no_matches
        self.cover_page_index = 0
        self.cancel = False
        self.wait_and_retry_on_rate_limit = False

        self.match_list = []

    def set_score_min_threshold(self, thresh: int):
        self.min_score_thresh = thresh

    def set_score_min_distance(self, distance):
        self.min_score_distance = distance

    def set_additional_metadata(self, md):
        self.additional_metadata = md

    def set_name_length_delta_threshold(self, delta):
        self.length_delta_thresh = delta

    def set_publisher_filter(self, filter):
        self.publisher_filter = filter

    def set_hasher_algorithm(self, algo):
        self.image_hasher = algo

    def set_output_function(self, func):
        self.output_function = func

    def calculate_hash(self, image_data):
        if self.image_hasher == "3":
            return ImageHasher(data=image_data).dct_average_hash()
        if self.image_hasher == "2":
            return ImageHasher(data=image_data).average_hash2()

        return ImageHasher(data=image_data).average_hash()

    def get_aspect_ratio(self, image_data):
        try:
            im = Image.open(io.BytesIO(image_data))
            w, h = im.size
            return float(h) / float(w)
        except:
            return 1.5

    def crop_cover(self, image_data):

        im = Image.open(io.BytesIO(image_data))
        w, h = im.size

        try:
            cropped_im = im.crop((int(w / 2), 0, w, h))
        except:
            logger.exception("cropCover() error")
            return None

        output = io.BytesIO()
        cropped_im.save(output, format="PNG")
        cropped_image_data = output.getvalue()
        output.close()

        return cropped_image_data

    def set_progress_callback(self, cb_func):
        self.callback = cb_func

    def set_cover_url_callback(self, cb_func):
        self.cover_url_callback = cb_func

    def get_search_keys(self):

        ca = self.comic_archive
        search_keys: SearchKeys = {}
        search_keys["series"] = None
        search_keys["issue_number"] = None
        search_keys["month"] = None
        search_keys["year"] = None
        search_keys["issue_count"] = None

        if ca is None:
            return None

        if self.only_use_additional_meta_data:
            search_keys["series"] = self.additional_metadata.series
            search_keys["issue_number"] = self.additional_metadata.issue
            search_keys["year"] = self.additional_metadata.year
            search_keys["month"] = self.additional_metadata.month
            search_keys["issue_count"] = self.additional_metadata.issue_count
            return search_keys

        # see if the archive has any useful meta data for searching with
        if ca.has_cix():
            internal_metadata = ca.read_cix()
        elif ca.has_cbi():
            internal_metadata = ca.read_cbi()
        else:
            internal_metadata = ca.read_cbi()

        # try to get some metadata from filename
        md_from_filename = ca.metadata_from_filename()

        # preference order:
        # 1. Additional metadata
        # 1. Internal metadata
        # 1. Filename metadata

        if self.additional_metadata.series is not None:
            search_keys["series"] = self.additional_metadata.series
        elif internal_metadata.series is not None:
            search_keys["series"] = internal_metadata.series
        else:
            search_keys["series"] = md_from_filename.series

        if self.additional_metadata.issue is not None:
            search_keys["issue_number"] = self.additional_metadata.issue
        elif internal_metadata.issue is not None:
            search_keys["issue_number"] = internal_metadata.issue
        else:
            search_keys["issue_number"] = md_from_filename.issue

        if self.additional_metadata.year is not None:
            search_keys["year"] = self.additional_metadata.year
        elif internal_metadata.year is not None:
            search_keys["year"] = internal_metadata.year
        else:
            search_keys["year"] = md_from_filename.year

        if self.additional_metadata.month is not None:
            search_keys["month"] = self.additional_metadata.month
        elif internal_metadata.month is not None:
            search_keys["month"] = internal_metadata.month
        else:
            search_keys["month"] = md_from_filename.month

        if self.additional_metadata.issue_count is not None:
            search_keys["issue_count"] = self.additional_metadata.issue_count
        elif internal_metadata.issue_count is not None:
            search_keys["issue_count"] = internal_metadata.issue_count
        else:
            search_keys["issue_count"] = md_from_filename.issue_count

        return search_keys

    @staticmethod
    def default_write_output(text):
        sys.stdout.write(text)
        sys.stdout.flush()

    def log_msg(self, msg: str, newline=True):
        msg = str(msg)
        if newline:
            msg += "\n"
        self.output_function(msg)

    def get_issue_cover_match_score(
        self,
        comic_vine,
        issue_id,
        primary_img_url,
        primary_thumb_url,
        page_url,
        local_cover_hash_list,
        use_remote_alternates=False,
        use_log=True,
    ):
        # local_cover_hash_list is a list of pre-calculated hashs.
        # use_remote_alternates - indicates to use alternate covers from CV

        try:
            url_image_data = ImageFetcher().fetch(primary_thumb_url, blocking=True)
        except ImageFetcherException as e:
            self.log_msg("Network issue while fetching cover image from Comic Vine. Aborting...")
            raise IssueIdentifierNetworkError from e

        if self.cancel:
            raise IssueIdentifierCancelled

        # alert the GUI, if needed
        if self.cover_url_callback is not None:
            self.cover_url_callback(url_image_data)

        remote_cover_list = []
        item = {}
        item["url"] = primary_img_url

        item["hash"] = self.calculate_hash(url_image_data)
        remote_cover_list.append(item)

        if self.cancel:
            raise IssueIdentifierCancelled

        if use_remote_alternates:
            alt_img_url_list = comic_vine.fetch_alternate_cover_urls(issue_id, page_url)
            for alt_url in alt_img_url_list:
                try:
                    alt_url_image_data = ImageFetcher().fetch(alt_url, blocking=True)
                except ImageFetcherException as e:
                    self.log_msg("Network issue while fetching alt. cover image from Comic Vine. Aborting...")
                    raise IssueIdentifierNetworkError from e

                if self.cancel:
                    raise IssueIdentifierCancelled

                # alert the GUI, if needed
                if self.cover_url_callback is not None:
                    self.cover_url_callback(alt_url_image_data)

                item = {}
                item["url"] = alt_url
                item["hash"] = self.calculate_hash(alt_url_image_data)
                remote_cover_list.append(item)

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
                score_item = {}
                score_item["score"] = score
                score_item["url"] = remote_cover_item["url"]
                score_item["hash"] = remote_cover_item["hash"]
                score_list.append(score_item)
                if use_log:
                    self.log_msg(score, False)

                if score <= self.strong_score_thresh:
                    # such a good score, we can quit now, since for sure we
                    # have a winner
                    done = True
                    break
            if done:
                break

        if use_log:
            self.log_msg(" ]", False)

        best_score_item = min(score_list, key=lambda x: x["score"])

        return best_score_item

    def search(self) -> List[IssueResult]:
        ca = self.comic_archive
        self.match_list: List[IssueResult] = []
        self.cancel = False
        self.search_result = self.result_no_matches

        if not pil_available:
            self.log_msg("Python Imaging Library (PIL) is not available and is needed for issue identification.")
            return self.match_list

        if not ca.seems_to_be_a_comic_archive():
            self.log_msg("Sorry, but " + ca.path + " is not a comic archive!")
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
        # normalize the issue number
        keys["issue_number"] = IssueString(keys["issue_number"]).as_string()

        # we need, at minimum, a series and issue number
        if keys["series"] is None or keys["issue_number"] is None:
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

        comic_vine = ComicVineTalker()
        comic_vine.wait_for_rate_limit = self.wait_and_retry_on_rate_limit

        comic_vine.set_log_func(self.output_function)

        self.log_msg(f"Searching for {keys['series']} #{keys['issue_number']} ...")
        try:
            cv_search_results = comic_vine.search_for_series(keys["series"])
        except ComicVineTalkerException:
            self.log_msg("Network issue while searching for series. Aborting...")
            return []

        if self.cancel:
            return []

        if cv_search_results is None:
            return []

        series_second_round_list = []

        for item in cv_search_results:
            length_approved = False
            publisher_approved = True
            date_approved = True

            # remove any series that starts after the issue year
            if (
                keys["year"] is not None
                and str(keys["year"]).isdigit()
                and item["start_year"] is not None
                and str(item["start_year"]).isdigit()
            ):
                if int(keys["year"]) < int(item["start_year"]):
                    date_approved = False

            # assume that our search name is close to the actual name, say
            # within ,e.g. 5 chars
            # sanitize both the search string and the result so that
            # we are comparing the same type of data
            shortened_key = utils.sanitize_title(keys["series"])
            shortened_item_name = utils.sanitize_title(item["name"])
            if len(shortened_item_name) < (len(shortened_key) + self.length_delta_thresh):
                length_approved = True

            # remove any series from publishers on the filter
            if item["publisher"] is not None:
                publisher = item["publisher"]["name"]
                if publisher is not None and publisher.lower() in self.publisher_filter:
                    publisher_approved = False

            if length_approved and publisher_approved and date_approved:
                series_second_round_list.append(item)

        self.log_msg("Searching in " + str(len(series_second_round_list)) + " series")

        if self.callback is not None:
            self.callback(0, len(series_second_round_list))

        # now sort the list by name length
        series_second_round_list.sort(key=lambda x: len(x["name"]), reverse=False)

        # build a list of volume IDs
        volume_id_list = []
        for series in series_second_round_list:
            volume_id_list.append(series["id"])

        issue_list = None
        try:
            if len(volume_id_list) > 0:
                issue_list = comic_vine.fetch_issues_by_volume_issue_num_and_year(
                    volume_id_list, keys["issue_number"], keys["year"]
                )

        except ComicVineTalkerException:
            self.log_msg("Network issue while searching for series details. Aborting...")
            return []

        if issue_list is None:
            return []

        shortlist = []
        # now re-associate the issues and volumes
        for issue in issue_list:
            for series in series_second_round_list:
                if series["id"] == issue["volume"]["id"]:
                    shortlist.append((series, issue))
                    break

        if keys["year"] is None:
            self.log_msg(f"Found {len(shortlist)} series that have an issue #{keys['issue_number']}")
        else:
            self.log_msg(
                f"Found {len(shortlist)} series that have an issue #{keys['issue_number']} from {keys['year']}"
            )

        # now we have a shortlist of volumes with the desired issue number
        # Do first round of cover matching
        counter = len(shortlist)
        for series, issue in shortlist:
            if self.callback is not None:
                self.callback(counter, len(shortlist) * 3)
                counter += 1

            self.log_msg(
                f"Examining covers for  ID: {series['id']} {series['name']} ({series['start_year']}) ...",
                newline=False,
            )

            # parse out the cover date
            _, month, year = comic_vine.parse_date_str(issue["cover_date"])

            # Now check the cover match against the primary image
            hash_list = [cover_hash]
            if narrow_cover_hash is not None:
                hash_list.append(narrow_cover_hash)

            try:
                image_url = issue["image"]["super_url"]
                thumb_url = issue["image"]["thumb_url"]
                page_url = issue["site_detail_url"]

                score_item = self.get_issue_cover_match_score(
                    comic_vine,
                    issue["id"],
                    image_url,
                    thumb_url,
                    page_url,
                    hash_list,
                    use_remote_alternates=False,
                )
            except:
                self.match_list = []
                return self.match_list

            match: IssueResult = {}
            match["series"] = f"{series['name']} ({series['start_year']})"
            match["distance"] = score_item["score"]
            match["issue_number"] = keys["issue_number"]
            match["cv_issue_count"] = series["count_of_issues"]
            match["url_image_hash"] = score_item["hash"]
            match["issue_title"] = issue["name"]
            match["issue_id"] = issue["id"]
            match["volume_id"] = series["id"]
            match["month"] = month
            match["year"] = year
            match["publisher"] = None
            if series["publisher"] is not None:
                match["publisher"] = series["publisher"]["name"]
            match["image_url"] = image_url
            match["thumb_url"] = thumb_url
            match["page_url"] = page_url
            match["description"] = issue["description"]

            self.match_list.append(match)

            self.log_msg(f" --> {match['distance']}", newline=False)

            self.log_msg("")

        if len(self.match_list) == 0:
            self.log_msg(":-(no matches!")
            self.search_result = self.result_no_matches
            return self.match_list

        # sort list by image match scores
        self.match_list.sort(key=lambda k: k["distance"])

        lst = []
        for i in self.match_list:
            lst.append(i["distance"])

        self.log_msg(f"Compared to covers in {len(self.match_list)} issue(s):", newline=False)
        self.log_msg(str(lst))

        def print_match(item):
            self.log_msg(
                "-----> {0} #{1} {2} ({3}/{4}) -- score: {5}".format(
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
            for i in range(1, min(3, ca.get_number_of_pages())):
                image_data = ca.get_page(i)
                page_hash = self.calculate_hash(image_data)
                hash_list.append(page_hash)

            second_match_list = []
            counter = 2 * len(self.match_list)
            for m in self.match_list:
                if self.callback is not None:
                    self.callback(counter, len(self.match_list) * 3)
                    counter += 1
                self.log_msg(f"Examining alternate covers for ID: {m['volume_id']} {m['series']} ...", newline=False)
                try:
                    score_item = self.get_issue_cover_match_score(
                        comic_vine,
                        m["issue_id"],
                        m["image_url"],
                        m["thumb_url"],
                        m["page_url"],
                        hash_list,
                        use_remote_alternates=True,
                    )
                except:
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
        for item in reversed(self.match_list):
            if item["distance"] > best_score + self.min_score_distance:
                self.match_list.remove(item)

        # One more test for the case choosing limited series first issue vs a trade with the same cover:
        # if we have a given issue count > 1 and the volume from CV has count==1, remove it from match list
        if len(self.match_list) >= 2 and keys["issue_count"] is not None and keys["issue_count"] != 1:
            new_list = []
            for match in self.match_list:
                if match["cv_issue_count"] != 1:
                    new_list.append(match)
                else:
                    self.log_msg(
                        f"Removing volume {match['series']} [{match['volume_id']}] from consideration (only 1 issue)"
                    )

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
            for item in self.match_list:
                print_match(item)
            self.log_msg("--------------------------------------------------------------------------")

        return self.match_list
