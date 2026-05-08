from __future__ import annotations

import logging
import re
from collections.abc import Callable
from typing import Any

from comicapi.comicarchive import ComicArchive
from comicapi.genericmetadata import GenericMetadata
from comicapi.utils import PublisherManager
from comictaggerlib.ctsettings import ct_ns
from comictaggerlib.issueidentifier import IssueIdentifier, IssueIdentifierOptions
from comictaggerlib.issueidentifier import Result as IIResult
from comictaggerlib.md import prepare_metadata
from comictaggerlib.resulttypes import Action, MatchStatus, OnlineMatchResults, Result, Status
from comictalker.comictalker import ComicTalker, RLCallBack, TalkerError

logger = logging.getLogger(__name__)


def identify_comic(
    ca: ComicArchive,
    md: GenericMetadata,
    tags_read: list[str],
    match_results: OnlineMatchResults,
    config: ct_ns,
    talker: ComicTalker,
    publishers: PublisherManager,
    output: Callable[[str], Any],
    on_rate_limit: RLCallBack | None,
    on_progress: Callable[[int, int, bytes], Any] | None = None,
) -> tuple[Result, OnlineMatchResults]:
    # ct_md, results, matches, match_results
    if md is None or md.is_empty:
        logger.error("No metadata given to search online with!")
        res = Result(
            Action.save,
            status=Status.match_failure,
            original_path=ca.path,
            match_status=MatchStatus.no_match,
            tags_read=tags_read,
        )
        match_results.no_matches.append(res)
        return res, match_results
    iio = IssueIdentifierOptions(
        series_match_search_thresh=config.Issue_Identifier__series_match_search_thresh,
        series_match_identify_thresh=config.Issue_Identifier__series_match_identify_thresh,
        use_publisher_filter=config.Auto_Tag__use_publisher_filter,
        publisher_filter=config.Auto_Tag__publisher_filter,
        quiet=config.Runtime_Options__quiet,
        cache_dir=config.Runtime_Options__config.user_cache_dir,
        border_crop_percent=config.Issue_Identifier__border_crop_percent,
        talker=talker,
    )
    ii = IssueIdentifier(
        iio,
        output=output,
        on_rate_limit=on_rate_limit,
        on_progress=on_progress,
    )

    if not config.Auto_Tag__use_year_when_identifying:
        md.year = None
    if config.Auto_Tag__ignore_leading_numbers_in_filename and md.series is not None:
        md.series = re.sub(r"^([\d.]+)", "", md.series)

    result, matches = ii.identify(ca, md)

    res = Result(
        Action.save,
        status=Status.match_failure,
        original_path=ca.path,
        online_results=matches,
        tags_read=tags_read,
    )
    if result == IIResult.multiple_bad_cover_scores:
        res.match_status = MatchStatus.low_confidence_match

        logger.error("Online search: Multiple low confidence matches. Save aborted")
        match_results.low_confidence_matches.append(res)
        return res, match_results

    if result == IIResult.single_bad_cover_score and not config.Auto_Tag__save_on_low_confidence:
        logger.error("Online search: Low confidence match. Save aborted")
        res.match_status = MatchStatus.low_confidence_match

        match_results.low_confidence_matches.append(res)
        return res, match_results

    if result == IIResult.multiple_good_matches:
        logger.error("Online search: Multiple good matches. Save aborted")
        res.match_status = MatchStatus.multiple_match

        match_results.multiple_matches.append(res)
        return res, match_results

    if result == IIResult.no_matches:
        logger.error("Online search: No match found. Save aborted")
        res.match_status = MatchStatus.no_match

        match_results.no_matches.append(res)
        return res, match_results

    # we got here, so we have a single match
    # now get the particular issue data
    try:
        assert matches[0].md.issue_id
        ct_md = talker.fetch_comic_data(issue_id=matches[0].md.issue_id, on_rate_limit=on_rate_limit)
    except TalkerError as e:
        logger.exception("Error retrieving issue details. Save aborted. %s", e)
        ct_md = GenericMetadata()

    ct_md = prepare_metadata(md, ct_md, publishers, config)

    if ct_md.is_empty:
        res.status = Status.fetch_data_failure
        res.match_status = MatchStatus.good_match

        match_results.fetch_data_failures.append(res)
        return res, match_results

    res.status = Status.success
    res.md = ct_md
    if result == IIResult.single_good_match:
        res.match_status = MatchStatus.good_match

    return res, match_results
