from __future__ import annotations

import settngs

import comicapi.comicarchive
import comicapi.genericmetadata
import comictaggerlib.ctversion
import comictaggerlib.resulttypes
from comicapi.tags.comicrack import ComicRack
from comictaggerlib import ctsettings
from comictaggerlib.cli import CLI
from comictalker.comictalker import ComicTalker


def test_save(
    plugin_config: tuple[settngs.Config[ctsettings.ct_ns], dict[str, ComicTalker]],
    tmp_comic_path,
    md_saved,
    mock_now,
) -> None:
    tmp_comic = comicapi.comicarchive.ComicArchive(tmp_comic_path)
    # Overwrite the series so it has definitely changed
    tmp_comic.write_tags(comictaggerlib.ctversion.version, md_saved.replace(series="nothing"), ComicRack())

    md = tmp_comic.read_tags(ComicRack())

    # Check that it changed
    assert md != md_saved

    # Setup the app
    config = plugin_config[0]
    talkers = plugin_config[1]

    # Save
    config[0].Commands__command = comictaggerlib.resulttypes.Action.save

    # Check online, should be intercepted by comicvine_api
    config[0].Auto_Tag__online = True
    # Use the temporary comic we created
    config[0].Runtime_Options__files = [tmp_comic_path]
    # Read and save ComicRack tags
    config[0].Runtime_Options__tags_read = [ComicRack]
    config[0].Runtime_Options__tags_write = [ComicRack]
    # Search using the correct series since we just put the wrong series name in the CBZ
    config[0].Auto_Tag__metadata = comicapi.genericmetadata.GenericMetadata(series=md_saved.series)
    # Run ComicTagger
    assert CLI(config[0], talkers).run() == 0

    # tmp_comic is invalid it can't handle outside changes so we need a new one
    tmp_comic = comicapi.comicarchive.ComicArchive(tmp_comic_path)

    # Read the CBZ
    md = tmp_comic.read_tags(ComicRack)

    # This is inserted here because otherwise several other tests
    # unrelated to comicvine need to be re-worked
    # the comicvine response is mocked to 1 for caching tests and adding the remaining 5 issues is more work
    md_saved.issue_count = 1
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
    tmp_comic_path,
    md_saved,
    mock_now,
) -> None:
    tmp_comic = comicapi.comicarchive.ComicArchive(tmp_comic_path)
    md = tmp_comic.read_tags(ComicRack)

    # Check that the metadata starts correct
    assert md == md_saved

    # Setup the app
    config = plugin_config[0]
    talkers = plugin_config[1]

    # Delete
    config[0].Commands__command = comictaggerlib.resulttypes.Action.delete

    # Use the temporary comic we created
    config[0].Runtime_Options__files = [tmp_comic_path]
    # Delete ComicRack tags
    config[0].Runtime_Options__tags_write = [ComicRack]
    # Run ComicTagger
    assert CLI(config[0], talkers).run() == 0

    # tmp_comic is invalid it can't handle outside changes so we need a new one
    tmp_comic = comicapi.comicarchive.ComicArchive(tmp_comic_path)

    # Read the CBZ
    md = tmp_comic.read_tags(ComicRack)

    # The default page list is set on load if the comic has the requested tags
    empty_md = comicapi.genericmetadata.GenericMetadata()

    # Validate that we got an empty metadata back
    assert md == empty_md


def test_rename(
    plugin_config: tuple[settngs.Config[ctsettings.ct_ns], dict[str, ComicTalker]],
    tmp_comic_path,
    md_saved,
    mock_now,
) -> None:
    tmp_comic = comicapi.comicarchive.ComicArchive(tmp_comic_path)
    md = tmp_comic.read_tags(ComicRack)

    # Check that the metadata starts correct
    assert md == md_saved

    # Setup the app
    config = plugin_config[0]
    talkers = plugin_config[1]

    # rename
    config[0].Commands__command = comictaggerlib.resulttypes.Action.rename

    # Use the temporary comic we created
    config[0].Runtime_Options__files = [tmp_comic_path]
    # Read ComicRack tags
    config[0].Runtime_Options__tags_read = [ComicRack]

    # Set the template
    config[0].File_Rename__template = "{series}"
    # Use the current directory
    config[0].File_Rename__dir = ""
    # Run ComicTagger
    assert CLI(config[0], talkers).run() == 0

    # tmp_comic is invalid it can't handle outside changes so we need a new one
    tmp_comic = comicapi.comicarchive.ComicArchive(tmp_comic.path.parent / ((md.series or "comic") + ".cbz"))

    # Read the CBZ
    md = tmp_comic.read_tags(ComicRack)

    # Validate that we got the correct metadata back
    assert md == md_saved
