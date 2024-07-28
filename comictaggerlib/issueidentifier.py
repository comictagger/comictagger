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
from operator import attrgetter
from typing import Any, Callable

from typing_extensions import NotRequired, TypedDict

from comicapi import utils
from comicapi.comicarchive import ComicArchive
from comicapi.genericmetadata import ComicSeries, GenericMetadata
from comicapi.issuestring import IssueString
from comictaggerlib.ctsettings import ct_ns
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
    series: str
    issue_number: str
    alternate_number: str | None
    month: int | None
    year: int | None
    issue_count: int | None
    alternate_count: int | None
    publisher: str | None
    imprint: str | None


class Score(TypedDict):
    score: NotRequired[int]
    url: str
    remote_hash: int
    local_hash_name: str
    local_hash: int


class IssueIdentifierNetworkError(Exception): ...


class IssueIdentifierCancelled(Exception): ...


class IssueIdentifier:
    result_no_matches = 0
    result_found_match_but_bad_cover_score = 1
    result_found_match_but_not_first_page = 2
    result_multiple_matches_with_bad_image_scores = 3
    result_one_good_match = 4
    result_multiple_good_matches = 5

    def __init__(
        self,
        comic_archive: ComicArchive,
        config: ct_ns,
        talker: ComicTalker,
        metadata: GenericMetadata = GenericMetadata(),
    ) -> None:
        self.config = config
        self.talker = talker
        self.comic_archive: ComicArchive = comic_archive
        self.md = metadata
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
        self.series_match_thresh = config.Issue_Identifier__series_match_identify_thresh

        # used to eliminate unlikely publishers
        self.use_publisher_filter = config.Auto_Tag__use_publisher_filter
        self.publisher_filter = [s.strip().casefold() for s in config.Auto_Tag__publisher_filter]

        self.additional_metadata = GenericMetadata()
        self.output_function: Callable[[str], None] = print
        self.progress_callback: Callable[[int, int], None] | None = None
        self.cover_url_callback: Callable[[bytes], None] | None = None
        self.search_result = self.result_no_matches
        self.cancel = False

        self.match_list: list[IssueResult] = []

    def set_output_function(self, func: Callable[[str], None]) -> None:
        self.output_function = func

    def set_progress_callback(self, cb_func: Callable[[int, int], None]) -> None:
        self.progress_callback = cb_func

    def set_cover_url_callback(self, cb_func: Callable[[bytes], None]) -> None:
        self.cover_url_callback = cb_func

    def calculate_hash(self, image_data: bytes) -> int:
        if self.image_hasher == 3:
            return ImageHasher(data=image_data).p_hash()
        if self.image_hasher == 2:
            return -1  # ImageHasher(data=image_data).average_hash2()

        return ImageHasher(data=image_data).average_hash()

    def log_msg(self, msg: Any) -> None:
        msg = str(msg)
        for handler in logging.getLogger().handlers:
            handler.flush()
        self.output(msg)

    def output(self, *args: Any, file: Any = None, **kwargs: Any) -> None:
        # We intercept and discard the file argument otherwise everything is passed to self.output_function

        # Ensure args[0] is defined and is a string for logger.info
        if not args:
            log_args: tuple[Any, ...] = ("",)
        elif isinstance(args[0], str):
            log_args = (args[0].strip("\n"), *args[1:])
        else:
            log_args = args
        log_msg = " ".join([str(x) for x in log_args])

        # Always send to logger so that we have a record for troubleshooting
        logger.info(log_msg, **kwargs)

        # If we are verbose or quiet we don't need to call the output function
        if self.config.Runtime_Options__verbose > 0 or self.config.Runtime_Options__quiet:
            return

        # default output is stdout
        self.output_function(*args, **kwargs)

    def identify(self, ca: ComicArchive, md: GenericMetadata) -> tuple[int, list[IssueResult]]:
        if not self._check_requirements(ca):
            return self.result_no_matches, []

        terms, images, extra_images = self._get_search_terms(ca, md)

        # we need, at minimum, a series and issue number
        if not (terms["series"] and terms["issue_number"]):
            self.log_msg("Not enough info for a search!")
            return self.result_no_matches, []

        self._print_terms(terms, images)

        issues = self._search_for_issues(terms)

        self.log_msg(f"Found {len(issues)} series that have an issue #{terms['issue_number']}")

        final_cover_matching = self._cover_matching(terms, images, extra_images, issues)

        # One more test for the case choosing limited series first issue vs a trade with the same cover:
        # if we have a given issue count > 1 and the series from CV has count==1, remove it from match list
        if len(final_cover_matching) > 1 and terms["issue_count"] is not None and terms["issue_count"] != 1:
            for match in final_cover_matching.copy():
                if match.issue_count == 1:
                    self.log_msg(
                        f"Removing series {match.series} [{match.series_id}] from consideration (only 1 issue)"
                    )
                    final_cover_matching.remove(match)

        if final_cover_matching:
            best_score = final_cover_matching[0].distance
        else:
            best_score = 0
        if best_score >= self.min_score_thresh:
            if len(final_cover_matching) == 1:
                self.log_msg("No matching pages in the issue.")
                self.log_msg("--------------------------------------------------------------------------")
                self._print_match(final_cover_matching[0])
                self.log_msg("--------------------------------------------------------------------------")
                search_result = self.result_found_match_but_bad_cover_score
            else:
                self.log_msg("--------------------------------------------------------------------------")
                self.log_msg("Multiple bad cover matches!  Need to use other info...")
                self.log_msg("--------------------------------------------------------------------------")
                search_result = self.result_multiple_matches_with_bad_image_scores
        else:
            if len(final_cover_matching) == 1:
                self.log_msg("--------------------------------------------------------------------------")
                self._print_match(final_cover_matching[0])
                self.log_msg("--------------------------------------------------------------------------")
                search_result = self.result_one_good_match

            elif len(self.match_list) == 0:
                self.log_msg("--------------------------------------------------------------------------")
                self.log_msg("No matches found :(")
                self.log_msg("--------------------------------------------------------------------------")
                search_result = self.result_no_matches
            else:
                # we've got multiple good matches:
                self.log_msg("More than one likely candidate.")
                search_result = self.result_multiple_good_matches
                self.log_msg("--------------------------------------------------------------------------")
                for match_item in final_cover_matching:
                    self._print_match(match_item)
                self.log_msg("--------------------------------------------------------------------------")

        return search_result, final_cover_matching

    def _crop_double_page(self, im: Image.Image) -> Image.Image | None:
        w, h = im.size

        try:
            cropped_im = im.crop((int(w / 2), 0, w, h))
        except Exception:
            logger.exception("cropCover() error")
            return None

        return cropped_im

    # Adapted from https://stackoverflow.com/a/10616717/20629671
    def _crop_border(self, im: Image.Image, ratio: int) -> Image.Image | None:
        assert Image
        assert ImageChops
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
            return im.crop(bbox)
        return None

    def _get_remote_hashes(self, urls: list[str]) -> list[tuple[str, int]]:
        remote_hashes: list[tuple[str, int]] = []
        for url in urls:
            try:
                alt_url_image_data = ImageFetcher(self.config.Runtime_Options__config.user_cache_dir).fetch(
                    url, blocking=True
                )
            except ImageFetcherException as e:
                self.log_msg(f"Network issue while fetching alt. cover image from {self.talker.name}. Aborting...")
                raise IssueIdentifierNetworkError from e

            self._user_canceled(self.cover_url_callback, alt_url_image_data)

            remote_hashes.append((url, self.calculate_hash(alt_url_image_data)))

            if self.cancel:
                raise IssueIdentifierCancelled
        return remote_hashes

    def _get_issue_cover_match_score(
        self,
        primary_img_url: str,
        alt_urls: list[str],
        local_hashes: list[tuple[str, int]],
        use_alt_urls: bool = False,
    ) -> Score:
        # local_hashes is a list of pre-calculated hashes.
        # use_alt_urls - indicates to use alternate covers from CV

        # If there is no URL return 100
        if not primary_img_url:
            return Score(score=100, url="", remote_hash=0)

        self._user_canceled()

        urls = [primary_img_url]
        if use_alt_urls:
            urls.extend(alt_urls)
            self.log_msg(f"[{len(alt_urls)} alt. covers]")

        remote_hashes = self._get_remote_hashes(urls)

        score_list = []
        done = False
        for local_hash in local_hashes:
            for remote_hash in remote_hashes:
                score = ImageHasher.hamming_distance(local_hash[1], remote_hash[1])
                score_list.append(
                    Score(
                        score=score,
                        url=remote_hash[0],
                        remote_hash=remote_hash[1],
                        local_hash_name=local_hash[0],
                        local_hash=local_hash[1],
                    )
                )

                self.log_msg(f" -  {score:03}")

                if score <= self.strong_score_thresh:
                    # such a good score, we can quit now, since for sure we have a winner
                    done = True
                    break
            if done:
                break

        best_score_item = min(score_list, key=lambda x: x["score"])

        return best_score_item

    def _check_requirements(self, ca: ComicArchive) -> bool:

        if not pil_available:
            self.log_msg("Python Imaging Library (PIL) is not available and is needed for issue identification.")
            return False

        if not ca.seems_to_be_a_comic_archive():
            self.log_msg(f"Sorry, but {ca.path} is not a comic archive!")
            return False
        return True

    def _process_cover(self, name: str, image_data: bytes) -> list[tuple[str, Image.Image]]:
        assert Image
        cover_image = Image.open(io.BytesIO(image_data))
        images = [(name, cover_image)]

        # check the aspect ratio
        # if it's wider than it is high, it's probably a two page spread (back_cover, front_cover)
        # if so, crop it and calculate a second hash
        aspect_ratio = float(cover_image.height) / float(cover_image.width)
        if aspect_ratio < 1.0:
            im = self._crop_double_page(cover_image)
            if im is not None:
                images.append(("double page", im))

        # Check and remove black borders. Helps in identifying comics with an excessive black border like https://comicvine.gamespot.com/marvel-graphic-novel-1-the-death-of-captain-marvel/4000-21782/
        cropped = self._crop_border(cover_image, self.config.Issue_Identifier__border_crop_percent)
        if cropped is not None:
            images.append(("black border cropped", cropped))

        return images

    def _get_images(self, ca: ComicArchive, md: GenericMetadata) -> list[tuple[str, Image.Image]]:
        covers: list[tuple[str, Image.Image]] = []
        for cover_index in md.get_cover_page_index_list():
            image_data = ca.get_page(cover_index)
            covers.extend(self._process_cover(f"{cover_index}", image_data))
        return covers

    def _get_extra_images(self, ca: ComicArchive, md: GenericMetadata) -> list[tuple[str, Image.Image]]:
        assert md
        covers: list[tuple[str, Image.Image]] = []
        for cover_index in range(1, min(3, ca.get_number_of_pages())):
            image_data = ca.get_page(md.get_archive_page_index(cover_index))
            covers.extend(self._process_cover(f"{cover_index}", image_data))
        return covers

    def _get_search_keys(self, md: GenericMetadata) -> Any:
        search_keys = SearchKeys(
            series=md.series,
            issue_number=IssueString(md.issue).as_string(),
            alternate_number=IssueString(md.alternate_number).as_string(),
            month=md.month,
            year=md.year,
            issue_count=md.issue_count,
            alternate_count=md.alternate_count,
            publisher=md.publisher,
            imprint=md.imprint,
        )
        return search_keys

    def _get_search_terms(
        self, ca: ComicArchive, md: GenericMetadata
    ) -> tuple[SearchKeys, list[tuple[str, Image.Image]], list[tuple[str, Image.Image]]]:
        return self._get_search_keys(md), self._get_images(ca, md), self._get_extra_images(ca, md)

    def _user_canceled(self, callback: Callable[..., Any] | None = None, *args: Any) -> Any:
        if self.cancel:
            raise IssueIdentifierCancelled
        if callback is not None:
            return callback(*args)

    def _print_terms(self, keys: SearchKeys, images: list[tuple[str, Image.Image]]) -> None:
        assert keys["series"]
        assert keys["issue_number"]
        self.log_msg(f"Using {self.talker.name} to search for:")
        self.log_msg("\tSeries: " + keys["series"])
        self.log_msg("\tIssue:  " + keys["issue_number"])
        # if keys["alternate_number"] is not None:
        #     self.log_msg("\tAlternate Issue:  " + str(keys["alternate_number"]))
        if keys["month"] is not None:
            self.log_msg("\tMonth:  " + str(keys["month"]))
        if keys["year"] is not None:
            self.log_msg("\tYear:   " + str(keys["year"]))
        if keys["issue_count"] is not None:
            self.log_msg("\tCount:  " + str(keys["issue_count"]))
        # if keys["alternate_count"] is not None:
        #     self.log_msg("\tAlternate Count:  " + str(keys["alternate_count"]))
        # if keys["publisher"] is not None:
        #     self.log_msg("\tPublisher:  " + str(keys["publisher"]))
        # if keys["imprint"] is not None:
        #     self.log_msg("\tImprint:  " + str(keys["imprint"]))
        for name, _ in images:
            self.log_msg("Cover: " + name)

        self.log_msg(f"Searching for {keys['series']} #{keys['issue_number']} ...")

    def _filter_series(self, terms: SearchKeys, search_results: list[ComicSeries]) -> list[ComicSeries]:
        assert terms["series"]

        filtered_results = []
        for item in search_results:
            length_approved = False
            publisher_approved = True
            date_approved = True

            # remove any series that starts after the issue year
            if terms["year"] is not None and item.start_year is not None:
                if item.start_year > terms["year"] + 1:
                    date_approved = False

            for name in [item.name, *item.aliases]:
                if utils.titles_match(terms["series"], name, self.series_match_thresh):
                    length_approved = True
                    break
            # remove any series from publishers on the filter
            if self.use_publisher_filter and item.publisher:
                if item.publisher.casefold() in self.publisher_filter:
                    publisher_approved = False

            if length_approved and publisher_approved and date_approved:
                filtered_results.append(item)
            else:
                logger.debug(
                    "Filtered out series: '%s' length approved: '%s', publisher approved: '%s', date approved: '%s'",
                    item.name,
                    length_approved,
                    publisher_approved,
                    date_approved,
                )
        return filtered_results

    def _calculate_hashes(self, images: list[tuple[str, Image.Image]]) -> list[tuple[str, int]]:
        hashes = []
        for name, image in images:
            hashes.append((name, ImageHasher(image=image).average_hash()))
        return hashes

    def _match_covers(
        self,
        terms: SearchKeys,
        images: list[tuple[str, Image.Image]],
        issues: list[tuple[ComicSeries, GenericMetadata]],
        use_alternates: bool,
    ) -> list[IssueResult]:
        assert terms["issue_number"]
        match_results: list[IssueResult] = []
        hashes = self._calculate_hashes(images)
        counter = 0
        alternate = ""
        if use_alternates:
            alternate = " Alternate"
        for series, issue in issues:
            self._user_canceled(self.progress_callback, counter, len(issues))
            counter += 1

            self.log_msg(
                f"Examining{alternate} covers for Series ID: {series.id} {series.name} ({series.start_year}):",
            )

            try:
                image_url = issue._cover_image or ""
                alt_urls = issue._alternate_images

                score_item = self._get_issue_cover_match_score(image_url, alt_urls, hashes, use_alt_urls=use_alternates)
            except Exception:
                logger.exception(f"Scoring series{alternate} covers failed")
                return []

            match = IssueResult(
                series=f"{series.name} ({series.start_year})",
                distance=score_item["score"],
                issue_number=terms["issue_number"],
                issue_count=series.count_of_issues,
                url_image_hash=score_item["remote_hash"],
                issue_title=issue.title or "",
                issue_id=issue.issue_id or "",
                series_id=series.id,
                month=issue.month,
                year=issue.year,
                publisher=None,
                image_url=image_url,
                alt_image_urls=alt_urls,
                description=issue.description or "",
            )
            if series.publisher is not None:
                match.publisher = series.publisher

            match_results.append(match)

            self.log_msg(f"best score {match.distance:03}")

            self.log_msg("")
        return match_results

    def _print_match(self, item: IssueResult) -> None:
        self.log_msg(
            "-----> {} #{} {} ({}/{}) -- score: {}".format(
                item.series,
                item.issue_number,
                item.issue_title,
                item.month,
                item.year,
                item.distance,
            )
        )

    def _search_for_issues(self, terms: SearchKeys) -> list[tuple[ComicSeries, GenericMetadata]]:
        try:
            search_results = self.talker.search_for_series(
                terms["series"],
                callback=lambda x, y: self._user_canceled(self.progress_callback, x, y),
                series_match_thresh=self.config.Issue_Identifier__series_match_search_thresh,
            )
        except TalkerError as e:
            self.log_msg(f"Error searching for series.\n{e}")
            return []
        # except IssueIdentifierCancelled:
        #     return []

        if not search_results:
            return []

        filtered_series = self._filter_series(terms, search_results)
        if not filtered_series:
            return []

        self.log_msg(f"Searching in {len(filtered_series)} series")

        self._user_canceled(self.progress_callback, 0, len(filtered_series))

        series_by_id = {series.id: series for series in filtered_series}

        try:
            talker_result = self.talker.fetch_issues_by_series_issue_num_and_year(
                list(series_by_id.keys()), terms["issue_number"], terms["year"]
            )
        except TalkerError as e:
            self.log_msg(f"Issue with while searching for series details. Aborting...\n{e}")
            return []
        # except IssueIdentifierCancelled:
        #     return []

        if not talker_result:
            return []

        self._user_canceled(self.progress_callback, 0, 0)

        issues: list[tuple[ComicSeries, GenericMetadata]] = []

        # now re-associate the issues and series
        for issue in talker_result:
            if issue.series_id in series_by_id:
                issues.append((series_by_id[issue.series_id], issue))
            else:
                logger.warning("Talker '%s' is returning arbitrary series when searching by id", self.talker.id)
        return issues

    def _cover_matching(
        self,
        terms: SearchKeys,
        images: list[tuple[str, Image.Image]],
        extra_images: list[tuple[str, Image.Image]],
        issues: list[tuple[ComicSeries, GenericMetadata]],
    ) -> list[IssueResult]:
        cover_matching_1 = self._match_covers(terms, images, issues, use_alternates=False)

        if len(cover_matching_1) == 0:
            self.log_msg(":-( no matches!")
            return cover_matching_1

        # sort list by image match scores
        cover_matching_1.sort(key=attrgetter("distance"))

        lst = []
        for i in cover_matching_1:
            lst.append(i.distance)

        self.log_msg(f"Compared to covers in {len(cover_matching_1)} issue(s): {lst}")

        cover_matching_2 = []
        final_cover_matching = cover_matching_1
        if cover_matching_1[0].distance >= self.min_score_thresh:
            # we have 1 or more low-confidence matches (all bad cover scores)
            # look at a few more pages in the archive, and also alternate covers online
            self.log_msg("Very weak scores for the cover. Analyzing alternate pages and covers...")

            temp = self._match_covers(terms, images + extra_images, issues, use_alternates=True)
            for score in temp:
                if score.distance < self.min_alternate_score_thresh:
                    cover_matching_2.append(score)

            if len(cover_matching_2) > 0:
                # We did good, found something!
                self.log_msg("Success in secondary/alternate cover matching!")

                final_cover_matching = cover_matching_2
                # sort new list by image match scores
                final_cover_matching.sort(key=attrgetter("distance"))
                self.log_msg("[Second round cover matching: best score = {best_score}]")
                # now drop down into the rest of the processing

        best_score = final_cover_matching[0].distance
        # now pare down list, remove any item more than specified distant from the top scores
        for match_item in reversed(final_cover_matching):
            if match_item.distance > (best_score + self.min_score_distance):
                final_cover_matching.remove(match_item)
        return final_cover_matching
