from __future__ import annotations

from datetime import datetime

from comicapi import merge, utils
from comicapi.comicarchive import ComicArchive
from comicapi.genericmetadata import GenericMetadata
from comictaggerlib import ctversion
from comictaggerlib.cbltransformer import CBLTransformer
from comictaggerlib.ctsettings.settngs_namespace import SettngsNS
from comictalker.talker_utils import cleanup_html


def prepare_metadata(md: GenericMetadata, new_md: GenericMetadata, config: SettngsNS) -> GenericMetadata:
    if config.Metadata_Options__apply_transform_on_import:
        new_md = CBLTransformer(new_md, config).apply()

    final_md = md.copy()
    if config.Auto_Tag__clear_tags:
        final_md = GenericMetadata()
        if config.Auto_Tag__keep_cli_tags:
            final_md = config.Auto_Tag__metadata.copy()

    final_md.overlay(new_md, config.Metadata_Options__metadata_merge, config.Metadata_Options__metadata_merge_lists)

    issue_id = ""
    if final_md.issue_id:
        issue_id = f" [Issue ID {final_md.issue_id}]"

    origin = ""
    if final_md.data_origin is not None:
        origin = f" using info from {final_md.data_origin.name}"
    notes = f"Tagged with ComicTagger {ctversion.version}{origin} on {datetime.now():%Y-%m-%d %H:%M:%S}.{issue_id}"

    if config.Auto_Tag__auto_imprint:
        final_md.fix_publisher()

    return final_md.replace(
        is_empty=False,
        notes=utils.combine_notes(final_md.notes, notes, "Tagged with ComicTagger"),
        description=cleanup_html(final_md.description, config.Metadata_Options__remove_html_tables) or None,
    )


def read_selected_tags(
    tag_ids: list[str], ca: ComicArchive, mode: merge.Mode = merge.Mode.OVERLAY, merge_lists: bool = False
) -> tuple[GenericMetadata, list[str], Exception | None]:
    md = GenericMetadata()
    error = None
    tags_used = []
    try:
        for tag_id in tag_ids:
            metadata = ca.read_tags(tag_id)
            if not metadata.is_empty:
                md.overlay(
                    metadata,
                    mode=mode,
                    merge_lists=merge_lists,
                )
                tags_used.append(tag_id)
    except Exception as e:
        error = e

    return md, tags_used, error
