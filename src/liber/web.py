"""Flask web interface for liber."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Optional

from flask import (
    Flask,
    abort,
    flash,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)

from liber.library import Library

_DEFAULT_LIBRARY_DIR = Path.home() / "liber"
_LIBER_DIR_ENV = "LIBER_DIR"


def create_app(library_dir: Optional[Path] = None) -> Flask:
    """Create and configure the Flask application.

    Args:
        library_dir: Path to the liber library directory.  Falls back to the
            ``LIBER_DIR`` environment variable and then ``~/liber``.
    """
    template_folder = Path(__file__).parent / "templates"
    app = Flask(__name__, template_folder=str(template_folder))

    if library_dir is None:
        library_dir = Path(
            os.environ.get(_LIBER_DIR_ENV, str(_DEFAULT_LIBRARY_DIR))
        )

    lib = Library(library_dir)
    lib.init()

    # Load or generate a persistent secret key stored in the library directory
    secret_key_path = lib.library_dir / ".liber_secret_key"
    if secret_key_path.exists():
        app.secret_key = secret_key_path.read_bytes()
    else:
        key = os.urandom(24)
        secret_key_path.write_bytes(key)
        app.secret_key = key

    # ------------------------------------------------------------------
    # Routes
    # ------------------------------------------------------------------

    @app.route("/")
    def index():
        papers = lib.list_papers()
        return render_template("index.html", papers=papers)

    @app.route("/search")
    def search():
        title = request.args.get("title") or None
        author = request.args.get("author") or None
        year_str = request.args.get("year") or None
        keyword = request.args.get("keyword") or None

        searched = any(v is not None for v in (title, author, year_str, keyword))
        papers = []
        if searched:
            year: Optional[int] = None
            if year_str is not None:
                try:
                    year = int(year_str)
                except ValueError:
                    flash("Year must be a number.", "error")
                    return render_template("search.html", papers=[], searched=False)
            papers = lib.search(title=title, author=author, year=year, keyword=keyword)

        return render_template("search.html", papers=papers, searched=searched)

    @app.route("/paper/<citation_key>")
    def paper_detail(citation_key: str):
        try:
            paper = lib.get(citation_key)
        except KeyError:
            abort(404)

        bibtex = paper.to_bibtex()

        notes_path = lib.notes_path(citation_key)
        notes_content = notes_path.read_text(encoding="utf-8") if notes_path.exists() else None

        return render_template(
            "paper.html",
            paper=paper,
            bibtex=bibtex,
            notes_content=notes_content,
        )

    @app.route("/paper/<citation_key>/pdf")
    def paper_pdf(citation_key: str):
        try:
            lib.get(citation_key)
        except KeyError:
            abort(404)

        pdf_path = lib.library_dir / citation_key / f"{citation_key}.pdf"
        if not pdf_path.exists():
            abort(404)

        return send_file(pdf_path, mimetype="application/pdf")

    @app.route("/paper/<citation_key>/notes", methods=["GET", "POST"])
    def paper_notes(citation_key: str):
        try:
            paper = lib.get(citation_key)
        except KeyError:
            abort(404)

        notes_path = lib.notes_path(citation_key)

        if request.method == "POST":
            content = request.form.get("notes", "")
            notes_path.write_text(content, encoding="utf-8")
            flash("Notes saved.", "success")
            return redirect(url_for("paper_detail", citation_key=citation_key))

        notes_content = notes_path.read_text(encoding="utf-8") if notes_path.exists() else (
            f"# Notes: {paper.title} ({paper.year})\n\n"
        )
        return render_template("notes.html", paper=paper, notes_content=notes_content)

    @app.route("/paper/<citation_key>/remove", methods=["POST"])
    def paper_remove(citation_key: str):
        try:
            paper = lib.remove(citation_key, delete_files=True)
        except KeyError:
            abort(404)

        flash(f"Paper '{paper.citation_key}' removed.", "success")
        return redirect(url_for("index"))

    @app.route("/add", methods=["GET", "POST"])
    def add():
        if request.method == "GET":
            return render_template("add.html")

        pdf_file = request.files.get("pdf")
        bib_file = request.files.get("bib")
        key = request.form.get("key") or None

        if not pdf_file or not pdf_file.filename:
            flash("Please select a PDF file.", "error")
            return render_template("add.html")
        if not bib_file or not bib_file.filename:
            flash("Please select a BibTeX (.bib) file.", "error")
            return render_template("add.html")

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            pdf_path = tmp / "upload.pdf"
            bib_path = tmp / "upload.bib"
            pdf_file.save(str(pdf_path))
            bib_file.save(str(bib_path))

            # Basic content validation: PDFs must start with the %PDF magic bytes
            with pdf_path.open("rb") as fh:
                header = fh.read(4)
            if header != b"%PDF":
                flash("The uploaded file does not appear to be a valid PDF.", "error")
                return render_template("add.html")

            try:
                paper = lib.add(pdf_path=pdf_path, bib_path=bib_path, citation_key=key)
            except (FileExistsError, FileNotFoundError, ValueError) as exc:
                flash(str(exc), "error")
                return render_template("add.html")

        flash(f"Paper '{paper.citation_key}' added successfully.", "success")
        return redirect(url_for("paper_detail", citation_key=paper.citation_key))

    return app
