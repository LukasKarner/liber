"""Unit tests for liber.library and liber.models."""

from __future__ import annotations

from pathlib import Path

import pytest

from liber.library import Library, make_citation_key
from liber.models import Paper
from tests.conftest import make_bib


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
def dummy_bib(tmp_path: Path) -> Path:
    """Return a path to a minimal BibTeX file."""
    bib = tmp_path / "paper.bib"
    bib.write_text(
        "@article{oldkey2015,\n"
        "  title    = {Machine Learning},\n"
        "  author   = {Smith, John},\n"
        "  year     = {2023},\n"
        "  keywords = {ml, artificial intelligence},\n"
        "  doi      = {10.1/ml},\n"
        "}\n",
        encoding="utf-8",
    )
    return bib


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
    def test_add_creates_directory(self, tmp_lib: Library, dummy_pdf: Path, dummy_bib: Path):
        paper = tmp_lib.add(bib_path=dummy_bib, pdf_path=dummy_pdf)
        assert (tmp_lib.library_dir / paper.citation_key).is_dir()

    def test_add_creates_pdf(self, tmp_lib: Library, dummy_pdf: Path, dummy_bib: Path):
        paper = tmp_lib.add(bib_path=dummy_bib, pdf_path=dummy_pdf)
        assert (tmp_lib.library_dir / paper.citation_key / f"{paper.citation_key}.pdf").exists()

    def test_add_creates_bib(self, tmp_lib: Library, dummy_pdf: Path, dummy_bib: Path):
        paper = tmp_lib.add(bib_path=dummy_bib, pdf_path=dummy_pdf)
        bib_path = tmp_lib.library_dir / paper.citation_key / f"{paper.citation_key}.bib"
        assert bib_path.exists()
        assert paper.citation_key in bib_path.read_text()

    def test_add_bib_preserves_original_content(self, tmp_lib: Library, dummy_pdf: Path, dummy_bib: Path):
        """Original BibTeX fields must be preserved; only the key changes."""
        paper = tmp_lib.add(bib_path=dummy_bib, pdf_path=dummy_pdf)
        bib_text = (
            tmp_lib.library_dir / paper.citation_key / f"{paper.citation_key}.bib"
        ).read_text()
        # Original field values must still be present
        assert "Machine Learning" in bib_text
        assert "Smith, John" in bib_text
        assert "10.1/ml" in bib_text
        # Old key must be gone; new key must be present
        assert "oldkey2015" not in bib_text
        assert paper.citation_key in bib_text

    def test_add_records_in_index(self, tmp_lib: Library, dummy_pdf: Path, dummy_bib: Path):
        tmp_lib.add(bib_path=dummy_bib, pdf_path=dummy_pdf)
        papers = tmp_lib.list_papers()
        assert len(papers) == 1
        assert papers[0].title == "Machine Learning"

    def test_add_extracts_metadata(self, tmp_lib: Library, dummy_pdf: Path, dummy_bib: Path):
        paper = tmp_lib.add(bib_path=dummy_bib, pdf_path=dummy_pdf)
        assert paper.title == "Machine Learning"
        assert paper.year == 2023
        assert paper.authors == ["Smith, John"]
        assert "ml" in paper.keywords
        assert paper.doi == "10.1/ml"

    def test_add_handles_missing_doi(self, tmp_lib: Library, tmp_path: Path, dummy_pdf: Path):
        bib = make_bib(tmp_path, "nodoi.bib", "No DOI Paper", 2021, ["Author, A"], ["test"])
        paper = tmp_lib.add(bib_path=bib, pdf_path=dummy_pdf)
        assert paper.doi == ""

    def test_add_handles_no_keywords(self, tmp_lib: Library, tmp_path: Path, dummy_pdf: Path):
        bib = make_bib(tmp_path, "nokw.bib", "No Keywords Paper", 2021, ["Author, A"], [])
        paper = tmp_lib.add(bib_path=bib, pdf_path=dummy_pdf)
        assert paper.keywords == []

    def test_add_without_pdf(self, tmp_lib: Library, dummy_bib: Path):
        """Adding a paper without a PDF should succeed; no .pdf file is created."""
        paper = tmp_lib.add(bib_path=dummy_bib)
        assert (tmp_lib.library_dir / paper.citation_key).is_dir()
        assert not (tmp_lib.library_dir / paper.citation_key / f"{paper.citation_key}.pdf").exists()
        assert (tmp_lib.library_dir / paper.citation_key / f"{paper.citation_key}.bib").exists()

    def test_add_duplicate_key_raises(self, tmp_lib: Library, dummy_pdf: Path, dummy_bib: Path):
        tmp_lib.add(bib_path=dummy_bib, pdf_path=dummy_pdf)
        dummy_pdf2 = dummy_pdf.parent / "paper2.pdf"
        dummy_pdf2.write_bytes(b"%PDF-1.4 second")
        with pytest.raises(FileExistsError):
            tmp_lib.add(bib_path=dummy_bib, pdf_path=dummy_pdf2)

    def test_add_missing_pdf_raises(self, tmp_lib: Library, dummy_bib: Path):
        with pytest.raises(FileNotFoundError):
            tmp_lib.add(bib_path=dummy_bib, pdf_path=Path("/nonexistent/paper.pdf"))

    def test_add_missing_bib_raises(self, tmp_lib: Library, dummy_pdf: Path):
        with pytest.raises(FileNotFoundError):
            tmp_lib.add(bib_path=Path("/nonexistent/paper.bib"), pdf_path=dummy_pdf)

    def test_add_custom_key(self, tmp_lib: Library, dummy_pdf: Path, dummy_bib: Path):
        paper = tmp_lib.add(
            bib_path=dummy_bib, pdf_path=dummy_pdf, citation_key="mykey2022custom"
        )
        assert paper.citation_key == "mykey2022custom"


# ---------------------------------------------------------------------------
# Library.remove
# ---------------------------------------------------------------------------


class TestLibraryRemove:
    def test_remove_deletes_directory(self, tmp_lib: Library, dummy_pdf: Path, dummy_bib: Path):
        paper = tmp_lib.add(pdf_path=dummy_pdf, bib_path=dummy_bib)
        key = paper.citation_key
        tmp_lib.remove(key)
        assert not (tmp_lib.library_dir / key).exists()

    def test_remove_updates_index(self, tmp_lib: Library, dummy_pdf: Path, dummy_bib: Path):
        paper = tmp_lib.add(pdf_path=dummy_pdf, bib_path=dummy_bib)
        tmp_lib.remove(paper.citation_key)
        assert tmp_lib.list_papers() == []

    def test_remove_keep_files(self, tmp_lib: Library, dummy_pdf: Path, dummy_bib: Path):
        paper = tmp_lib.add(pdf_path=dummy_pdf, bib_path=dummy_bib)
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
            bib = make_bib(tmp_path, f"paper{i}.bib", title, year, authors, keywords)
            lib.add(bib_path=bib, pdf_path=pdf)

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
    def test_notes_path_correct(self, tmp_lib: Library, dummy_pdf: Path, dummy_bib: Path):
        paper = tmp_lib.add(bib_path=dummy_bib, pdf_path=dummy_pdf)
        notes = tmp_lib.notes_path(paper.citation_key)
        assert notes == tmp_lib.library_dir / paper.citation_key / f"{paper.citation_key}.md"

    def test_notes_path_nonexistent_raises(self, tmp_lib: Library):
        with pytest.raises(KeyError):
            tmp_lib.notes_path("ghost2000key")


# ---------------------------------------------------------------------------
# Library.pdf_path / Library.add_pdf
# ---------------------------------------------------------------------------


class TestLibraryPdfPath:
    def test_pdf_path_correct(self, tmp_lib: Library, dummy_bib: Path):
        paper = tmp_lib.add(bib_path=dummy_bib)
        assert tmp_lib.pdf_path(paper.citation_key) == (
            tmp_lib.library_dir / paper.citation_key / f"{paper.citation_key}.pdf"
        )

    def test_pdf_path_nonexistent_raises(self, tmp_lib: Library):
        with pytest.raises(KeyError):
            tmp_lib.pdf_path("ghost2000key")


class TestLibraryAddPdf:
    def test_add_pdf_creates_file(self, tmp_lib: Library, dummy_pdf: Path, dummy_bib: Path):
        paper = tmp_lib.add(bib_path=dummy_bib)
        assert not tmp_lib.pdf_path(paper.citation_key).exists()
        tmp_lib.add_pdf(paper.citation_key, dummy_pdf)
        assert tmp_lib.pdf_path(paper.citation_key).exists()

    def test_add_pdf_replaces_existing(self, tmp_lib: Library, dummy_pdf: Path, dummy_bib: Path, tmp_path: Path):
        paper = tmp_lib.add(bib_path=dummy_bib, pdf_path=dummy_pdf)
        new_pdf = tmp_path / "new.pdf"
        new_pdf.write_bytes(b"%PDF-1.4 replacement")
        tmp_lib.add_pdf(paper.citation_key, new_pdf)
        content = tmp_lib.pdf_path(paper.citation_key).read_bytes()
        assert content == b"%PDF-1.4 replacement"

    def test_add_pdf_missing_file_raises(self, tmp_lib: Library, dummy_bib: Path):
        paper = tmp_lib.add(bib_path=dummy_bib)
        with pytest.raises(FileNotFoundError):
            tmp_lib.add_pdf(paper.citation_key, Path("/nonexistent/paper.pdf"))

    def test_add_pdf_nonexistent_key_raises(self, tmp_lib: Library, dummy_pdf: Path):
        with pytest.raises(KeyError):
            tmp_lib.add_pdf("ghost2000key", dummy_pdf)


# ---------------------------------------------------------------------------
# Library.rename_key
# ---------------------------------------------------------------------------


class TestLibraryRenameKey:
    def test_rename_updates_index(self, tmp_lib: Library, dummy_pdf: Path, dummy_bib: Path):
        paper = tmp_lib.add(bib_path=dummy_bib, pdf_path=dummy_pdf)
        old_key = paper.citation_key
        renamed = tmp_lib.rename_key(old_key, "newkey2099test")
        assert renamed.citation_key == "newkey2099test"
        papers = tmp_lib.list_papers()
        assert len(papers) == 1
        assert papers[0].citation_key == "newkey2099test"
        assert not any(p.citation_key == old_key for p in papers)

    def test_rename_moves_directory(self, tmp_lib: Library, dummy_pdf: Path, dummy_bib: Path):
        paper = tmp_lib.add(bib_path=dummy_bib, pdf_path=dummy_pdf)
        old_key = paper.citation_key
        tmp_lib.rename_key(old_key, "newkey2099test")
        assert not (tmp_lib.library_dir / old_key).exists()
        assert (tmp_lib.library_dir / "newkey2099test").is_dir()

    def test_rename_renames_files(self, tmp_lib: Library, dummy_pdf: Path, dummy_bib: Path):
        paper = tmp_lib.add(bib_path=dummy_bib, pdf_path=dummy_pdf)
        tmp_lib.rename_key(paper.citation_key, "newkey2099test")
        new_dir = tmp_lib.library_dir / "newkey2099test"
        assert (new_dir / "newkey2099test.pdf").exists()
        assert (new_dir / "newkey2099test.bib").exists()

    def test_rename_updates_bib_file_content(self, tmp_lib: Library, dummy_pdf: Path, dummy_bib: Path):
        paper = tmp_lib.add(bib_path=dummy_bib, pdf_path=dummy_pdf)
        old_key = paper.citation_key
        tmp_lib.rename_key(old_key, "newkey2099test")
        bib_text = (tmp_lib.library_dir / "newkey2099test" / "newkey2099test.bib").read_text()
        assert "newkey2099test" in bib_text
        assert old_key not in bib_text

    def test_rename_also_renames_notes(self, tmp_lib: Library, dummy_pdf: Path, dummy_bib: Path):
        paper = tmp_lib.add(bib_path=dummy_bib, pdf_path=dummy_pdf)
        old_key = paper.citation_key
        notes = tmp_lib.notes_path(old_key)
        notes.write_text("# Notes\n", encoding="utf-8")
        tmp_lib.rename_key(old_key, "newkey2099test")
        assert (tmp_lib.library_dir / "newkey2099test" / "newkey2099test.md").exists()

    def test_rename_nonexistent_raises(self, tmp_lib: Library):
        with pytest.raises(KeyError):
            tmp_lib.rename_key("ghost2000key", "newkey2099test")

    def test_rename_duplicate_target_raises(self, tmp_lib: Library, dummy_pdf: Path, dummy_bib: Path, tmp_path: Path):
        from tests.conftest import make_bib as _make_bib
        paper = tmp_lib.add(bib_path=dummy_bib, pdf_path=dummy_pdf)
        pdf2 = tmp_path / "paper2.pdf"
        pdf2.write_bytes(b"%PDF second")
        bib2 = _make_bib(tmp_path, "b2.bib", "Another Paper", 2024, ["Other, A"], [])
        paper2 = tmp_lib.add(bib_path=bib2, pdf_path=pdf2)
        with pytest.raises(FileExistsError):
            tmp_lib.rename_key(paper.citation_key, paper2.citation_key)

    def test_rename_invalid_key_raises(self, tmp_lib: Library, dummy_pdf: Path, dummy_bib: Path):
        paper = tmp_lib.add(bib_path=dummy_bib, pdf_path=dummy_pdf)
        with pytest.raises(ValueError):
            tmp_lib.rename_key(paper.citation_key, "invalid key!")

    def test_rename_empty_key_raises(self, tmp_lib: Library, dummy_pdf: Path, dummy_bib: Path):
        paper = tmp_lib.add(bib_path=dummy_bib, pdf_path=dummy_pdf)
        with pytest.raises(ValueError):
            tmp_lib.rename_key(paper.citation_key, "")


# ---------------------------------------------------------------------------
# Library.update_bibtex
# ---------------------------------------------------------------------------


class TestLibraryUpdateBibtex:
    def test_update_bibtex_updates_index(self, tmp_lib: Library, dummy_pdf: Path, dummy_bib: Path):
        paper = tmp_lib.add(bib_path=dummy_bib, pdf_path=dummy_pdf)
        new_bib = (
            f"@article{{{paper.citation_key},\n"
            "  title  = {Updated Title},\n"
            "  author = {Doe, Jane},\n"
            "  year   = {2024},\n"
            "}\n"
        )
        updated = tmp_lib.update_bibtex(paper.citation_key, new_bib)
        assert updated.title == "Updated Title"
        assert updated.year == 2024
        assert updated.authors == ["Doe, Jane"]
        assert updated.citation_key == paper.citation_key  # key unchanged

    def test_update_bibtex_writes_file(self, tmp_lib: Library, dummy_pdf: Path, dummy_bib: Path):
        paper = tmp_lib.add(bib_path=dummy_bib, pdf_path=dummy_pdf)
        new_bib = (
            f"@article{{differentkey,\n"
            "  title  = {New Title},\n"
            "  author = {Doe, Jane},\n"
            "  year   = {2024},\n"
            "}\n"
        )
        tmp_lib.update_bibtex(paper.citation_key, new_bib)
        bib_text = (
            tmp_lib.library_dir / paper.citation_key / f"{paper.citation_key}.bib"
        ).read_text()
        assert paper.citation_key in bib_text
        assert "differentkey" not in bib_text
        assert "New Title" in bib_text

    def test_update_bibtex_ignores_key_in_text(self, tmp_lib: Library, dummy_pdf: Path, dummy_bib: Path):
        paper = tmp_lib.add(bib_path=dummy_bib, pdf_path=dummy_pdf)
        new_bib = (
            "@article{totallydifferentkey,\n"
            "  title  = {Some Title},\n"
            "  author = {Doe, Jane},\n"
            "  year   = {2024},\n"
            "}\n"
        )
        updated = tmp_lib.update_bibtex(paper.citation_key, new_bib)
        assert updated.citation_key == paper.citation_key

    def test_update_bibtex_nonexistent_raises(self, tmp_lib: Library):
        with pytest.raises(KeyError):
            tmp_lib.update_bibtex("ghost2000key", "@article{x, title={T}, author={A}, year={2024}}")

    def test_update_bibtex_invalid_bib_raises(self, tmp_lib: Library, dummy_pdf: Path, dummy_bib: Path):
        paper = tmp_lib.add(bib_path=dummy_bib, pdf_path=dummy_pdf)
        with pytest.raises(ValueError):
            tmp_lib.update_bibtex(paper.citation_key, "not a bibtex entry at all")

