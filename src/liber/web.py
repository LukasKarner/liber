"""Flask web interface for liber."""

from __future__ import annotations

import os
import ipaddress
import socket
import tempfile
import urllib.error
import urllib.parse
import urllib.request
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


_PDF_DOWNLOAD_MAX_BYTES = 50 * 1024 * 1024  # 50 MB
_PDF_DOWNLOAD_CHUNK_SIZE = 64 * 1024  # 64 KB


def _is_safe_url(url: str) -> bool:
    """Return True if *url* is a safe http/https URL pointing to a public host.

    Resolves the hostname via :func:`socket.getaddrinfo` (covering both IPv4
    and IPv6) and rejects loopback, private, link-local, or reserved addresses
    to mitigate SSRF risks.

    Note: DNS rebinding (TOCTOU) is a residual risk because
    ``urllib.request.urlopen`` performs its own resolution after this check.
    This function reduces exposure but is not a complete defence against a
    targeted DNS-rebinding attack.
    """
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return False
    hostname = parsed.hostname
    if not hostname:
        return False
    try:
        addrinfos = socket.getaddrinfo(hostname, None)
    except socket.gaierror:
        return False
    if not addrinfos:
        return False
    for _family, _type, _proto, _canonname, sockaddr in addrinfos:
        addr_str = sockaddr[0]
        try:
            addr = ipaddress.ip_address(addr_str)
        except ValueError:
            return False
        if (
            addr.is_loopback
            or addr.is_private
            or addr.is_link_local
            or addr.is_reserved
        ):
            return False
    return True


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

        bib_file = lib.bib_path(citation_key)
        bibtex = bib_file.read_text(encoding="utf-8") if bib_file.exists() else paper.to_bibtex()

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

    @app.route("/paper/<citation_key>/rename", methods=["POST"])
    def paper_rename(citation_key: str):
        new_key = (request.form.get("new_key") or "").strip()
        if not new_key:
            flash("Please enter a new citation key.", "error")
            return redirect(url_for("paper_detail", citation_key=citation_key))
        try:
            paper = lib.rename_key(citation_key, new_key)
        except KeyError:
            abort(404)
        except (FileExistsError, ValueError) as exc:
            flash(str(exc), "error")
            return redirect(url_for("paper_detail", citation_key=citation_key))
        flash(f"Citation key renamed to '{paper.citation_key}'.", "success")
        return redirect(url_for("paper_detail", citation_key=paper.citation_key))

    @app.route("/paper/<citation_key>/edit_bibtex", methods=["GET", "POST"])
    def paper_edit_bibtex(citation_key: str):
        try:
            paper = lib.get(citation_key)
        except KeyError:
            abort(404)

        bib_file = lib.bib_path(citation_key)
        current_bib = bib_file.read_text(encoding="utf-8") if bib_file.exists() else paper.to_bibtex()

        if request.method == "POST":
            new_bib_text = request.form.get("bibtex", "")
            try:
                lib.update_bibtex(citation_key, new_bib_text)
            except (ValueError, KeyError) as exc:
                flash(str(exc), "error")
                return render_template(
                    "edit_bibtex.html",
                    paper=paper,
                    bibtex=new_bib_text,
                )
            flash("BibTeX entry updated.", "success")
            return redirect(url_for("paper_detail", citation_key=citation_key))

        return render_template("edit_bibtex.html", paper=paper, bibtex=current_bib)

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
        pdf_url = (request.form.get("pdf_url") or "").strip()
        bib_file = request.files.get("bib")
        bib_text = (request.form.get("bib_text") or "").strip()
        key = request.form.get("key") or None

        has_pdf_file = pdf_file and pdf_file.filename
        if not has_pdf_file and not pdf_url:
            flash("Please select a PDF file or provide a URL to a PDF.", "error")
            return render_template("add.html")

        has_bib_file = bib_file and bib_file.filename
        if not has_bib_file and not bib_text:
            flash("Please select a BibTeX (.bib) file or paste a BibTeX entry.", "error")
            return render_template("add.html")

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            pdf_path = tmp / "upload.pdf"
            bib_path = tmp / "upload.bib"

            if has_pdf_file:
                pdf_file.save(str(pdf_path))
            else:
                # Validate and download from URL
                if not _is_safe_url(pdf_url):
                    flash(
                        "PDF URL must use http or https and point to a public host.",
                        "error",
                    )
                    return render_template("add.html")
                try:
                    with urllib.request.urlopen(pdf_url, timeout=30) as resp:  # noqa: S310
                        chunks: list[bytes] = []
                        total = 0
                        while True:
                            chunk = resp.read(_PDF_DOWNLOAD_CHUNK_SIZE)
                            if not chunk:
                                break
                            total += len(chunk)
                            if total > _PDF_DOWNLOAD_MAX_BYTES:
                                flash(
                                    "The PDF at the provided URL exceeds the"
                                    " maximum allowed size (50 MB).",
                                    "error",
                                )
                                return render_template("add.html")
                            chunks.append(chunk)
                    pdf_path.write_bytes(b"".join(chunks))
                except urllib.error.URLError as exc:
                    flash(f"Failed to download PDF: {exc}", "error")
                    return render_template("add.html")

            # Basic content validation: PDFs must start with the %PDF magic bytes
            with pdf_path.open("rb") as fh:
                header = fh.read(4)
            if header != b"%PDF":
                flash("The file does not appear to be a valid PDF.", "error")
                return render_template("add.html")

            if has_bib_file:
                bib_file.save(str(bib_path))
            else:
                bib_path.write_text(bib_text, encoding="utf-8")

            try:
                paper = lib.add(pdf_path=pdf_path, bib_path=bib_path, citation_key=key)
            except (FileExistsError, FileNotFoundError, ValueError) as exc:
                flash(str(exc), "error")
                return render_template("add.html")

        flash(f"Paper '{paper.citation_key}' added successfully.", "success")
        return redirect(url_for("paper_detail", citation_key=paper.citation_key))

    return app
