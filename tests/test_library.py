"""Unit tests for liber.library and liber.models."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import pytest

from liber.library import Library, make_citation_key
from liber.models import Paper


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def tmp_lib(tmp_path: Path) -> Library:
    """Return an initialised Library backed by a temporary directory."""
    lib = Library(tmp_path / "mylib")
    lib.init()
    return lib


@pytest.fixture()
def dummy_pdf(tmp_path: Path) -> Path:
    """Return a path to a small dummy PDF file."""
    pdf = tmp_path / "paper.pdf"
    pdf.write_bytes(b"%PDF-1.4 dummy content")
    return pdf


# ---------------------------------------------------------------------------
# make_citation_key
# ---------------------------------------------------------------------------


class TestMakeCitationKey:
    def test_basic(self):
        key = make_citation_key(["Smith, John"], 2023, "Machine Learning Overview")
        assert key == "smith2023machine"

    def test_first_last_format(self):
        key = make_citation_key(["John Smith"], 2023, "Deep Learning")
        assert key == "smith2023deep"

    def test_multiple_authors_uses_first(self):
        key = make_citation_key(
            ["LeCun, Yann", "Bengio, Yoshua"], 2015, "Deep Learning"
        )
        assert key == "lecun2015deep"

    def test_title_skips_stop_words(self):
        key = make_citation_key(["Jones, Alice"], 2020, "A Study of Neural Networks")
        assert key == "jones2020study"

    def test_title_all_stop_words_falls_back(self):
        key = make_citation_key(["Jones, Alice"], 2020, "a the of")
        # Falls back to first word when no significant words remain
        assert key.startswith("jones2020")

    def test_empty_authors(self):
        key = make_citation_key([], 2021, "Quantum Computing")
        assert key == "unknown2021quantum"

    def test_special_chars_stripped(self):
        key = make_citation_key(["Müller, Hans"], 2019, "Über die Natur")
        # Non-ASCII letters are stripped: "Müller" → "mller" (ü removed)
        assert key.startswith("mller2019")

    def test_lowercase_output(self):
        key = make_citation_key(["BROWN, Charlie"], 2022, "Big Data Analytics")
        assert key == key.lower()


# ---------------------------------------------------------------------------
# Paper.to_bibtex
# ---------------------------------------------------------------------------


class TestPaperBibtex:
    def _make_paper(self) -> Paper:
        return Paper(
            title="Deep Learning",
            year=2015,
            authors=["LeCun, Yann", "Bengio, Yoshua", "Hinton, Geoffrey"],
            keywords=["deep learning", "neural networks"],
            doi="10.1038/nature14539",
            citation_key="lecun2015deep",
        )

    def test_bibtex_contains_key(self):
        bib = self._make_paper().to_bibtex()
        assert "@article{lecun2015deep," in bib

    def test_bibtex_contains_title(self):
        bib = self._make_paper().to_bibtex()
        assert "Deep Learning" in bib

    def test_bibtex_contains_authors(self):
        bib = self._make_paper().to_bibtex()
        assert "LeCun, Yann" in bib
        assert "Bengio, Yoshua" in bib

    def test_bibtex_contains_doi(self):
        bib = self._make_paper().to_bibtex()
        assert "10.1038/nature14539" in bib

    def test_bibtex_no_doi_omits_field(self):
        paper = self._make_paper()
        paper.doi = ""
        bib = paper.to_bibtex()
        assert "doi" not in bib

    def test_bibtex_no_keywords_omits_field(self):
        paper = self._make_paper()
        paper.keywords = []
        bib = paper.to_bibtex()
        assert "keywords" not in bib

    def test_roundtrip_dict(self):
        paper = self._make_paper()
        assert Paper.from_dict(paper.to_dict()) == paper


# ---------------------------------------------------------------------------
# Library.add
# ---------------------------------------------------------------------------


class TestLibraryAdd:
    def test_add_creates_directory(self, tmp_lib: Library, dummy_pdf: Path):
        paper = tmp_lib.add(
            pdf_path=dummy_pdf,
            title="Machine Learning",
            year=2023,
            authors=["Smith, John"],
            keywords=["ml"],
            doi="",
        )
        assert (tmp_lib.library_dir / paper.citation_key).is_dir()

    def test_add_creates_pdf(self, tmp_lib: Library, dummy_pdf: Path):
        paper = tmp_lib.add(
            pdf_path=dummy_pdf,
            title="Machine Learning",
            year=2023,
            authors=["Smith, John"],
            keywords=[],
        )
        assert (tmp_lib.library_dir / paper.citation_key / f"{paper.citation_key}.pdf").exists()

    def test_add_creates_bib(self, tmp_lib: Library, dummy_pdf: Path):
        paper = tmp_lib.add(
            pdf_path=dummy_pdf,
            title="Machine Learning",
            year=2023,
            authors=["Smith, John"],
            keywords=[],
        )
        bib_path = tmp_lib.library_dir / paper.citation_key / f"{paper.citation_key}.bib"
        assert bib_path.exists()
        assert paper.citation_key in bib_path.read_text()

    def test_add_records_in_index(self, tmp_lib: Library, dummy_pdf: Path):
        tmp_lib.add(
            pdf_path=dummy_pdf,
            title="Neural Networks",
            year=2020,
            authors=["Doe, Jane"],
            keywords=[],
        )
        papers = tmp_lib.list_papers()
        assert len(papers) == 1
        assert papers[0].title == "Neural Networks"

    def test_add_duplicate_key_raises(self, tmp_lib: Library, dummy_pdf: Path):
        tmp_lib.add(
            pdf_path=dummy_pdf,
            title="Neural Networks",
            year=2020,
            authors=["Doe, Jane"],
            keywords=[],
        )
        dummy_pdf2 = dummy_pdf.parent / "paper2.pdf"
        dummy_pdf2.write_bytes(b"%PDF-1.4 second")
        with pytest.raises(FileExistsError):
            tmp_lib.add(
                pdf_path=dummy_pdf2,
                title="Neural Networks",
                year=2020,
                authors=["Doe, Jane"],
                keywords=[],
            )

    def test_add_missing_pdf_raises(self, tmp_lib: Library):
        with pytest.raises(FileNotFoundError):
            tmp_lib.add(
                pdf_path=Path("/nonexistent/paper.pdf"),
                title="Test",
                year=2021,
                authors=["Author, A"],
                keywords=[],
            )

    def test_add_custom_key(self, tmp_lib: Library, dummy_pdf: Path):
        paper = tmp_lib.add(
            pdf_path=dummy_pdf,
            title="Custom Key Paper",
            year=2022,
            authors=["Author, A"],
            keywords=[],
            citation_key="mykey2022custom",
        )
        assert paper.citation_key == "mykey2022custom"


# ---------------------------------------------------------------------------
# Library.remove
# ---------------------------------------------------------------------------


class TestLibraryRemove:
    def test_remove_deletes_directory(self, tmp_lib: Library, dummy_pdf: Path):
        paper = tmp_lib.add(
            pdf_path=dummy_pdf,
            title="To Remove",
            year=2021,
            authors=["Author, A"],
            keywords=[],
        )
        key = paper.citation_key
        tmp_lib.remove(key)
        assert not (tmp_lib.library_dir / key).exists()

    def test_remove_updates_index(self, tmp_lib: Library, dummy_pdf: Path):
        paper = tmp_lib.add(
            pdf_path=dummy_pdf,
            title="To Remove",
            year=2021,
            authors=["Author, A"],
            keywords=[],
        )
        tmp_lib.remove(paper.citation_key)
        assert tmp_lib.list_papers() == []

    def test_remove_keep_files(self, tmp_lib: Library, dummy_pdf: Path):
        paper = tmp_lib.add(
            pdf_path=dummy_pdf,
            title="Keep Files",
            year=2021,
            authors=["Author, A"],
            keywords=[],
        )
        key = paper.citation_key
        tmp_lib.remove(key, delete_files=False)
        assert (tmp_lib.library_dir / key).exists()  # files remain
        assert tmp_lib.list_papers() == []  # but index is updated

    def test_remove_nonexistent_raises(self, tmp_lib: Library):
        with pytest.raises(KeyError):
            tmp_lib.remove("nonexistent2000key")


# ---------------------------------------------------------------------------
# Library.search
# ---------------------------------------------------------------------------


class TestLibrarySearch:
    def _populate(self, lib: Library, tmp_path: Path) -> None:
        for i, (title, year, authors, keywords) in enumerate(
            [
                ("Deep Learning", 2015, ["LeCun, Yann", "Bengio, Yoshua"], ["deep learning", "neural networks"]),
                ("Attention Is All You Need", 2017, ["Vaswani, Ashish"], ["transformers", "attention"]),
                ("BERT", 2019, ["Devlin, Jacob"], ["nlp", "transformers"]),
                ("Reinforcement Learning", 2020, ["Sutton, Richard"], ["rl", "rewards"]),
            ]
        ):
            pdf = tmp_path / f"paper{i}.pdf"
            pdf.write_bytes(b"%PDF")
            lib.add(pdf_path=pdf, title=title, year=year, authors=authors, keywords=keywords)

    def test_search_by_author(self, tmp_lib: Library, tmp_path: Path):
        self._populate(tmp_lib, tmp_path)
        results = tmp_lib.search(author="Vaswani")
        assert len(results) == 1
        assert results[0].title == "Attention Is All You Need"

    def test_search_by_year(self, tmp_lib: Library, tmp_path: Path):
        self._populate(tmp_lib, tmp_path)
        results = tmp_lib.search(year=2019)
        assert len(results) == 1
        assert results[0].title == "BERT"

    def test_search_by_keyword(self, tmp_lib: Library, tmp_path: Path):
        self._populate(tmp_lib, tmp_path)
        results = tmp_lib.search(keyword="transformers")
        assert len(results) == 2

    def test_search_by_title(self, tmp_lib: Library, tmp_path: Path):
        self._populate(tmp_lib, tmp_path)
        results = tmp_lib.search(title="learning")
        assert len(results) == 2  # "Deep Learning" and "Reinforcement Learning"

    def test_search_combined(self, tmp_lib: Library, tmp_path: Path):
        self._populate(tmp_lib, tmp_path)
        results = tmp_lib.search(keyword="transformers", year=2017)
        assert len(results) == 1
        assert results[0].title == "Attention Is All You Need"

    def test_search_no_results(self, tmp_lib: Library, tmp_path: Path):
        self._populate(tmp_lib, tmp_path)
        results = tmp_lib.search(author="Turing")
        assert results == []


# ---------------------------------------------------------------------------
# Library.notes_path
# ---------------------------------------------------------------------------


class TestLibraryNotesPath:
    def test_notes_path_correct(self, tmp_lib: Library, dummy_pdf: Path):
        paper = tmp_lib.add(
            pdf_path=dummy_pdf,
            title="Test Notes",
            year=2022,
            authors=["Author, A"],
            keywords=[],
        )
        notes = tmp_lib.notes_path(paper.citation_key)
        assert notes == tmp_lib.library_dir / paper.citation_key / f"{paper.citation_key}.md"

    def test_notes_path_nonexistent_raises(self, tmp_lib: Library):
        with pytest.raises(KeyError):
            tmp_lib.notes_path("ghost2000key")
