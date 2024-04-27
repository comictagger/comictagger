from __future__ import annotations

from datetime import datetime

from comicapi import utils
from comicapi.genericmetadata import GenericMetadata
from comictaggerlib import ctversion
from comictaggerlib.cbltransformer import CBLTransformer
from comictaggerlib.ctsettings.settngs_namespace import SettngsNS
from comictalker.talker_utils import cleanup_html


def prepare_metadata(md: GenericMetadata, new_md: GenericMetadata, opts: SettngsNS) -> GenericMetadata:
    if opts.Comic_Book_Lover__apply_transform_on_import:
        new_md = CBLTransformer(new_md, opts).apply()

    final_md = md.copy()
    if opts.Issue_Identifier__clear_metadata:
        final_md = GenericMetadata()

    final_md.overlay(new_md)
    assert final_md.tag_origin
    notes = (
        f"Tagged with ComicTagger {ctversion.version} using info from {final_md.tag_origin.name} on"
        f" {datetime.now():%Y-%m-%d %H:%M:%S}. [Issue ID {final_md.issue_id}]"
    )
    final_md.replace(
        notes=utils.combine_notes(md.notes, notes, "Tagged with ComicTagger"),
        description=cleanup_html(md.description, opts.Sources__remove_html_tables),
    )

    if opts.Issue_Identifier__auto_imprint:
        md.fix_publisher()
    return final_md
