from __future__ import annotations

from datetime import datetime

from comicapi import utils
from comicapi.genericmetadata import GenericMetadata
from comictaggerlib import ctversion
from comictaggerlib.cbltransformer import CBLTransformer
from comictaggerlib.ctsettings.settngs_namespace import SettngsNS
from comictalker.talker_utils import cleanup_html


def prepare_metadata(md: GenericMetadata, new_md: GenericMetadata, opts: SettngsNS) -> GenericMetadata:
    if opts.Metadata_Options__apply_transform_on_import:
        new_md = CBLTransformer(new_md, opts).apply()

    final_md = md.copy()
    if opts.Auto_Tag__clear_metadata:
        final_md = GenericMetadata()

    final_md.overlay(new_md, opts.Metadata_Options__metadata_merge, opts.Metadata_Options__metadata_merge_lists)
    if final_md.tag_origin is not None:
        notes = (
            f"Tagged with ComicTagger {ctversion.version} using info from {final_md.tag_origin.name} on"
            + f" {datetime.now():%Y-%m-%d %H:%M:%S}. [Issue ID {final_md.issue_id}]"
        )
    else:
        notes = (
            f"Tagged with ComicTagger {ctversion.version} on"
            + f" {datetime.now():%Y-%m-%d %H:%M:%S}. "
            + (f"[Issue ID {final_md.issue_id}]" if final_md.issue_id else "")
        )

    if opts.Auto_Tag__auto_imprint:
        final_md.fix_publisher()

    return final_md.replace(
        is_empty=False,
        notes=utils.combine_notes(final_md.notes, notes, "Tagged with ComicTagger"),
        description=cleanup_html(final_md.description, opts.Sources__remove_html_tables) or None,
    )
