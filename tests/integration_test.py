from __future__ import annotations

import settngs

import comicapi.comicarchive
import comicapi.comicinfoxml
import comicapi.genericmetadata
import comictaggerlib.resulttypes
from comictaggerlib import ctsettings
from comictaggerlib.cli import CLI
from comictalker.comictalker import ComicTalker


def test_save(
    plugin_config: tuple[settngs.Config[ctsettings.ct_ns], dict[str, ComicTalker]],
    tmp_comic,
    comicvine_api,
    md_saved,
    mock_now,
) -> None:
    # Overwrite the series so it has definitely changed
    tmp_comic.write_cix(md_saved.replace(series="nothing"))

    md = tmp_comic.read_cix()

    # Check that it changed
    assert md != md_saved

    # Clear the cached metadata
    tmp_comic.reset_cache()

    # Setup the app
    config = plugin_config[0]
    talkers = plugin_config[1]

    # Save
    config[0].Commands__command = comictaggerlib.resulttypes.Action.save

    # Check online, should be intercepted by comicvine_api
    config[0].Runtime_Options__online = True
    # Use the temporary comic we created
    config[0].Runtime_Options__files = [tmp_comic.path]
    # Save ComicRack tags
    config[0].Runtime_Options__type = [comicapi.comicarchive.MetaDataStyle.CIX]
    # Search using the correct series since we just put the wrong series name in the CBZ
    config[0].Runtime_Options__metadata = comicapi.genericmetadata.GenericMetadata(series=md_saved.series)
    # Run ComicTagger
    CLI(config[0], talkers).run()

    # Read the CBZ
    md = tmp_comic.read_cix()

    # Validate that we got the correct metadata back
    assert md == md_saved


def test_delete(
    plugin_config: tuple[settngs.Config[ctsettings.ct_ns], dict[str, ComicTalker]],
    tmp_comic,
    comicvine_api,
    md_saved,
    mock_now,
) -> None:
    md = tmp_comic.read_cix()

    # Check that the metadata starts correct
    assert md == md_saved

    # Clear the cached metadata
    tmp_comic.reset_cache()

    # Setup the app
    config = plugin_config[0]
    talkers = plugin_config[1]

    # Delete
    config[0].Commands__command = comictaggerlib.resulttypes.Action.delete

    # Use the temporary comic we created
    config[0].Runtime_Options__files = [tmp_comic.path]
    # Delete ComicRack tags
    config[0].Runtime_Options__type = [comicapi.comicarchive.MetaDataStyle.CIX]
    # Run ComicTagger
    CLI(config[0], talkers).run()

    # Read the CBZ
    md = tmp_comic.read_cix()

    # Currently we set the default page list on load
    empty_md = comicapi.genericmetadata.GenericMetadata()
    empty_md.set_default_page_list(tmp_comic.get_number_of_pages())

    # Validate that we got an empty metadata back
    assert md == empty_md
