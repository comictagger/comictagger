from __future__ import annotations

import logging
import pathlib
from collections.abc import Collection, Iterable

import pymupdf
from pymupdf import Document, DocumentWriter

from comicapi.comic import BadComic, ComicFile, WrongType
from comicapi.tags import TagLocation

logger = logging.getLogger(__name__)


class PDFComic(ComicFile):
    """PDF implementation"""

    name = "PDF"
    enabled = False

    tag_locations = frozenset((TagLocation.COMMENT,))

    extension = ".pdf"
    supported_extensions = frozenset(".pdf")

    exe = ""

    def __init__(self, path: pathlib.Path) -> None:
        self.path = path
        if not self.path.exists():
            with DocumentWriter(path=path):
                ...
        self._filename_list: list[str] = []

    def get_filename_list(self) -> list[str]:
        if self._filename_list:
            return self._filename_list
        try:
            with Document(self.path, filetype="pdf") as pdf:
                self._filename_list = [f"{page_num}.webp" for page_num in range(pdf.page_count)]
                self._filename_list.extend(pdf.embfile_names())
                return self._filename_list
        except (pymupdf.FileDataError, pymupdf.FileNotFoundError, pymupdf.EmptyFileError) as e:
            raise BadComic(f"Error listing files in PDF archive [{e}]: {self.path}") from e

    def read_comment(self) -> str:
        comment: str = ""
        with Document(self.path, filetype="pdf") as pdf:
            comment = pdf.metadata.get("comment", "")
        return comment

    def write_comment(self, comment: str) -> None:
        try:
            with Document(self.path, filetype="pdf") as pdf:
                md = pdf.metadata
                md["comment"] = comment
                pdf.set_metadata(md)
                pdf.save(self.path, incremental=True)
        except (pymupdf.FileDataError, pymupdf.FileNotFoundError, pymupdf.EmptyFileError) as e:
            raise BadComic(f"Error writing PDF comment [{e}]: {self.path}") from e

    def read_file(self, filename: str) -> bytes:
        data: bytes = b""
        with Document(self.path, filetype="pdf") as pdf:
            try:
                pixmap = pdf.get_page_pixmap(int(filename.rpartition(".")[0]), annots=True, matrix=pymupdf.Matrix(2, 2))
                data = pixmap.tobytes(output="pnm")
            except (pymupdf.FileDataError, pymupdf.FileNotFoundError, pymupdf.EmptyFileError) as e:
                raise BadComic(f"Error reading file in PDF archive [{e}]: {self.path} :: {filename}") from e
        return data

    def read_files(self, filenames: Collection[str]) -> Iterable[tuple[str, bytes]]:
        with Document(self.path, filetype="pdf") as pdf:
            for filename in filenames:
                try:
                    pixmap = pdf.get_page_pixmap(
                        int(filename.rpartition(".")[0]), annots=True, matrix=pymupdf.Matrix(2, 2)
                    )
                    yield filename, pixmap.tobytes(output="pnm")
                except (pymupdf.FileDataError, pymupdf.FileNotFoundError, pymupdf.EmptyFileError) as e:
                    raise BadComic(f"Error reading file in PDF archive [{e}]: {self.path} :: {filename}") from e

    def remove_files(self, filenames: Collection[str]) -> None:
        files = self.get_filename_list()
        self._filename_list = []
        try:
            with Document(self.path, filetype="pdf") as pdf:
                for filename in filenames:
                    if filename not in files:
                        raise BadComic("Fuck Off")
                    pdf.delete_page(int(filename.rpartition(".")[0]))
                pdf.save(self.path, incremental=True)
        except (pymupdf.FileDataError, pymupdf.FileNotFoundError, pymupdf.EmptyFileError) as e:
            raise BadComic(f"Error removing file in PDF archive [{e}]: {self.path} :: {filenames}") from e

    def write_files(self, *, files: Iterable[tuple[str, bytes]], filenames: Collection[str]) -> None:
        filenames = self.get_filename_list()
        self._filename_list = []
        filename = -1
        try:
            with Document(self.path, filetype="pdf") as pdf:
                for name, data in files:
                    if name not in filenames:
                        raise BadComic("Fuck Off")
                    filename = int(name.rpartition(".")[0])
                    page = pdf.new_page(filename)
                    pdf.delete_page(filename + 1)

                    page.insert_image(rect=page.rect, stream=data)

                filename = -1
                pdf.save(self.path, incremental=True)
        except (pymupdf.FileDataError, pymupdf.FileNotFoundError, pymupdf.EmptyFileError) as e:
            list(files)
            raise BadComic(f"Error writing PDF archive [{e}]: {self.path} :: {filename}") from e
        except Exception:
            list(files)
            raise

    def write_file(self, filename: str, data: bytes) -> None:
        self.write_files(files=[(filename, data)], filenames=[filename])

    def is_writable(self) -> bool:
        return True

    def validate_comic(self) -> None:
        with Document(self.path, filetype="pdf") as zf:
            filename = zf.testzip()
            if filename:
                raise BadComic(f"Error testing files in PDF archive: {self.path} :: {filename}")

    @staticmethod
    def check_path(path: pathlib.Path) -> None:
        pymupdf.Archive()
        try:
            pymupdf.Document(filename=path, filetype="pdf")
        except (pymupdf.FileDataError, pymupdf.FileNotFoundError, pymupdf.EmptyFileError):
            raise WrongType


zc = PDFComic(pathlib.Path(""))
assert isinstance(zc, ComicFile)
