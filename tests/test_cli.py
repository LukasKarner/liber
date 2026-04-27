"""CLI integration tests using click.testing.CliRunner."""

from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner

from liber.cli import cli
from tests.conftest import make_bib


@pytest.fixture()
def runner():
    return CliRunner()


@pytest.fixture()
def lib_dir(tmp_path: Path) -> Path:
    return tmp_path / "testlib"


@pytest.fixture()
def dummy_bib(tmp_path: Path) -> Path:
    """BibTeX file for 'Deep Learning' by LeCun et al. (2015)."""
    bib = tmp_path / "paper.bib"
    bib.write_text(
        "@article{oldkey,\n"
        "  title    = {Deep Learning},\n"
        "  author   = {LeCun, Yann and Bengio, Yoshua},\n"
        "  year     = {2015},\n"
        "  keywords = {deep learning, neural networks},\n"
        "  doi      = {10.1038/nature14539},\n"
        "}\n",
        encoding="utf-8",
    )
    return bib


def _base_args(lib_dir: Path) -> list:
    return ["--library-dir", str(lib_dir)]


# ---------------------------------------------------------------------------
# init
# ---------------------------------------------------------------------------


class TestInitCmd:
    def test_init_creates_directory(self, runner, lib_dir):
        result = runner.invoke(cli, _base_args(lib_dir) + ["init"])
        assert result.exit_code == 0
        assert lib_dir.is_dir()

    def test_init_idempotent(self, runner, lib_dir):
        runner.invoke(cli, _base_args(lib_dir) + ["init"])
        result = runner.invoke(cli, _base_args(lib_dir) + ["init"])
        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# add
# ---------------------------------------------------------------------------


class TestAddCmd:
    def _add(self, runner, lib_dir, dummy_bib, dummy_pdf=None, extra=None):
        args = _base_args(lib_dir) + ["add", str(dummy_bib)]
        if dummy_pdf:
            args += ["--pdf", str(dummy_pdf)]
        if extra:
            args += extra
        return runner.invoke(cli, args)

    def test_add_exits_zero(self, runner, lib_dir, dummy_pdf, dummy_bib):
        result = self._add(runner, lib_dir, dummy_bib, dummy_pdf)
        assert result.exit_code == 0, result.output

    def test_add_outputs_key(self, runner, lib_dir, dummy_pdf, dummy_bib):
        result = self._add(runner, lib_dir, dummy_bib, dummy_pdf)
        assert "lecun2015deep" in result.output

    def test_add_creates_files(self, runner, lib_dir, dummy_pdf, dummy_bib):
        self._add(runner, lib_dir, dummy_bib, dummy_pdf)
        paper_dir = lib_dir / "library" / "lecun2015deep"
        assert paper_dir.is_dir()
        assert (paper_dir / "lecun2015deep.pdf").exists()
        assert (paper_dir / "lecun2015deep.bib").exists()

    def test_add_without_pdf(self, runner, lib_dir, dummy_bib):
        """Adding a paper without --pdf should succeed with no .pdf file created."""
        result = self._add(runner, lib_dir, dummy_bib)
        assert result.exit_code == 0, result.output
        paper_dir = lib_dir / "library" / "lecun2015deep"
        assert paper_dir.is_dir()
        assert not (paper_dir / "lecun2015deep.pdf").exists()
        assert (paper_dir / "lecun2015deep.bib").exists()

    def test_add_bib_key_updated(self, runner, lib_dir, dummy_pdf, dummy_bib):
        """The stored .bib file must use the new citation key, not the original."""
        self._add(runner, lib_dir, dummy_bib, dummy_pdf)
        bib_text = (lib_dir / "library" / "lecun2015deep" / "lecun2015deep.bib").read_text()
        assert "lecun2015deep" in bib_text
        assert "oldkey" not in bib_text

    def test_add_bib_fields_preserved(self, runner, lib_dir, dummy_pdf, dummy_bib):
        """Original BibTeX fields (title, author, doi…) must be preserved."""
        self._add(runner, lib_dir, dummy_bib, dummy_pdf)
        bib_text = (lib_dir / "library" / "lecun2015deep" / "lecun2015deep.bib").read_text()
        assert "Deep Learning" in bib_text
        assert "LeCun, Yann" in bib_text
        assert "10.1038/nature14539" in bib_text

    def test_add_with_custom_key(self, runner, lib_dir, dummy_pdf, dummy_bib):
        result = self._add(runner, lib_dir, dummy_bib, dummy_pdf, extra=["--key", "mycustomkey"])
        assert result.exit_code == 0
        assert "mycustomkey" in result.output

    def test_add_duplicate_fails(self, runner, lib_dir, dummy_pdf, dummy_bib):
        self._add(runner, lib_dir, dummy_bib, dummy_pdf)
        dummy_pdf2 = dummy_pdf.parent / "paper2.pdf"
        dummy_pdf2.write_bytes(b"%PDF second")
        result = runner.invoke(cli, _base_args(lib_dir) + ["add", str(dummy_bib), "--pdf", str(dummy_pdf2)])
        assert result.exit_code != 0

    def test_add_no_doi_graceful(self, runner, lib_dir, tmp_path, dummy_pdf):
        bib = make_bib(tmp_path, "nodoi.bib", "No DOI Paper", 2021, ["Author, A"])
        result = runner.invoke(cli, _base_args(lib_dir) + ["add", str(bib), "--pdf", str(dummy_pdf)])
        assert result.exit_code == 0

    def test_add_missing_pdf_fails(self, runner, lib_dir, dummy_bib):
        result = runner.invoke(
            cli, _base_args(lib_dir) + ["add", str(dummy_bib), "--pdf", "/nonexistent/file.pdf"]
        )
        assert result.exit_code != 0

    def test_add_missing_bib_fails(self, runner, lib_dir, dummy_pdf):
        result = runner.invoke(
            cli, _base_args(lib_dir) + ["add", "/nonexistent/paper.bib", "--pdf", str(dummy_pdf)]
        )
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# list
# ---------------------------------------------------------------------------


class TestListCmd:
    def test_list_empty(self, runner, lib_dir):
        runner.invoke(cli, _base_args(lib_dir) + ["init"])
        result = runner.invoke(cli, _base_args(lib_dir) + ["list"])
        assert result.exit_code == 0
        assert "empty" in result.output.lower()

    def test_list_shows_added_paper(self, runner, lib_dir, tmp_path, dummy_pdf):
        bib = make_bib(tmp_path, "nn.bib", "Neural Networks", 2020, ["Doe, Jane"])
        runner.invoke(cli, _base_args(lib_dir) + ["add", str(bib), "--pdf", str(dummy_pdf)])
        result = runner.invoke(cli, _base_args(lib_dir) + ["list"])
        assert result.exit_code == 0
        assert "Neural Networks" in result.output
        assert "2020" in result.output


# ---------------------------------------------------------------------------
# search
# ---------------------------------------------------------------------------


class TestSearchCmd:
    def test_search_no_filters_fails(self, runner, lib_dir):
        runner.invoke(cli, _base_args(lib_dir) + ["init"])
        result = runner.invoke(cli, _base_args(lib_dir) + ["search"])
        assert result.exit_code != 0

    def test_search_by_author(self, runner, lib_dir, tmp_path, dummy_pdf):
        bib = make_bib(tmp_path, "tp.bib", "Test Paper", 2021,
                        ["Smith, John"], ["testing"])
        runner.invoke(cli, _base_args(lib_dir) + ["add", str(bib), "--pdf", str(dummy_pdf)])
        result = runner.invoke(cli, _base_args(lib_dir) + ["search", "--author", "Smith"])
        assert result.exit_code == 0
        assert "Test Paper" in result.output

    def test_search_no_match(self, runner, lib_dir, tmp_path, dummy_pdf):
        bib = make_bib(tmp_path, "tp.bib", "Test Paper", 2021, ["Smith, John"])
        runner.invoke(cli, _base_args(lib_dir) + ["add", str(bib), "--pdf", str(dummy_pdf)])
        result = runner.invoke(cli, _base_args(lib_dir) + ["search", "--author", "Turing"])
        assert result.exit_code == 0
        assert "No papers" in result.output


# ---------------------------------------------------------------------------
# show
# ---------------------------------------------------------------------------


class TestShowCmd:
    def test_show_existing(self, runner, lib_dir, tmp_path, dummy_pdf):
        bib = make_bib(tmp_path, "show.bib", "Show Test", 2022,
                        ["Author, A"], [], "10.1/test")
        runner.invoke(cli, _base_args(lib_dir) + ["add", str(bib), "--pdf", str(dummy_pdf)])
        result = runner.invoke(cli, _base_args(lib_dir) + ["show", "author2022show"])
        assert result.exit_code == 0
        assert "Show Test" in result.output
        assert "10.1/test" in result.output

    def test_show_nonexistent_fails(self, runner, lib_dir):
        runner.invoke(cli, _base_args(lib_dir) + ["init"])
        result = runner.invoke(cli, _base_args(lib_dir) + ["show", "ghost2000key"])
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# remove
# ---------------------------------------------------------------------------


class TestRemoveCmd:
    def test_remove_deletes_paper(self, runner, lib_dir, tmp_path, dummy_pdf):
        bib = make_bib(tmp_path, "rm.bib", "Remove Paper", 2021, ["Author, A"])
        runner.invoke(cli, _base_args(lib_dir) + ["add", str(bib), "--pdf", str(dummy_pdf)])
        result = runner.invoke(
            cli,
            _base_args(lib_dir) + ["remove", "author2021remove"],
            input="y\n",
        )
        assert result.exit_code == 0
        assert not (lib_dir / "library" / "author2021remove").exists()

    def test_remove_keep_files(self, runner, lib_dir, tmp_path, dummy_pdf):
        bib = make_bib(tmp_path, "keep.bib", "Keep Paper", 2021, ["Author, A"])
        runner.invoke(cli, _base_args(lib_dir) + ["add", str(bib), "--pdf", str(dummy_pdf)])
        result = runner.invoke(
            cli,
            _base_args(lib_dir) + ["remove", "--keep-files", "author2021keep"],
            input="y\n",
        )
        assert result.exit_code == 0
        assert (lib_dir / "library" / "author2021keep").exists()

    def test_remove_nonexistent_fails(self, runner, lib_dir):
        runner.invoke(cli, _base_args(lib_dir) + ["init"])
        result = runner.invoke(
            cli,
            _base_args(lib_dir) + ["remove", "ghost2000key"],
            input="y\n",
        )
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# rename-key
# ---------------------------------------------------------------------------


class TestRenameKeyCmd:
    def _add_paper(self, runner, lib_dir, tmp_path, dummy_pdf):
        bib = make_bib(tmp_path, "rk.bib", "Rename Key Paper", 2021, ["Author, A"])
        runner.invoke(cli, _base_args(lib_dir) + ["add", str(bib), "--pdf", str(dummy_pdf)])

    def test_rename_key_succeeds(self, runner, lib_dir, tmp_path, dummy_pdf):
        self._add_paper(runner, lib_dir, tmp_path, dummy_pdf)
        result = runner.invoke(
            cli, _base_args(lib_dir) + ["rename-key", "author2021rename", "newkey2021"]
        )
        assert result.exit_code == 0
        assert "newkey2021" in result.output
        assert (lib_dir / "library" / "newkey2021").is_dir()
        assert not (lib_dir / "library" / "author2021rename").exists()

    def test_rename_key_nonexistent_fails(self, runner, lib_dir):
        runner.invoke(cli, _base_args(lib_dir) + ["init"])
        result = runner.invoke(cli, _base_args(lib_dir) + ["rename-key", "ghost", "newkey"])
        assert result.exit_code != 0

    def test_rename_key_invalid_key_fails(self, runner, lib_dir, tmp_path, dummy_pdf):
        self._add_paper(runner, lib_dir, tmp_path, dummy_pdf)
        result = runner.invoke(
            cli, _base_args(lib_dir) + ["rename-key", "author2021rename", "invalid key!"]
        )
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# edit-bibtex (non-interactive: no change)
# ---------------------------------------------------------------------------


class TestEditBibtexCmd:
    def test_edit_bibtex_no_change(self, runner, lib_dir, tmp_path, dummy_pdf, monkeypatch):
        """When the editor makes no changes, reports 'No changes made'."""
        bib = make_bib(tmp_path, "eb.bib", "Edit Bibtex", 2022, ["Author, A"])
        runner.invoke(cli, _base_args(lib_dir) + ["add", str(bib)])

        # Monkeypatch subprocess.run to be a no-op (simulate no editor changes)
        monkeypatch.setattr("subprocess.run", lambda *a, **kw: None)

        result = runner.invoke(cli, _base_args(lib_dir) + ["edit-bibtex", "author2022edit"])
        assert result.exit_code == 0
        assert "No changes" in result.output

    def test_edit_bibtex_nonexistent_fails(self, runner, lib_dir):
        runner.invoke(cli, _base_args(lib_dir) + ["init"])
        result = runner.invoke(cli, _base_args(lib_dir) + ["edit-bibtex", "ghost"])
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# tag
# ---------------------------------------------------------------------------


class TestTagCmds:
    def _add_paper(self, runner, lib_dir, tmp_path):
        bib = make_bib(tmp_path, "tag.bib", "Tag Paper", 2023, ["Author, A"])
        runner.invoke(cli, _base_args(lib_dir) + ["add", str(bib)])

    def test_tag_list_empty(self, runner, lib_dir):
        runner.invoke(cli, _base_args(lib_dir) + ["init"])
        result = runner.invoke(cli, _base_args(lib_dir) + ["tag", "list"])
        assert result.exit_code == 0
        assert "No tags" in result.output

    def test_tag_create_and_list(self, runner, lib_dir):
        runner.invoke(cli, _base_args(lib_dir) + ["init"])
        runner.invoke(cli, _base_args(lib_dir) + ["tag", "create", "ml"])
        result = runner.invoke(cli, _base_args(lib_dir) + ["tag", "list"])
        assert result.exit_code == 0
        assert "ml" in result.output

    def test_tag_create_invalid_fails(self, runner, lib_dir):
        runner.invoke(cli, _base_args(lib_dir) + ["init"])
        result = runner.invoke(cli, _base_args(lib_dir) + ["tag", "create", "bad!tag"])
        assert result.exit_code != 0

    def test_tag_delete(self, runner, lib_dir):
        runner.invoke(cli, _base_args(lib_dir) + ["init"])
        runner.invoke(cli, _base_args(lib_dir) + ["tag", "create", "todelete"])
        result = runner.invoke(
            cli, _base_args(lib_dir) + ["tag", "delete", "todelete"], input="y\n"
        )
        assert result.exit_code == 0
        result2 = runner.invoke(cli, _base_args(lib_dir) + ["tag", "list"])
        assert "todelete" not in result2.output

    def test_tag_delete_nonexistent_fails(self, runner, lib_dir):
        runner.invoke(cli, _base_args(lib_dir) + ["init"])
        result = runner.invoke(
            cli, _base_args(lib_dir) + ["tag", "delete", "ghost"], input="y\n"
        )
        assert result.exit_code != 0

    def test_tag_add_to_paper(self, runner, lib_dir, tmp_path):
        self._add_paper(runner, lib_dir, tmp_path)
        result = runner.invoke(
            cli, _base_args(lib_dir) + ["tag", "add", "author2023tag", "ml"]
        )
        assert result.exit_code == 0
        show_result = runner.invoke(cli, _base_args(lib_dir) + ["show", "author2023tag"])
        assert "ml" in show_result.output

    def test_tag_remove_from_paper(self, runner, lib_dir, tmp_path):
        self._add_paper(runner, lib_dir, tmp_path)
        runner.invoke(cli, _base_args(lib_dir) + ["tag", "add", "author2023tag", "ml"])
        result = runner.invoke(
            cli, _base_args(lib_dir) + ["tag", "remove", "author2023tag", "ml"]
        )
        assert result.exit_code == 0

    def test_tag_add_nonexistent_paper_fails(self, runner, lib_dir):
        runner.invoke(cli, _base_args(lib_dir) + ["init"])
        result = runner.invoke(cli, _base_args(lib_dir) + ["tag", "add", "ghost", "ml"])
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# export
# ---------------------------------------------------------------------------


class TestExportCmd:
    def test_export_empty_library(self, runner, lib_dir):
        runner.invoke(cli, _base_args(lib_dir) + ["init"])
        result = runner.invoke(cli, _base_args(lib_dir) + ["export"])
        assert result.exit_code == 0

    def test_export_to_stdout(self, runner, lib_dir, tmp_path, dummy_pdf):
        bib = make_bib(tmp_path, "ex.bib", "Export Paper", 2020, ["Author, A"])
        runner.invoke(cli, _base_args(lib_dir) + ["add", str(bib)])
        result = runner.invoke(cli, _base_args(lib_dir) + ["export"])
        assert result.exit_code == 0
        assert "@article" in result.output

    def test_export_to_file(self, runner, lib_dir, tmp_path):
        bib = make_bib(tmp_path, "exf.bib", "Export File Paper", 2021, ["Author, A"])
        runner.invoke(cli, _base_args(lib_dir) + ["add", str(bib)])
        out_file = str(tmp_path / "out.bib")
        result = runner.invoke(cli, _base_args(lib_dir) + ["export", "--output", out_file])
        assert result.exit_code == 0
        assert Path(out_file).exists()
        assert "@article" in Path(out_file).read_text()

    def test_export_with_filter(self, runner, lib_dir, tmp_path):
        bib1 = make_bib(tmp_path, "e1.bib", "Alpha Paper", 2020, ["Alpha, A"])
        bib2 = make_bib(tmp_path, "e2.bib", "Beta Paper", 2021, ["Beta, B"])
        runner.invoke(cli, _base_args(lib_dir) + ["add", str(bib1)])
        runner.invoke(cli, _base_args(lib_dir) + ["add", str(bib2)])
        result = runner.invoke(cli, _base_args(lib_dir) + ["export", "--author", "Alpha"])
        assert result.exit_code == 0
        assert "Alpha" in result.output
        assert "Beta" not in result.output


# ---------------------------------------------------------------------------
# delete-pdf
# ---------------------------------------------------------------------------


class TestDeletePdfCmd:
    def test_delete_pdf_succeeds(self, runner, lib_dir, tmp_path, dummy_pdf):
        bib = make_bib(tmp_path, "dp.bib", "Delete PDF Paper", 2022, ["Author, A"])
        runner.invoke(cli, _base_args(lib_dir) + ["add", str(bib), "--pdf", str(dummy_pdf)])
        result = runner.invoke(
            cli, _base_args(lib_dir) + ["delete-pdf", "author2022delete"], input="y\n"
        )
        assert result.exit_code == 0
        assert not (lib_dir / "library" / "author2022delete" / "author2022delete.pdf").exists()

    def test_delete_pdf_no_pdf_fails(self, runner, lib_dir, tmp_path):
        bib = make_bib(tmp_path, "dnp.bib", "Delete No PDF", 2022, ["Author, A"])
        runner.invoke(cli, _base_args(lib_dir) + ["add", str(bib)])
        result = runner.invoke(
            cli, _base_args(lib_dir) + ["delete-pdf", "author2022delete"], input="y\n"
        )
        assert result.exit_code != 0

    def test_delete_pdf_nonexistent_paper_fails(self, runner, lib_dir):
        runner.invoke(cli, _base_args(lib_dir) + ["init"])
        result = runner.invoke(
            cli, _base_args(lib_dir) + ["delete-pdf", "ghost"], input="y\n"
        )
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# search with --tag filter
# ---------------------------------------------------------------------------


class TestSearchTagFilter:
    def test_search_by_tag(self, runner, lib_dir, tmp_path):
        bib = make_bib(tmp_path, "st.bib", "Search Tag Paper", 2021, ["Author, A"])
        runner.invoke(cli, _base_args(lib_dir) + ["add", str(bib)])
        runner.invoke(cli, _base_args(lib_dir) + ["tag", "add", "author2021search", "mytag"])
        result = runner.invoke(cli, _base_args(lib_dir) + ["search", "--tag", "mytag"])
        assert result.exit_code == 0
        assert "Search Tag Paper" in result.output

    def test_search_tag_no_match(self, runner, lib_dir, tmp_path):
        bib = make_bib(tmp_path, "st2.bib", "Another Paper", 2022, ["Author, A"])
        runner.invoke(cli, _base_args(lib_dir) + ["add", str(bib)])
        result = runner.invoke(cli, _base_args(lib_dir) + ["search", "--tag", "nonexistenttag"])
        assert result.exit_code == 0
        assert "No papers" in result.output

