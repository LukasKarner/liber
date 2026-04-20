"""Command-line interface for liber."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

import click

from liber.library import Library, make_citation_key

# ---------------------------------------------------------------------------
# Configuration helpers
# ---------------------------------------------------------------------------

_DEFAULT_LIBRARY_DIR = Path.home() / "liber"
_LIBER_DIR_ENV = "LIBER_DIR"


def _get_library(ctx: click.Context) -> Library:
    """Return a :class:`Library` instance for the directory in *ctx.obj*."""
    return Library(ctx.obj["library_dir"])


# ---------------------------------------------------------------------------
# CLI root
# ---------------------------------------------------------------------------


@click.group()
@click.option(
    "--library-dir",
    "-d",
    envvar=_LIBER_DIR_ENV,
    default=str(_DEFAULT_LIBRARY_DIR),
    show_default=True,
    help="Path to the library directory.",
    type=click.Path(),
)
@click.pass_context
def cli(ctx: click.Context, library_dir: str) -> None:
    """liber – academic literature management system.

    Manages a directory of academic papers, each in its own sub-directory
    containing a PDF, a BibTeX file, and optional Markdown notes.

    The library directory can be set with the --library-dir option or the
    LIBER_DIR environment variable.
    """
    ctx.ensure_object(dict)
    ctx.obj["library_dir"] = Path(library_dir)


# ---------------------------------------------------------------------------
# init
# ---------------------------------------------------------------------------


@cli.command("init")
@click.pass_context
def init_cmd(ctx: click.Context) -> None:
    """Initialise a new library directory."""
    lib = _get_library(ctx)
    lib.init()
    click.echo(f"Library initialised at: {lib.library_dir}")


# ---------------------------------------------------------------------------
# add
# ---------------------------------------------------------------------------


@cli.command("add")
@click.argument("pdf", type=click.Path(exists=True, dir_okay=False))
@click.argument("bib", type=click.Path(exists=True, dir_okay=False))
@click.option(
    "--key",
    default=None,
    help="Override the auto-generated citation key.",
)
@click.pass_context
def add_cmd(
    ctx: click.Context,
    pdf: str,
    bib: str,
    key: Optional[str],
) -> None:
    """Add a paper to the library.

    PDF is the path to the PDF file to import.
    BIB is the path to the existing BibTeX file for the paper.

    Metadata (title, year, authors, keywords, doi) is extracted from the bib
    file.  The citation key is rewritten to the author-year-title format; all
    other BibTeX fields are preserved unchanged.

    Example:

    \b
        liber add paper.pdf paper.bib
        liber add paper.pdf paper.bib --key lecun2015deep
    """
    lib = _get_library(ctx)
    lib.init()
    try:
        paper = lib.add(
            pdf_path=Path(pdf),
            bib_path=Path(bib),
            citation_key=key,
        )
    except (FileExistsError, FileNotFoundError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc

    click.echo(f"Added paper '{paper.citation_key}'.")
    click.echo(f"  Directory : {lib.library_dir / paper.citation_key}")
    click.echo(f"  BibTeX key: {paper.citation_key}")


# ---------------------------------------------------------------------------
# list
# ---------------------------------------------------------------------------


@cli.command("list")
@click.pass_context
def list_cmd(ctx: click.Context) -> None:
    """List all papers in the library."""
    lib = _get_library(ctx)
    papers = lib.list_papers()
    if not papers:
        click.echo("The library is empty.")
        return

    for paper in papers:
        authors_str = "; ".join(paper.authors)
        click.echo(
            f"[{paper.citation_key}]  {paper.year}  {paper.title}  —  {authors_str}"
        )


# ---------------------------------------------------------------------------
# search
# ---------------------------------------------------------------------------


@cli.command("search")
@click.option("--title", "-t", default=None, help="Filter by title substring.")
@click.option("--author", "-a", default=None, help="Filter by author substring.")
@click.option("--year", "-y", default=None, type=int, help="Filter by exact year.")
@click.option("--keyword", "-k", default=None, help="Filter by keyword substring.")
@click.pass_context
def search_cmd(
    ctx: click.Context,
    title: Optional[str],
    author: Optional[str],
    year: Optional[int],
    keyword: Optional[str],
) -> None:
    """Search papers in the library.

    Multiple filters are combined with AND logic.
    """
    if all(v is None for v in (title, author, year, keyword)):
        raise click.UsageError(
            "Provide at least one of --title, --author, --year, --keyword."
        )

    lib = _get_library(ctx)
    papers = lib.search(title=title, author=author, year=year, keyword=keyword)

    if not papers:
        click.echo("No papers matched your query.")
        return

    for paper in papers:
        authors_str = "; ".join(paper.authors)
        click.echo(
            f"[{paper.citation_key}]  {paper.year}  {paper.title}  —  {authors_str}"
        )


# ---------------------------------------------------------------------------
# show
# ---------------------------------------------------------------------------


@cli.command("show")
@click.argument("citation_key")
@click.pass_context
def show_cmd(ctx: click.Context, citation_key: str) -> None:
    """Show details for a paper identified by CITATION_KEY."""
    lib = _get_library(ctx)
    try:
        paper = lib.get(citation_key)
    except KeyError as exc:
        raise click.ClickException(str(exc)) from exc

    paper_dir = lib.library_dir / citation_key
    notes_path = lib.notes_path(citation_key)

    click.echo(f"Citation key : {paper.citation_key}")
    click.echo(f"Title        : {paper.title}")
    click.echo(f"Year         : {paper.year}")
    click.echo(f"Authors      : {'; '.join(paper.authors)}")
    click.echo(f"Keywords     : {', '.join(paper.keywords)}")
    click.echo(f"DOI          : {paper.doi or '—'}")
    click.echo(f"Directory    : {paper_dir}")
    click.echo(f"Notes        : {notes_path} ({'exists' if notes_path.exists() else 'not created yet'})")


# ---------------------------------------------------------------------------
# remove
# ---------------------------------------------------------------------------


@cli.command("remove")
@click.argument("citation_key")
@click.option(
    "--keep-files",
    is_flag=True,
    default=False,
    help="Remove from index only; keep files on disk.",
)
@click.confirmation_option(prompt="Are you sure you want to remove this paper?")
@click.pass_context
def remove_cmd(ctx: click.Context, citation_key: str, keep_files: bool) -> None:
    """Remove the paper identified by CITATION_KEY from the library."""
    lib = _get_library(ctx)
    try:
        paper = lib.remove(citation_key, delete_files=not keep_files)
    except KeyError as exc:
        raise click.ClickException(str(exc)) from exc

    action = "removed from index (files kept)" if keep_files else "removed"
    click.echo(f"Paper '{paper.citation_key}' {action}.")


# ---------------------------------------------------------------------------
# note
# ---------------------------------------------------------------------------


@cli.command("note")
@click.argument("citation_key")
@click.pass_context
def note_cmd(ctx: click.Context, citation_key: str) -> None:
    """Open (or create) the Markdown notes file for CITATION_KEY.

    Uses the EDITOR environment variable, falling back to 'nano'.
    """
    lib = _get_library(ctx)
    try:
        notes = lib.notes_path(citation_key)
    except KeyError as exc:
        raise click.ClickException(str(exc)) from exc

    # Create an empty notes file if it doesn't exist yet
    if not notes.exists():
        paper = lib.get(citation_key)
        notes.write_text(
            f"# Notes: {paper.title} ({paper.year})\n\n",
            encoding="utf-8",
        )

    editor = os.environ.get("EDITOR", "nano")
    subprocess.run([editor, str(notes)], check=False)
