"""CLI integration tests using click.testing.CliRunner."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from liber.cli import cli, _CONFIG_FILE, _read_saved_library_dir, _save_library_dir
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
    def test_init_creates_directory(self, runner, lib_dir, monkeypatch, tmp_path):
        config_file = tmp_path / "config.json"
        monkeypatch.setattr("liber.cli._CONFIG_FILE", config_file)
        result = runner.invoke(cli, _base_args(lib_dir) + ["init"])
        assert result.exit_code == 0
        assert lib_dir.is_dir()

    def test_init_idempotent(self, runner, lib_dir, monkeypatch, tmp_path):
        config_file = tmp_path / "config.json"
        monkeypatch.setattr("liber.cli._CONFIG_FILE", config_file)
        runner.invoke(cli, _base_args(lib_dir) + ["init"])
        result = runner.invoke(cli, _base_args(lib_dir) + ["init"])
        assert result.exit_code == 0

    def test_init_saves_library_dir_to_config(self, runner, lib_dir, monkeypatch, tmp_path):
        """init saves the library directory so subsequent commands use it."""
        config_file = tmp_path / "config.json"
        monkeypatch.setattr("liber.cli._CONFIG_FILE", config_file)
        result = runner.invoke(cli, _base_args(lib_dir) + ["init"])
        assert result.exit_code == 0
        assert config_file.exists()
        data = json.loads(config_file.read_text())
        assert Path(data["library_dir"]) == lib_dir

    def test_init_help_shows_library_dir_option(self, runner):
        result = runner.invoke(cli, ["init", "--help"])
        assert result.exit_code == 0
        assert "--library-dir" in result.output


# ---------------------------------------------------------------------------
# config helpers
# ---------------------------------------------------------------------------


class TestConfigHelpers:
    def test_read_saved_library_dir_missing_file(self, monkeypatch, tmp_path):
        """Returns None when no config file exists yet."""
        config_file = tmp_path / "nonexistent" / "config.json"
        monkeypatch.setattr("liber.cli._CONFIG_FILE", config_file)
        assert _read_saved_library_dir() is None

    def test_read_saved_library_dir_malformed_json(self, monkeypatch, tmp_path):
        """Returns None when the config file contains invalid JSON."""
        config_file = tmp_path / "config.json"
        config_file.write_text("not-valid-json", encoding="utf-8")
        monkeypatch.setattr("liber.cli._CONFIG_FILE", config_file)
        assert _read_saved_library_dir() is None

    def test_save_and_read_roundtrip(self, monkeypatch, tmp_path):
        """Saved directory can be read back correctly."""
        config_file = tmp_path / "config.json"
        monkeypatch.setattr("liber.cli._CONFIG_FILE", config_file)
        path = tmp_path / "mylib"
        _save_library_dir(path)
        assert _read_saved_library_dir() == path


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

    def test_add_help_shows_library_dir_option(self, runner):
        result = runner.invoke(cli, ["add", "--help"])
        assert result.exit_code == 0
        assert "--library-dir" in result.output

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

    def test_edit_bibtex_invalid_content_fails(self, runner, lib_dir, tmp_path, monkeypatch):
        """When the editor writes invalid BibTeX, an error is reported."""
        bib = make_bib(tmp_path, "ebinv.bib", "Edit Invalid", 2022, ["Author, A"])
        runner.invoke(cli, _base_args(lib_dir) + ["add", str(bib)])

        def write_invalid(args, **kw):
            Path(args[-1]).write_text("this is not valid bibtex", encoding="utf-8")

        monkeypatch.setattr("subprocess.run", write_invalid)
        result = runner.invoke(cli, _base_args(lib_dir) + ["edit-bibtex", "author2022edit"])
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


# ---------------------------------------------------------------------------
# add-pdf
# ---------------------------------------------------------------------------


class TestAddPdfCmd:
    def test_add_pdf_succeeds(self, runner, lib_dir, tmp_path, dummy_pdf):
        """add-pdf command copies a PDF into an existing paper entry."""
        bib = make_bib(tmp_path, "ap.bib", "Add PDF Paper", 2022, ["Author, A"])
        runner.invoke(cli, _base_args(lib_dir) + ["add", str(bib)])
        result = runner.invoke(
            cli, _base_args(lib_dir) + ["add-pdf", "author2022add", str(dummy_pdf)]
        )
        assert result.exit_code == 0, result.output
        assert "PDF added" in result.output
        assert (lib_dir / "library" / "author2022add" / "author2022add.pdf").exists()

    def test_add_pdf_nonexistent_key_fails(self, runner, lib_dir, dummy_pdf):
        runner.invoke(cli, _base_args(lib_dir) + ["init"])
        result = runner.invoke(
            cli, _base_args(lib_dir) + ["add-pdf", "ghost2000key", str(dummy_pdf)]
        )
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# note
# ---------------------------------------------------------------------------


class TestNoteCmd:
    def test_note_creates_file_and_opens_editor(self, runner, lib_dir, tmp_path, monkeypatch):
        """note command creates the notes file and opens it in $EDITOR."""
        bib = make_bib(tmp_path, "note.bib", "Note Paper", 2023, ["Author, A"])
        runner.invoke(cli, _base_args(lib_dir) + ["add", str(bib)])

        opened = []
        monkeypatch.setattr(
            "subprocess.run", lambda args, **kw: opened.append(args)
        )
        result = runner.invoke(cli, _base_args(lib_dir) + ["note", "author2023note"])
        assert result.exit_code == 0
        # editor was called with the notes file
        assert len(opened) == 1
        assert "author2023note.md" in opened[0][-1]

    def test_note_existing_file_opened_without_overwrite(
        self, runner, lib_dir, tmp_path, monkeypatch
    ):
        """If a notes file already exists its content is not overwritten."""
        bib = make_bib(tmp_path, "notex.bib", "Note Existing", 2023, ["Author, A"])
        runner.invoke(cli, _base_args(lib_dir) + ["add", str(bib)])
        notes_path = lib_dir / "library" / "author2023note" / "author2023note.md"
        notes_path.write_text("# Existing notes\n", encoding="utf-8")

        monkeypatch.setattr("subprocess.run", lambda *a, **kw: None)
        result = runner.invoke(cli, _base_args(lib_dir) + ["note", "author2023note"])
        assert result.exit_code == 0
        assert notes_path.read_text(encoding="utf-8") == "# Existing notes\n"

    def test_note_nonexistent_key_fails(self, runner, lib_dir):
        runner.invoke(cli, _base_args(lib_dir) + ["init"])
        result = runner.invoke(cli, _base_args(lib_dir) + ["note", "ghost2000key"])
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# edit-bibtex with actual changes
# ---------------------------------------------------------------------------


class TestEditBibtexCmdExtended:
    def test_edit_bibtex_with_changes(self, runner, lib_dir, tmp_path, monkeypatch):
        """When the editor modifies the bib content the index is updated."""
        bib = make_bib(tmp_path, "ebc.bib", "Edit Changed", 2022, ["Author, A"])
        runner.invoke(cli, _base_args(lib_dir) + ["add", str(bib)])

        new_content = (
            "@article{author2022edit,\n"
            "  title  = {Updated Title},\n"
            "  author = {Author, A},\n"
            "  year   = {2022},\n"
            "}\n"
        )

        def fake_editor(args, **kw):
            # args is [editor, tmp_file_path] – write new content to tmp file
            Path(args[-1]).write_text(new_content, encoding="utf-8")

        monkeypatch.setattr("subprocess.run", fake_editor)
        result = runner.invoke(
            cli, _base_args(lib_dir) + ["edit-bibtex", "author2022edit"]
        )
        assert result.exit_code == 0, result.output
        assert "updated" in result.output.lower()


# ---------------------------------------------------------------------------
# tag add – invalid chars / tag remove – nonexistent paper
# ---------------------------------------------------------------------------


class TestTagCmdsExtended:
    def test_tag_add_invalid_chars_fails(self, runner, lib_dir, tmp_path):
        """tag add with invalid chars in tag name fails (ValueError path)."""
        bib = make_bib(tmp_path, "tagi.bib", "Tag Invalid", 2024, ["Author, A"])
        runner.invoke(cli, _base_args(lib_dir) + ["add", str(bib)])
        result = runner.invoke(
            cli, _base_args(lib_dir) + ["tag", "add", "author2024tag", "bad!tag#"]
        )
        assert result.exit_code != 0

    def test_tag_remove_nonexistent_paper_fails(self, runner, lib_dir):
        """tag remove for a non-existent paper fails (KeyError path)."""
        runner.invoke(cli, _base_args(lib_dir) + ["init"])
        result = runner.invoke(
            cli, _base_args(lib_dir) + ["tag", "remove", "ghost2000key", "ml"]
        )
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# export – fallback to paper.to_bibtex() when stored .bib is missing
# ---------------------------------------------------------------------------


class TestExportCmdFallback:
    def test_export_paper_without_stored_bib(self, runner, lib_dir, tmp_path):
        """Export falls back to paper.to_bibtex() when .bib file is absent (line 582)."""
        bib = make_bib(tmp_path, "efb.bib", "Fallback Paper", 2020, ["Author, A"])
        runner.invoke(cli, _base_args(lib_dir) + ["add", str(bib)])
        # Remove the stored bib file to trigger the fallback path
        stored_bib = lib_dir / "library" / "author2020fallback" / "author2020fallback.bib"
        stored_bib.unlink()

        result = runner.invoke(cli, _base_args(lib_dir) + ["export"])
        assert result.exit_code == 0
        assert "@article" in result.output
        assert "Fallback Paper" in result.output


# ---------------------------------------------------------------------------
# serve
# ---------------------------------------------------------------------------


class TestServeCmd:
    def test_serve_starts_app(self, runner, lib_dir, tmp_path, monkeypatch):
        """serve command creates the Flask app and calls app.run (lines 644-651)."""
        runs = []

        class FakeApp:
            def run(self, host, port, debug):
                runs.append({"host": host, "port": port, "debug": debug})

        monkeypatch.setattr("liber.web.create_app", lambda **kw: FakeApp())
        result = runner.invoke(
            cli,
            _base_args(lib_dir) + ["serve", "--host", "127.0.0.1", "--port", "5001"],
        )
        assert result.exit_code == 0
        assert "5001" in result.output
        assert len(runs) == 1
        assert runs[0]["port"] == 5001

    def test_serve_uses_saved_library_dir(self, runner, lib_dir, monkeypatch, tmp_path):
        """serve uses the directory saved by init when --library-dir is omitted."""
        config_file = tmp_path / "config.json"
        monkeypatch.setattr("liber.cli._CONFIG_FILE", config_file)

        # First, init with a custom directory so it gets saved to the config
        runner.invoke(cli, _base_args(lib_dir) + ["init"])
        assert config_file.exists()

        # Now serve WITHOUT --library-dir; it should use the saved dir
        received_dirs = []

        def fake_create_app(**kw):
            received_dirs.append(kw.get("library_dir"))

            class FakeApp:
                def run(self, host, port, debug):
                    pass

            return FakeApp()

        monkeypatch.setattr("liber.web.create_app", fake_create_app)
        result = runner.invoke(cli, ["serve"])
        assert result.exit_code == 0
        assert received_dirs, "create_app was not called"
        assert received_dirs[0] == lib_dir
