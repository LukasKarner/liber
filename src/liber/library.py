"""Core library management for liber."""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import Optional

from liber.bibtex import (
    get_authors,
    get_doi,
    get_keywords,
    get_title,
    get_year,
    parse_bib_file,
    parse_bibtex,
    rewrite_key,
)
from liber.models import Paper

_INDEX_FILE = ".liber_index.json"

_STOP_WORDS = {
    "a", "an", "the", "of", "in", "on", "at", "to", "for", "with",
    "by", "from", "and", "or", "is", "are", "was", "were", "as", "its",
    "this", "that", "these", "those", "toward", "towards",
}


def make_citation_key(authors: list[str], year: int, title: str) -> str:
    """Generate a citation key in *lastname-year-titleword* format.

    The key consists of:
    - The last name of the first author (lower-case ASCII letters only).
    - The 4-digit publication year.
    - The first non-stop-word from the title (lower-case ASCII letters only).

    Example: ``smith2023machine`` for Smith (2023) "Machine Learning Overview".
    """
    # --- author part ---
    if authors:
        first_author = authors[0].strip()
        # "Last, First" or "First Last"
        if "," in first_author:
            last_name = first_author.split(",")[0].strip()
        else:
            last_name = first_author.split()[-1] if first_author.split() else first_author
    else:
        last_name = "unknown"

    author_part = re.sub(r"[^a-z]", "", last_name.lower())
    if not author_part:
        author_part = "unknown"

    # --- year part ---
    year_part = str(year)

    # --- title part ---
    words = re.sub(r"[^a-z\s]", "", title.lower()).split()
    significant = [w for w in words if w not in _STOP_WORDS]
    title_part = significant[0] if significant else (words[0] if words else "untitled")

    return f"{author_part}{year_part}{title_part}"


class Library:
    """Manages a directory-based academic literature library.

    Directory layout::

        <library_dir>/
        ├── .liber_index.json
        ├── <citation_key>/
        │   ├── <citation_key>.pdf
        │   ├── <citation_key>.bib
        │   └── <citation_key>.md   (optional)
        └── ...
    """

    def __init__(self, library_dir: Path) -> None:
        self.library_dir = Path(library_dir).expanduser().resolve()
        self._index_path = self.library_dir / _INDEX_FILE

    # ------------------------------------------------------------------
    # Initialisation
    # ------------------------------------------------------------------

    def init(self) -> None:
        """Create the library directory and an empty index if needed."""
        self.library_dir.mkdir(parents=True, exist_ok=True)
        if not self._index_path.exists():
            self._write_index([])

    # ------------------------------------------------------------------
    # CRUD operations
    # ------------------------------------------------------------------

    def add(
        self,
        pdf_path: Path,
        bib_path: Path,
        citation_key: Optional[str] = None,
    ) -> Paper:
        """Add a paper to the library from a PDF and a BibTeX file.

        Copies *pdf_path* into the library, writes a ``.bib`` file with the
        citation key updated to the author-year-title format (all other BibTeX
        fields are preserved as-is), and records the paper in the index.

        Args:
            pdf_path: Path to the PDF file to import.
            bib_path: Path to an existing ``.bib`` file for the paper.
            citation_key: Override the auto-generated citation key (optional).

        Returns:
            The newly created :class:`Paper` instance.

        Raises:
            FileNotFoundError: If *pdf_path* or *bib_path* does not exist.
            FileExistsError: If a paper with the same citation key already
                exists in the library.
            ValueError: If required BibTeX fields (title, year, author) are
                missing or malformed.
        """
        pdf_path = Path(pdf_path).expanduser().resolve()
        bib_path = Path(bib_path).expanduser().resolve()
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF not found: {pdf_path}")
        if not bib_path.exists():
            raise FileNotFoundError(f"BibTeX file not found: {bib_path}")

        # Parse the bib file to extract metadata
        fields = parse_bib_file(bib_path)
        title = get_title(fields)
        year = get_year(fields)
        authors = get_authors(fields)
        keywords = get_keywords(fields)
        doi = get_doi(fields)

        key = citation_key or make_citation_key(authors, year, title)

        papers = self._read_index()
        if any(p.citation_key == key for p in papers):
            raise FileExistsError(
                f"A paper with citation key '{key}' already exists in the library."
            )

        paper_dir = self.library_dir / key
        paper_dir.mkdir(parents=True, exist_ok=False)

        # Copy PDF
        dest_pdf = paper_dir / f"{key}.pdf"
        shutil.copy2(pdf_path, dest_pdf)

        # Write bib file: preserve original content, only update the key
        original_bib_text = bib_path.read_text(encoding="utf-8")
        new_bib_text = rewrite_key(original_bib_text, key)
        dest_bib = paper_dir / f"{key}.bib"
        dest_bib.write_text(new_bib_text, encoding="utf-8")

        # Build Paper and update index
        paper = Paper(
            title=title,
            year=year,
            authors=authors,
            keywords=keywords,
            doi=doi,
            citation_key=key,
        )
        papers.append(paper)
        self._write_index(papers)

        return paper

    def remove(self, citation_key: str, *, delete_files: bool = True) -> Paper:
        """Remove a paper from the library.

        Args:
            citation_key: The citation key of the paper to remove.
            delete_files: If ``True`` (default) the paper's sub-directory is
                deleted from disk as well.

        Returns:
            The :class:`Paper` that was removed.

        Raises:
            KeyError: If no paper with *citation_key* is found.
        """
        papers = self._read_index()
        match = next((p for p in papers if p.citation_key == citation_key), None)
        if match is None:
            raise KeyError(f"No paper with citation key '{citation_key}' found.")

        papers = [p for p in papers if p.citation_key != citation_key]
        self._write_index(papers)

        if delete_files:
            paper_dir = self.library_dir / citation_key
            if paper_dir.exists():
                shutil.rmtree(paper_dir)

        return match

    def list_papers(self) -> list[Paper]:
        """Return all papers in the library (sorted by year then title)."""
        papers = self._read_index()
        return sorted(papers, key=lambda p: (p.year, p.title.lower()))

    def get(self, citation_key: str) -> Paper:
        """Return the paper for *citation_key*.

        Raises:
            KeyError: If not found.
        """
        papers = self._read_index()
        match = next((p for p in papers if p.citation_key == citation_key), None)
        if match is None:
            raise KeyError(f"No paper with citation key '{citation_key}' found.")
        return match

    def search(
        self,
        *,
        title: Optional[str] = None,
        author: Optional[str] = None,
        year: Optional[int] = None,
        keyword: Optional[str] = None,
    ) -> list[Paper]:
        """Search papers by one or more criteria (all provided criteria must match).

        All string comparisons are case-insensitive substring matches.
        """
        results = self._read_index()

        if title is not None:
            t = title.lower()
            results = [p for p in results if t in p.title.lower()]

        if author is not None:
            a = author.lower()
            results = [
                p for p in results if any(a in auth.lower() for auth in p.authors)
            ]

        if year is not None:
            results = [p for p in results if p.year == year]

        if keyword is not None:
            kw = keyword.lower()
            results = [
                p for p in results if any(kw in k.lower() for k in p.keywords)
            ]

        return sorted(results, key=lambda p: (p.year, p.title.lower()))

    # ------------------------------------------------------------------
    # Notes
    # ------------------------------------------------------------------

    def rename_key(self, old_key: str, new_key: str) -> Paper:
        """Rename a paper's citation key.

        Renames the paper's directory and all files inside it, updates the
        citation key inside the stored ``.bib`` file, updates the index, and
        returns the updated :class:`Paper`.

        Args:
            old_key: The current citation key.
            new_key: The desired new citation key.

        Raises:
            KeyError: If no paper with *old_key* is found.
            ValueError: If *new_key* is empty or contains invalid characters.
            FileExistsError: If a paper with *new_key* already exists.
        """
        if not new_key or not re.fullmatch(r"[A-Za-z0-9_:.\-]+", new_key):
            raise ValueError(
                f"Invalid citation key {new_key!r}. "
                "Use only letters, digits, underscores, hyphens, colons, or dots."
            )

        papers = self._read_index()
        match = next((p for p in papers if p.citation_key == old_key), None)
        if match is None:
            raise KeyError(f"No paper with citation key '{old_key}' found.")

        if any(p.citation_key == new_key for p in papers):
            raise FileExistsError(
                f"A paper with citation key '{new_key}' already exists in the library."
            )

        old_dir = self.library_dir / old_key
        new_dir = self.library_dir / new_key

        # Rename files inside the directory before renaming the directory itself
        if old_dir.exists():
            for suffix in (".pdf", ".bib", ".md"):
                old_file = old_dir / f"{old_key}{suffix}"
                if old_file.exists():
                    old_file.rename(old_dir / f"{new_key}{suffix}")

            # Update citation key inside the .bib file
            bib_file = old_dir / f"{new_key}.bib"
            if bib_file.exists():
                bib_text = bib_file.read_text(encoding="utf-8")
                bib_file.write_text(rewrite_key(bib_text, new_key), encoding="utf-8")

            old_dir.rename(new_dir)

        # Update index
        match.citation_key = new_key
        self._write_index(papers)

        return match

    def update_bibtex(self, citation_key: str, new_bib_text: str) -> Paper:
        """Replace the stored BibTeX entry for *citation_key*.

        The citation key is always kept as *citation_key* regardless of what
        is written in *new_bib_text*.  Metadata stored in the index (title,
        year, authors, keywords, doi) is re-extracted from *new_bib_text*.

        Args:
            citation_key: Citation key of the paper to update.
            new_bib_text: Full BibTeX entry text (one ``@type{...}`` block).

        Returns:
            The updated :class:`Paper`.

        Raises:
            KeyError: If no paper with *citation_key* is found.
            ValueError: If the BibTeX text is malformed or missing required
                fields (title, year, author).
        """
        papers = self._read_index()
        idx = next(
            (i for i, p in enumerate(papers) if p.citation_key == citation_key), None
        )
        if idx is None:
            raise KeyError(f"No paper with citation key '{citation_key}' found.")

        fields = parse_bibtex(new_bib_text)
        title = get_title(fields)
        year = get_year(fields)
        authors = get_authors(fields)
        keywords = get_keywords(fields)
        doi = get_doi(fields)

        # Write the bib file, preserving the existing citation key
        bib_text_with_key = rewrite_key(new_bib_text, citation_key)
        (self.library_dir / citation_key / f"{citation_key}.bib").write_text(
            bib_text_with_key, encoding="utf-8"
        )

        # Update index entry
        paper = Paper(
            title=title,
            year=year,
            authors=authors,
            keywords=keywords,
            doi=doi,
            citation_key=citation_key,
        )
        papers[idx] = paper
        self._write_index(papers)

        return paper

    def notes_path(self, citation_key: str) -> Path:
        """Return the path to the notes Markdown file for *citation_key*.

        The file is not created by this method; callers may create it as needed.

        Raises:
            KeyError: If no paper with *citation_key* exists in the index.
        """
        self.get(citation_key)  # raises KeyError if not found
        return self.library_dir / citation_key / f"{citation_key}.md"

    def bib_path(self, citation_key: str) -> Path:
        """Return the path to the BibTeX file for *citation_key*.

        The file is not created by this method; callers may create it as needed.

        Raises:
            KeyError: If no paper with *citation_key* exists in the index.
        """
        self.get(citation_key)  # raises KeyError if not found
        return self.library_dir / citation_key / f"{citation_key}.bib"

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _read_index(self) -> list[Paper]:
        if not self._index_path.exists():
            return []
        with self._index_path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        return [Paper.from_dict(entry) for entry in data]

    def _write_index(self, papers: list[Paper]) -> None:
        with self._index_path.open("w", encoding="utf-8") as fh:
            json.dump([p.to_dict() for p in papers], fh, indent=2, ensure_ascii=False)
