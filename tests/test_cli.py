"""CLI integration tests using click.testing.CliRunner."""

from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner

from liber.cli import cli


@pytest.fixture()
def runner():
    return CliRunner()


@pytest.fixture()
def lib_dir(tmp_path: Path) -> Path:
    return tmp_path / "testlib"


@pytest.fixture()
def dummy_pdf(tmp_path: Path) -> Path:
    pdf = tmp_path / "paper.pdf"
    pdf.write_bytes(b"%PDF-1.4 dummy")
    return pdf


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
    def _add(self, runner, lib_dir, dummy_pdf, extra=None):
        args = _base_args(lib_dir) + [
            "add",
            str(dummy_pdf),
            "--title", "Deep Learning",
            "--year", "2015",
            "--author", "LeCun, Yann",
            "--author", "Bengio, Yoshua",
            "--keyword", "deep learning",
            "--doi", "10.1038/nature14539",
        ]
        if extra:
            args += extra
        return runner.invoke(cli, args)

    def test_add_exits_zero(self, runner, lib_dir, dummy_pdf):
        result = self._add(runner, lib_dir, dummy_pdf)
        assert result.exit_code == 0, result.output

    def test_add_outputs_key(self, runner, lib_dir, dummy_pdf):
        result = self._add(runner, lib_dir, dummy_pdf)
        assert "lecun2015deep" in result.output

    def test_add_creates_files(self, runner, lib_dir, dummy_pdf):
        self._add(runner, lib_dir, dummy_pdf)
        paper_dir = lib_dir / "lecun2015deep"
        assert paper_dir.is_dir()
        assert (paper_dir / "lecun2015deep.pdf").exists()
        assert (paper_dir / "lecun2015deep.bib").exists()

    def test_add_with_custom_key(self, runner, lib_dir, dummy_pdf):
        result = self._add(runner, lib_dir, dummy_pdf, extra=["--key", "mycustomkey"])
        assert result.exit_code == 0
        assert "mycustomkey" in result.output

    def test_add_duplicate_fails(self, runner, lib_dir, dummy_pdf):
        self._add(runner, lib_dir, dummy_pdf)
        dummy_pdf2 = dummy_pdf.parent / "paper2.pdf"
        dummy_pdf2.write_bytes(b"%PDF second")
        result = runner.invoke(cli, _base_args(lib_dir) + [
            "add", str(dummy_pdf2),
            "--title", "Deep Learning",
            "--year", "2015",
            "--author", "LeCun, Yann",
        ])
        assert result.exit_code != 0

    def test_add_missing_pdf_fails(self, runner, lib_dir):
        result = runner.invoke(cli, _base_args(lib_dir) + [
            "add", "/nonexistent/file.pdf",
            "--title", "Test",
            "--year", "2021",
            "--author", "Author, A",
        ])
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

    def test_list_shows_added_paper(self, runner, lib_dir, dummy_pdf):
        runner.invoke(cli, _base_args(lib_dir) + [
            "add", str(dummy_pdf),
            "--title", "Neural Networks",
            "--year", "2020",
            "--author", "Doe, Jane",
        ])
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

    def test_search_by_author(self, runner, lib_dir, dummy_pdf):
        runner.invoke(cli, _base_args(lib_dir) + [
            "add", str(dummy_pdf),
            "--title", "Test Paper",
            "--year", "2021",
            "--author", "Smith, John",
            "--keyword", "testing",
        ])
        result = runner.invoke(cli, _base_args(lib_dir) + ["search", "--author", "Smith"])
        assert result.exit_code == 0
        assert "Test Paper" in result.output

    def test_search_no_match(self, runner, lib_dir, dummy_pdf):
        runner.invoke(cli, _base_args(lib_dir) + [
            "add", str(dummy_pdf),
            "--title", "Test Paper",
            "--year", "2021",
            "--author", "Smith, John",
        ])
        result = runner.invoke(cli, _base_args(lib_dir) + ["search", "--author", "Turing"])
        assert result.exit_code == 0
        assert "No papers" in result.output


# ---------------------------------------------------------------------------
# show
# ---------------------------------------------------------------------------


class TestShowCmd:
    def test_show_existing(self, runner, lib_dir, dummy_pdf):
        runner.invoke(cli, _base_args(lib_dir) + [
            "add", str(dummy_pdf),
            "--title", "Show Test",
            "--year", "2022",
            "--author", "Author, A",
            "--doi", "10.1/test",
        ])
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
    def test_remove_deletes_paper(self, runner, lib_dir, dummy_pdf):
        runner.invoke(cli, _base_args(lib_dir) + [
            "add", str(dummy_pdf),
            "--title", "To Remove",
            "--year", "2021",
            "--author", "Author, A",
        ])
        # "To Remove": "to" is a stop word → key becomes "author2021remove"
        result = runner.invoke(
            cli,
            _base_args(lib_dir) + ["remove", "author2021remove"],
            input="y\n",
        )
        assert result.exit_code == 0
        assert not (lib_dir / "author2021remove").exists()

    def test_remove_keep_files(self, runner, lib_dir, dummy_pdf):
        runner.invoke(cli, _base_args(lib_dir) + [
            "add", str(dummy_pdf),
            "--title", "Keep Me",
            "--year", "2021",
            "--author", "Author, A",
        ])
        result = runner.invoke(
            cli,
            _base_args(lib_dir) + ["remove", "--keep-files", "author2021keep"],
            input="y\n",
        )
        assert result.exit_code == 0
        assert (lib_dir / "author2021keep").exists()

    def test_remove_nonexistent_fails(self, runner, lib_dir):
        runner.invoke(cli, _base_args(lib_dir) + ["init"])
        result = runner.invoke(
            cli,
            _base_args(lib_dir) + ["remove", "ghost2000key"],
            input="y\n",
        )
        assert result.exit_code != 0
