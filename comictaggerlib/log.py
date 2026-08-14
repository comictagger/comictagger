from __future__ import annotations

import logging.handlers
import pathlib
import platform
import sys

from comictaggerlib.ctversion import version

logger = logging.getLogger("comictagger")


def get_filename(filename: str) -> str:
    filename, _, number = filename.rpartition(".")
    return filename.removesuffix("log") + number + ".log"


def get_file_handler(filename: pathlib.Path) -> logging.FileHandler:
    file_handler = logging.handlers.RotatingFileHandler(filename, encoding="utf-8", backupCount=10)
    file_handler.namer = get_filename

    if filename.is_file() and filename.stat().st_size > 0:
        file_handler.doRollover()
    return file_handler


def setup_logging(verbose: int, log_dir: pathlib.Path) -> None:
    logging.getLogger("comicapi").setLevel(logging.DEBUG)
    logging.getLogger("comictaggerlib").setLevel(logging.DEBUG)
    logging.getLogger("comictalker").setLevel(logging.DEBUG)

    log_file = log_dir / "ComicTagger.log"
    log_dir.mkdir(parents=True, exist_ok=True)

    stream_handler = logging.StreamHandler()
    file_handler = get_file_handler(log_file)

    if verbose > 1:
        stream_handler.setLevel(logging.DEBUG)
    elif verbose > 0:
        stream_handler.setLevel(logging.INFO)
    else:
        stream_handler.setLevel(logging.WARNING)

    logging.basicConfig(
        handlers=[stream_handler, file_handler],
        level=logging.WARNING,
        format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )

    logger.info(
        "ComicTagger Version: %s running on: %s PyInstaller: %s",
        version,
        platform.system(),
        "Yes" if getattr(sys, "frozen", None) else "No",
    )
