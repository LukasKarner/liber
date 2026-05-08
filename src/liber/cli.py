"""Command-line interface for liber."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

import click

from liber.library import Library, make_citation_key

# ---------------------------------------------------------------------------
# Configuration helpers
# ---------------------------------------------------------------------------

_DEFAULT_LIBRARY_DIR = Path.home() / "liber"
_LIBER_DIR_ENV = "LIBER_DIR"
_CONFIG_FILE = Path.home() / ".config" / "liber" / "config.json"


class LiberCommand(click.Command):
    """Custom command that documents global options in subcommand help."""

    def format_options(
        self,
        ctx: click.Context,
        formatter: click.HelpFormatter,
    ) -> None:
        super().format_options(ctx, formatter)

        if ctx.parent is None:
            return

        local_option_names = {
            param.name
            for param in self.get_params(ctx)
            if isinstance(param, click.Option)
        }
        global_records = []
        for param in ctx.parent.command.get_params(ctx.parent):
            if not isinstance(param, click.Option):
                continue
            if param.name in local_option_names:
                continue
            record = param.get_help_record(ctx.parent)
            if record is not None:
                global_records.append(record)

        if global_records:
            with formatter.section("Global Options"):
                formatter.write_dl(global_records)


class LiberGroup(click.Group):
    """CLI group using LiberCommand for subcommands."""

    command_class = LiberCommand


def _read_saved_library_dir() -> Optional[Path]:
    """Return the library directory saved by a previous ``init``, or *None*."""
    try:
        data = json.loads(_CONFIG_FILE.read_text(encoding="utf-8"))
        return Path(data["library_dir"])
    except Exception:  # noqa: BLE001
        return None


def _save_library_dir(path: Path) -> None:
    """Persist *path* as the active library directory."""
    _CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    _CONFIG_FILE.write_text(
        json.dumps({"library_dir": str(path)}, indent=2),
        encoding="utf-8",
    )


def _get_library(ctx: click.Context) -> Library:
    """Return a :class:`Library` instance for the directory in *ctx.obj*."""
    return Library(ctx.obj["library_dir"])


# ---------------------------------------------------------------------------
# CLI root
# ---------------------------------------------------------------------------


@click.group(cls=LiberGroup)
@click.option(
    "--library-dir",
    "-d",
    envvar=_LIBER_DIR_ENV,
    default=None,
    show_default=False,
    help=(
        "Path to the library directory. "
        "Defaults to the directory saved by the last 'init', "
        f"or '{_DEFAULT_LIBRARY_DIR}' if none was saved."
    ),
    type=click.Path(),
)
@click.pass_context
def cli(ctx: click.Context, library_dir: str) -> None:
    """liber – academic literature management system.

    Manages a directory of academic papers, each in its own sub-directory
    containing a PDF, a BibTeX file, and optional Markdown notes.

    The library directory can be set with the --library-dir option or the
    LIBER_DIR environment variable.  When neither is provided liber uses the
    directory saved during the last ``init`` run, falling back to the default
    of ~/liber.
    """
    ctx.ensure_object(dict)
    if library_dir is None:
        saved = _read_saved_library_dir()
        resolved = saved if saved is not None else _DEFAULT_LIBRARY_DIR
    else:
        resolved = Path(library_dir)
    ctx.obj["library_dir"] = resolved


# ---------------------------------------------------------------------------
# init
# ---------------------------------------------------------------------------


@cli.command("init")
@click.pass_context
def init_cmd(ctx: click.Context) -> None:
    """Initialise a new library directory."""
    lib = _get_library(ctx)
    lib.init()
    _save_library_dir(ctx.obj["library_dir"])
    click.echo(f"Library initialised at: {lib.library_dir}")


# ---------------------------------------------------------------------------
# add
# ---------------------------------------------------------------------------


@cli.command("add")
@click.argument("bib", type=click.Path(exists=True, dir_okay=False))
@click.option(
    "--pdf",
    default=None,
    type=click.Path(exists=True, dir_okay=False),
    help="Path to the PDF file to import (optional).",
)
@click.option(
    "--key",
    default=None,
    help="Override the auto-generated citation key.",
)
@click.pass_context
def add_cmd(
    ctx: click.Context,
    bib: str,
    pdf: Optional[str],
    key: Optional[str],
) -> None:
    """Add a paper to the library.

    BIB is the path to the existing BibTeX file for the paper. A PDF can
    optionally be provided via --pdf.

    Metadata (title, year, authors, keywords, doi) is extracted from the bib
    file.  The citation key is rewritten to the author-year-title format; all
    other BibTeX fields are preserved unchanged.

    Example:

    \b
        liber add paper.bib
        liber add paper.bib --pdf paper.pdf
        liber add paper.bib --key lecun2015deep
    """
    lib = _get_library(ctx)
    lib.init()
    try:
        paper = lib.add(
            bib_path=Path(bib),
            pdf_path=Path(pdf) if pdf else None,
            citation_key=key,
        )
    except (FileExistsError, FileNotFoundError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc

    click.echo(f"Added paper '{paper.citation_key}'.")
    click.echo(f"  Directory : {lib.library_dir / paper.citation_key}")
    click.echo(f"  BibTeX key: {paper.citation_key}")


# ---------------------------------------------------------------------------
# add-pdf
# ---------------------------------------------------------------------------


@cli.command("add-pdf")
@click.argument("citation_key")
@click.argument("pdf", type=click.Path(exists=True, dir_okay=False))
@click.pass_context
def add_pdf_cmd(ctx: click.Context, citation_key: str, pdf: str) -> None:
    """Add or replace the PDF for an existing paper.

    CITATION_KEY is the key of the paper already in the library.
    PDF is the path to the PDF file to import.

    Example:

    \b
        liber add-pdf vaswani2017attention paper.pdf
    """
    lib = _get_library(ctx)
    try:
        lib.add_pdf(citation_key, Path(pdf))
    except (KeyError, FileNotFoundError) as exc:
        raise click.ClickException(str(exc)) from exc

    click.echo(f"PDF added for '{citation_key}'.")


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
@click.option("--tag", default=None, help="Filter by exact tag name.")
@click.pass_context
def search_cmd(
    ctx: click.Context,
    title: Optional[str],
    author: Optional[str],
    year: Optional[int],
    keyword: Optional[str],
    tag: Optional[str],
) -> None:
    """Search papers in the library.

    Multiple filters are combined with AND logic.

    Example:

    \b
        liber search --keyword transformers
        liber search --author Vaswani --year 2017
        liber search --tag "machine learning"
    """
    if all(v is None for v in (title, author, year, keyword, tag)):
        raise click.UsageError(
            "Provide at least one of --title, --author, --year, --keyword, --tag."
        )

    lib = _get_library(ctx)
    papers = lib.search(title=title, author=author, year=year, keyword=keyword, tag=tag)

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
    pdf_path = lib.pdf_path(citation_key)

    click.echo(f"Citation key : {paper.citation_key}")
    click.echo(f"Title        : {paper.title}")
    click.echo(f"Year         : {paper.year}")
    click.echo(f"Authors      : {'; '.join(paper.authors)}")
    click.echo(f"Keywords     : {', '.join(paper.keywords)}")
    click.echo(f"Tags         : {', '.join(paper.tags) if paper.tags else '—'}")
    click.echo(f"DOI          : {paper.doi or '—'}")
    click.echo(f"PDF          : {pdf_path} ({'exists' if pdf_path.exists() else 'not present'})")
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


# ---------------------------------------------------------------------------
# rename-key
# ---------------------------------------------------------------------------


@cli.command("rename-key")
@click.argument("citation_key")
@click.argument("new_key")
@click.pass_context
def rename_key_cmd(ctx: click.Context, citation_key: str, new_key: str) -> None:
    """Rename the citation key of a paper.

    CITATION_KEY is the current key; NEW_KEY is the desired replacement.
    All files in the paper's directory are renamed accordingly and the
    BibTeX entry is updated in place.

    Example:

    \b
        liber rename-key oldkey2020foo newkey2020foo
    """
    lib = _get_library(ctx)
    try:
        paper = lib.rename_key(citation_key, new_key)
    except KeyError as exc:
        raise click.ClickException(str(exc)) from exc
    except (FileExistsError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc

    click.echo(f"Citation key renamed: '{citation_key}' → '{paper.citation_key}'.")


# ---------------------------------------------------------------------------
# edit-bibtex
# ---------------------------------------------------------------------------


@cli.command("edit-bibtex")
@click.argument("citation_key")
@click.pass_context
def edit_bibtex_cmd(ctx: click.Context, citation_key: str) -> None:
    """Edit the BibTeX entry for a paper in $EDITOR.

    Opens the current BibTeX entry in $EDITOR (default: nano).  After saving
    and closing the editor the index is updated from the new content.

    Example:

    \b
        liber edit-bibtex vaswani2017attention
    """
    lib = _get_library(ctx)
    try:
        bib_file = lib.bib_path(citation_key)
    except KeyError as exc:
        raise click.ClickException(str(exc)) from exc

    current_bib = bib_file.read_text(encoding="utf-8") if bib_file.exists() else ""

    # Write current content to a temporary file for editing
    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".bib",
        prefix=f"{citation_key}_",
        delete=False,
        encoding="utf-8",
    ) as tmp:
        tmp.write(current_bib)
        tmp_path = Path(tmp.name)

    try:
        editor = os.environ.get("EDITOR", "nano")
        subprocess.run([editor, str(tmp_path)], check=False)
        new_bib_text = tmp_path.read_text(encoding="utf-8")
    finally:
        tmp_path.unlink(missing_ok=True)

    if new_bib_text == current_bib:
        click.echo("No changes made.")
        return

    try:
        lib.update_bibtex(citation_key, new_bib_text)
    except (KeyError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc

    click.echo(f"BibTeX entry updated for '{citation_key}'.")


# ---------------------------------------------------------------------------
# tag (sub-group)
# ---------------------------------------------------------------------------


@cli.group("tag")
@click.pass_context
def tag_group(ctx: click.Context) -> None:
    """Manage tags for the library and individual papers.

    Tags are short labels (letters, digits, spaces, hyphens, underscores) that
    can be assigned to papers for organisation.

    Examples:

    \b
        liber tag list
        liber tag create "machine learning"
        liber tag delete "machine learning"
        liber tag add vaswani2017attention transformers
        liber tag remove vaswani2017attention transformers
    """


@tag_group.command("list")
@click.pass_context
def tag_list_cmd(ctx: click.Context) -> None:
    """List all tags in the library."""
    lib = _get_library(ctx)
    tags = lib.list_tags()
    if not tags:
        click.echo("No tags defined.")
        return
    for tag in tags:
        click.echo(tag)


@tag_group.command("create")
@click.argument("tag")
@click.pass_context
def tag_create_cmd(ctx: click.Context, tag: str) -> None:
    """Create a new tag named TAG.

    TAG may contain letters, digits, spaces, hyphens, and underscores.

    Example:

    \b
        liber tag create "machine learning"
    """
    lib = _get_library(ctx)
    try:
        lib.create_tag(tag)
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(f"Tag '{tag}' created.")


@tag_group.command("delete")
@click.argument("tag")
@click.confirmation_option(prompt="This will remove the tag from all papers. Continue?")
@click.pass_context
def tag_delete_cmd(ctx: click.Context, tag: str) -> None:
    """Delete the tag named TAG from the library and all papers.

    Example:

    \b
        liber tag delete "machine learning"
    """
    lib = _get_library(ctx)
    try:
        lib.delete_tag(tag)
    except KeyError as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(f"Tag '{tag}' deleted.")


@tag_group.command("add")
@click.argument("citation_key")
@click.argument("tag")
@click.pass_context
def tag_add_cmd(ctx: click.Context, citation_key: str, tag: str) -> None:
    """Assign TAG to the paper identified by CITATION_KEY.

    If TAG does not yet exist it is created automatically.

    Example:

    \b
        liber tag add vaswani2017attention transformers
    """
    lib = _get_library(ctx)
    try:
        lib.add_paper_tag(citation_key, tag)
    except KeyError as exc:
        raise click.ClickException(str(exc)) from exc
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(f"Tag '{tag}' added to '{citation_key}'.")


@tag_group.command("remove")
@click.argument("citation_key")
@click.argument("tag")
@click.pass_context
def tag_remove_cmd(ctx: click.Context, citation_key: str, tag: str) -> None:
    """Remove TAG from the paper identified by CITATION_KEY.

    The tag is kept in the global registry; only the assignment is removed.

    Example:

    \b
        liber tag remove vaswani2017attention transformers
    """
    lib = _get_library(ctx)
    try:
        lib.remove_paper_tag(citation_key, tag)
    except KeyError as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(f"Tag '{tag}' removed from '{citation_key}'.")


# ---------------------------------------------------------------------------
# export
# ---------------------------------------------------------------------------


@cli.command("export")
@click.option("--output", "-o", default=None, type=click.Path(dir_okay=False),
              help="Write output to FILE instead of stdout.")
@click.option("--title", "-t", default=None, help="Filter by title substring.")
@click.option("--author", "-a", default=None, help="Filter by author substring.")
@click.option("--year", "-y", default=None, type=int, help="Filter by exact year.")
@click.option("--keyword", "-k", default=None, help="Filter by keyword substring.")
@click.option("--tag", default=None, help="Filter by exact tag name.")
@click.pass_context
def export_cmd(
    ctx: click.Context,
    output: Optional[str],
    title: Optional[str],
    author: Optional[str],
    year: Optional[int],
    keyword: Optional[str],
    tag: Optional[str],
) -> None:
    """Export bibliographies as a BibTeX file.

    Without filters all papers are exported.  Supply one or more filters to
    export a subset (filters are combined with AND logic).  The result is
    written to stdout or to a file with --output.

    Example:

    \b
        liber export                                  # all papers → stdout
        liber export --output bibliography.bib        # all papers → file
        liber export --tag transformers -o subset.bib # filtered export
        liber export --author Vaswani --year 2017
    """
    lib = _get_library(ctx)
    has_filters = any(v is not None for v in (title, author, year, keyword, tag))
    if has_filters:
        papers = lib.search(title=title, author=author, year=year, keyword=keyword, tag=tag)
    else:
        papers = lib.list_papers()

    entries: list[str] = []
    for paper in papers:
        bib_file = lib.bib_path(paper.citation_key)
        if bib_file.exists():
            entries.append(bib_file.read_text(encoding="utf-8").strip())
        else:
            entries.append(paper.to_bibtex().strip())

    bib_content = "\n\n".join(entries)

    if output:
        Path(output).write_text(bib_content, encoding="utf-8")
        click.echo(f"Exported {len(papers)} paper(s) to '{output}'.")
    else:
        click.echo(bib_content)


# ---------------------------------------------------------------------------
# delete-pdf
# ---------------------------------------------------------------------------


@cli.command("delete-pdf")
@click.argument("citation_key")
@click.confirmation_option(prompt="Are you sure you want to delete the PDF?")
@click.pass_context
def delete_pdf_cmd(ctx: click.Context, citation_key: str) -> None:
    """Delete the PDF file for the paper identified by CITATION_KEY.

    The paper entry and BibTeX file are kept; only the PDF is removed.

    Example:

    \b
        liber delete-pdf vaswani2017attention
    """
    lib = _get_library(ctx)
    try:
        lib.delete_pdf(citation_key)
    except KeyError as exc:
        raise click.ClickException(str(exc)) from exc
    except FileNotFoundError as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(f"PDF deleted for '{citation_key}'.")


# ---------------------------------------------------------------------------
# serve
# ---------------------------------------------------------------------------


@cli.command("serve")
@click.option("--host", default="127.0.0.1", show_default=True, help="Host to bind to.")
@click.option("--port", "-p", default=5000, show_default=True, type=int, help="Port to listen on.")
@click.option("--debug", is_flag=True, default=False, help="Enable Flask debug mode.")
@click.pass_context
def serve_cmd(ctx: click.Context, host: str, port: int, debug: bool) -> None:
    """Start the liber web interface.

    Opens a locally hosted website for browsing and managing your library.

    Example:

    \b
        liber serve
        liber serve --port 8080
        liber --library-dir /path/to/lib serve
    """
    from liber.web import create_app  # noqa: PLC0415

    library_dir = ctx.obj["library_dir"]
    app = create_app(library_dir=library_dir)
    click.echo(f"Starting liber web interface at http://{host}:{port}")
    click.echo(f"Library directory: {library_dir}")
    click.echo("Press Ctrl+C to stop.")
    app.run(host=host, port=port, debug=debug)
