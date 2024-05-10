from __future__ import annotations

import settngs

import comicapi.comicarchive
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
    tmp_comic.write_metadata(md_saved.replace(series="nothing"), "cr")

    md = tmp_comic.read_metadata("cr")

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
    # Read and save ComicRack tags
    config[0].Runtime_Options__type_read = ["cr"]
    config[0].Runtime_Options__type_modify = ["cr"]
    # Search using the correct series since we just put the wrong series name in the CBZ
    config[0].Runtime_Options__metadata = comicapi.genericmetadata.GenericMetadata(series=md_saved.series)
    # Run ComicTagger
    CLI(config[0], talkers).run()

    # Read the CBZ
    md = tmp_comic.read_metadata("cr")

    # This is inserted here because otherwise several other tests
    # unrelated to comicvine need to be re-worked
    md_saved.credits.insert(
        1,
        comicapi.genericmetadata.Credit(
            person="Esteve Polls",
            primary=False,
            role="Writer",
        ),
    )

    # Validate that we got the correct metadata back
    assert md == md_saved


def test_delete(
    plugin_config: tuple[settngs.Config[ctsettings.ct_ns], dict[str, ComicTalker]],
    tmp_comic,
    comicvine_api,
    md_saved,
    mock_now,
) -> None:
    md = tmp_comic.read_metadata("cr")

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
    config[0].Runtime_Options__type_modify = ["cr"]
    # Run ComicTagger
    CLI(config[0], talkers).run()

    # Read the CBZ
    md = tmp_comic.read_metadata("cr")

    # The default page list is set on load if the comic has the requested metadata style
    empty_md = comicapi.genericmetadata.GenericMetadata()

    # Validate that we got an empty metadata back
    assert md == empty_md


def test_rename(
    plugin_config: tuple[settngs.Config[ctsettings.ct_ns], dict[str, ComicTalker]],
    tmp_comic,
    comicvine_api,
    md_saved,
    mock_now,
) -> None:
    md = tmp_comic.read_metadata("cr")

    # Check that the metadata starts correct
    assert md == md_saved

    # Clear the cached metadata
    tmp_comic.reset_cache()

    # Setup the app
    config = plugin_config[0]
    talkers = plugin_config[1]

    # Delete
    config[0].Commands__command = comictaggerlib.resulttypes.Action.rename

    # Use the temporary comic we created
    config[0].Runtime_Options__files = [tmp_comic.path]

    # Set the template
    config[0].File_Rename__template = "{series}"
    # Use the current directory
    config[0].File_Rename__dir = ""
    # Run ComicTagger
    CLI(config[0], talkers).run()

    # Update the comic path
    tmp_comic.path = tmp_comic.path.parent / (md.series + ".cbz")

    # Read the CBZ
    md = tmp_comic.read_metadata("cr")

    # Validate that we got the correct metadata back
    assert md == md_saved
