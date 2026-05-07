"""Tests for the Flask web interface."""

from __future__ import annotations

import io
import ipaddress
import socket
from pathlib import Path
from unittest.mock import patch

from liber.library import Library
from liber.web import _is_safe_url, create_app
from tests.conftest import make_bib


def _seed_library(tmp_path: Path) -> Path:
    """Create a temporary library with a few papers and return its path."""
    lib_dir = tmp_path / "weblib"
    lib = Library(lib_dir)
    lib.init()

    pdf = tmp_path / "paper.pdf"
    pdf.write_bytes(b"%PDF-1.4 test content")

    bib1 = make_bib(
        tmp_path,
        "alpha.bib",
        "Alpha Study",
        2019,
        ["Doe, Jane"],
        ["vision"],
    )
    bib2 = make_bib(
        tmp_path,
        "beta.bib",
        "Beta Models",
        2022,
        ["Smith, John"],
        ["nlp", "transformers"],
    )
    bib3 = make_bib(
        tmp_path,
        "gamma.bib",
        "Gamma Networks",
        2020,
        ["Roe, Alex"],
        ["rl"],
    )

    lib.add(bib_path=bib1, pdf_path=pdf)
    lib.add(bib_path=bib2, pdf_path=pdf)
    lib.add(bib_path=bib3, pdf_path=pdf)

    return lib_dir


def _client_for_library(library_dir: Path):
    app = create_app(library_dir)
    return app.test_client()


def test_index_shows_filter_pane_fields(tmp_path: Path):
    client = _client_for_library(_seed_library(tmp_path))

    response = client.get("/")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Filter Papers" in html
    assert 'name="title"' in html
    assert 'name="author"' in html
    assert 'name="year"' in html
    assert 'name="keyword"' in html
    assert "Clear Filters" in html


def test_index_filters_without_leaving_page(tmp_path: Path):
    client = _client_for_library(_seed_library(tmp_path))

    response = client.get("/?title=beta")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Beta Models" in html
    assert "Alpha Study" not in html
    assert "Gamma Networks" not in html


def test_index_sorting_by_column(tmp_path: Path):
    client = _client_for_library(_seed_library(tmp_path))

    response = client.get("/?sort_by=title&sort_dir=asc")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert html.index("Alpha Study") < html.index("Beta Models") < html.index("Gamma Networks")


def test_index_invalid_year_shows_error_and_unfiltered_results(tmp_path: Path):
    client = _client_for_library(_seed_library(tmp_path))

    response = client.get("/?year=not-a-number")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Year must be a number." in html
    assert "Alpha Study" in html
    assert "Beta Models" in html
    assert "Gamma Networks" in html


def test_search_route_redirects_to_index_with_params(tmp_path: Path):
    client = _client_for_library(_seed_library(tmp_path))

    response = client.get("/search?author=smith", follow_redirects=False)

    assert response.status_code == 302
    assert response.headers["Location"] == "/?author=smith"


def _seed_library_no_pdf(tmp_path: Path) -> tuple[Path, str]:
    """Create a library with one paper without a PDF; return (lib_dir, citation_key)."""
    lib_dir = tmp_path / "nopdflib"
    lib = Library(lib_dir)
    lib.init()
    bib = make_bib(tmp_path, "nopdf.bib", "No PDF Paper", 2024, ["Author, A"], ["test"])
    paper = lib.add(bib_path=bib)
    return lib_dir, paper.citation_key


def test_paper_detail_shows_view_pdf_when_pdf_exists(tmp_path: Path):
    client = _client_for_library(_seed_library(tmp_path))

    # Get any paper key from the seeded library
    lib = Library(tmp_path / "weblib")
    key = lib.list_papers()[0].citation_key

    response = client.get(f"/paper/{key}")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "View PDF" in html
    assert "Add PDF" not in html


def test_paper_detail_shows_add_pdf_when_no_pdf(tmp_path: Path):
    lib_dir, key = _seed_library_no_pdf(tmp_path)
    client = _client_for_library(lib_dir)

    response = client.get(f"/paper/{key}")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Add PDF" in html
    assert "View PDF" not in html


def test_add_paper_without_pdf_succeeds(tmp_path: Path):
    lib_dir = tmp_path / "addlib"
    client = _client_for_library(lib_dir)

    bib_content = (
        "@article{test2024paper,\n"
        "  title  = {Test Paper},\n"
        "  author = {Tester, A},\n"
        "  year   = {2024},\n"
        "}\n"
    )

    response = client.post(
        "/add",
        data={"bib_text": bib_content},
        follow_redirects=True,
    )
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Test Paper" in html


def test_add_pdf_route_get(tmp_path: Path):
    lib_dir, key = _seed_library_no_pdf(tmp_path)
    client = _client_for_library(lib_dir)

    response = client.get(f"/paper/{key}/add_pdf")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Add PDF" in html
    assert 'name="pdf"' in html
    assert 'name="pdf_url"' in html


def test_add_pdf_route_post_file(tmp_path: Path):
    import io

    lib_dir, key = _seed_library_no_pdf(tmp_path)
    client = _client_for_library(lib_dir)

    pdf_bytes = b"%PDF-1.4 test"
    response = client.post(
        f"/paper/{key}/add_pdf",
        data={"pdf": (io.BytesIO(pdf_bytes), "paper.pdf")},
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "PDF added successfully" in html

    # Verify the PDF file was actually created
    lib = Library(lib_dir)
    assert lib.pdf_path(key).exists()


def test_add_pdf_route_missing_input_shows_error(tmp_path: Path):
    lib_dir, key = _seed_library_no_pdf(tmp_path)
    client = _client_for_library(lib_dir)

    response = client.post(f"/paper/{key}/add_pdf", data={}, follow_redirects=True)
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Please select a PDF file" in html


# ---------------------------------------------------------------------------
# Tag management routes
# ---------------------------------------------------------------------------


def test_index_shows_tags_pane(tmp_path: Path):
    client = _client_for_library(_seed_library(tmp_path))

    response = client.get("/")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Tags" in html
    assert 'name="tag"' in html


def test_tag_create_and_appears_in_index(tmp_path: Path):
    client = _client_for_library(_seed_library(tmp_path))

    response = client.post("/tags/create", data={"tag": "survey"}, follow_redirects=True)
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "survey" in html


def test_tag_create_empty_shows_error(tmp_path: Path):
    client = _client_for_library(_seed_library(tmp_path))

    response = client.post("/tags/create", data={"tag": ""}, follow_redirects=True)
    html = response.get_data(as_text=True)

    assert "Please enter a tag name" in html


def test_tag_delete(tmp_path: Path):
    lib_dir = _seed_library(tmp_path)
    lib = Library(lib_dir)
    lib.create_tag("to-delete")
    client = _client_for_library(lib_dir)

    response = client.post("/tags/delete", data={"tag": "to-delete"}, follow_redirects=True)

    assert response.status_code == 200
    assert "to-delete" not in lib.list_tags()


def test_paper_tag_add(tmp_path: Path):
    lib_dir = _seed_library(tmp_path)
    lib = Library(lib_dir)
    key = lib.list_papers()[0].citation_key
    client = _client_for_library(lib_dir)

    response = client.post(
        f"/paper/{key}/tags/add",
        data={"tag": "my-tag"},
        follow_redirects=True,
    )
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "my-tag" in html
    assert "my-tag" in lib.get(key).tags


def test_paper_tag_remove(tmp_path: Path):
    lib_dir = _seed_library(tmp_path)
    lib = Library(lib_dir)
    key = lib.list_papers()[0].citation_key
    lib.add_paper_tag(key, "remove-me")
    client = _client_for_library(lib_dir)

    response = client.post(
        f"/paper/{key}/tags/remove",
        data={"tag": "remove-me"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert "remove-me" not in lib.get(key).tags


def test_index_filter_by_tag(tmp_path: Path):
    lib_dir = _seed_library(tmp_path)
    lib = Library(lib_dir)
    papers = lib.list_papers()
    lib.add_paper_tag(papers[0].citation_key, "special")
    client = _client_for_library(lib_dir)

    response = client.get("/?tag=special")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert papers[0].title in html
    assert papers[1].title not in html


# ---------------------------------------------------------------------------
# Export bibliography route
# ---------------------------------------------------------------------------


def test_export_bib_returns_bib_file(tmp_path: Path):
    client = _client_for_library(_seed_library(tmp_path))

    response = client.get("/export_bib")

    assert response.status_code == 200
    assert response.content_type.startswith("text/plain")
    assert "bibliography.bib" in response.headers.get("Content-Disposition", "")
    content = response.get_data(as_text=True)
    # All three papers should be in the export
    assert "@" in content  # at least one BibTeX entry
    assert "Alpha Study" in content
    assert "Beta Models" in content
    assert "Gamma Networks" in content


def test_export_bib_respects_filters(tmp_path: Path):
    client = _client_for_library(_seed_library(tmp_path))

    response = client.get("/export_bib?title=beta")

    assert response.status_code == 200
    content = response.get_data(as_text=True)
    assert "Beta Models" in content
    assert "Alpha Study" not in content
    assert "Gamma Networks" not in content


# ---------------------------------------------------------------------------
# Delete PDF route
# ---------------------------------------------------------------------------


def test_delete_pdf_removes_file(tmp_path: Path):
    lib_dir = _seed_library(tmp_path)
    lib = Library(lib_dir)
    key = lib.list_papers()[0].citation_key
    client = _client_for_library(lib_dir)

    assert lib.pdf_path(key).exists()

    response = client.post(f"/paper/{key}/delete_pdf", follow_redirects=True)
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "PDF deleted" in html
    assert not lib.pdf_path(key).exists()


def test_delete_pdf_when_no_pdf_shows_error(tmp_path: Path):
    lib_dir, key = _seed_library_no_pdf(tmp_path)
    client = _client_for_library(lib_dir)

    response = client.post(f"/paper/{key}/delete_pdf", follow_redirects=True)
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "No PDF file found to delete" in html


def test_delete_pdf_unknown_key_returns_404(tmp_path: Path):
    client = _client_for_library(_seed_library(tmp_path))

    response = client.post("/paper/doesnotexist/delete_pdf")

    assert response.status_code == 404


def test_paper_detail_shows_delete_pdf_only_when_pdf_exists(tmp_path: Path):
    lib_dir = _seed_library(tmp_path)
    lib = Library(lib_dir)
    key = lib.list_papers()[0].citation_key
    client = _client_for_library(lib_dir)

    # With PDF: should show Delete PDF button
    response = client.get(f"/paper/{key}")
    html = response.get_data(as_text=True)
    assert "Delete PDF" in html

    # Delete the PDF then check again
    lib.delete_pdf(key)
    response2 = client.get(f"/paper/{key}")
    html2 = response2.get_data(as_text=True)
    assert "Delete PDF" not in html2


# ---------------------------------------------------------------------------
# Markdown notes rendering
# ---------------------------------------------------------------------------


def test_paper_detail_renders_markdown_notes(tmp_path: Path):
    lib_dir = _seed_library(tmp_path)
    lib = Library(lib_dir)
    key = lib.list_papers()[0].citation_key
    notes_path = lib.notes_path(key)
    notes_path.write_text("# My Heading\n\nSome **bold** text.", encoding="utf-8")
    client = _client_for_library(lib_dir)

    response = client.get(f"/paper/{key}")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "<h1>My Heading</h1>" in html
    assert "<strong>bold</strong>" in html
    # Raw markdown should not appear in a pre block
    assert "# My Heading" not in html


def test_paper_detail_sanitizes_markdown_html(tmp_path: Path):
    lib_dir = _seed_library(tmp_path)
    lib = Library(lib_dir)
    key = lib.list_papers()[0].citation_key
    lib.notes_path(key).write_text(
        "<script>alert('xss')</script>\n\n[click](javascript:alert(1))",
        encoding="utf-8",
    )
    client = _client_for_library(lib_dir)

    response = client.get(f"/paper/{key}")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "<script>" not in html
    assert 'href="javascript:alert(1)"' not in html


def test_add_rejects_pdf_url_for_security(tmp_path: Path):
    lib_dir = tmp_path / "addlib-url-disabled"
    client = _client_for_library(lib_dir)

    bib_content = (
        "@article{test2024paper,\n"
        "  title  = {Test Paper},\n"
        "  author = {Tester, A},\n"
        "  year   = {2024},\n"
        "}\n"
    )

    response = client.post(
        "/add",
        data={"bib_text": bib_content, "pdf_url": "https://example.com/paper.pdf"},
        follow_redirects=True,
    )
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "importing PDFs from URLs is disabled" in html


def test_add_pdf_rejects_pdf_url_for_security(tmp_path: Path):
    lib_dir, key = _seed_library_no_pdf(tmp_path)
    client = _client_for_library(lib_dir)

    response = client.post(
        f"/paper/{key}/add_pdf",
        data={"pdf_url": "https://example.com/paper.pdf"},
        follow_redirects=True,
    )
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "importing PDFs from URLs is disabled" in html


# ---------------------------------------------------------------------------
# _is_safe_url – SSRF mitigation helper
# ---------------------------------------------------------------------------


class TestIsSafeUrl:
    def test_rejects_non_http_scheme(self):
        assert _is_safe_url("ftp://example.com/file.pdf") is False

    def test_rejects_file_scheme(self):
        assert _is_safe_url("file:///etc/passwd") is False

    def test_rejects_missing_hostname(self):
        assert _is_safe_url("http://") is False

    def test_rejects_unresolvable_host(self):
        with patch("socket.getaddrinfo", side_effect=socket.gaierror):
            assert _is_safe_url("http://this.host.does.not.exist.invalid/") is False

    def test_rejects_loopback_ipv4(self):
        addrinfo = [(socket.AF_INET, None, None, "", ("127.0.0.1", 0))]
        with patch("socket.getaddrinfo", return_value=addrinfo):
            assert _is_safe_url("http://localhost/") is False

    def test_rejects_private_ipv4(self):
        addrinfo = [(socket.AF_INET, None, None, "", ("192.168.1.1", 0))]
        with patch("socket.getaddrinfo", return_value=addrinfo):
            assert _is_safe_url("http://intranet.local/") is False

    def test_rejects_link_local(self):
        addrinfo = [(socket.AF_INET, None, None, "", ("169.254.1.1", 0))]
        with patch("socket.getaddrinfo", return_value=addrinfo):
            assert _is_safe_url("http://link-local.example/") is False

    def test_accepts_public_host(self):
        addrinfo = [(socket.AF_INET, None, None, "", ("93.184.216.34", 0))]
        with patch("socket.getaddrinfo", return_value=addrinfo):
            assert _is_safe_url("https://example.com/paper.pdf") is True

    def test_rejects_ipv6_loopback(self):
        addrinfo = [(socket.AF_INET6, None, None, "", ("::1", 0, 0, 0))]
        with patch("socket.getaddrinfo", return_value=addrinfo):
            assert _is_safe_url("http://ipv6-loopback/") is False

    def test_rejects_empty_addrinfos(self):
        with patch("socket.getaddrinfo", return_value=[]):
            assert _is_safe_url("http://empty-resolve.example/") is False

    def test_rejects_invalid_addr_string(self):
        """ValueError from ipaddress.ip_address causes the URL to be rejected."""
        # sockaddr[0] is not a valid IP string
        addrinfo = [(socket.AF_INET, None, None, "", ("not-an-ip", 0))]
        with patch("socket.getaddrinfo", return_value=addrinfo):
            assert _is_safe_url("http://weird.example/") is False


# ---------------------------------------------------------------------------
# create_app – secret key persistence and env-var fallback
# ---------------------------------------------------------------------------


def test_create_app_reuses_existing_secret_key(tmp_path: Path):
    """Second call to create_app must reuse the persisted secret key file."""
    lib_dir = tmp_path / "sktestlib"
    app1 = create_app(library_dir=lib_dir)
    key1 = app1.secret_key

    app2 = create_app(library_dir=lib_dir)
    key2 = app2.secret_key

    assert key1 == key2


def test_create_app_uses_env_var(tmp_path: Path, monkeypatch):
    """create_app falls back to LIBER_DIR env var when library_dir is None."""
    lib_dir = tmp_path / "envlib"
    monkeypatch.setenv("LIBER_DIR", str(lib_dir))
    app = create_app(library_dir=None)
    assert app is not None


# ---------------------------------------------------------------------------
# Paper PDF route
# ---------------------------------------------------------------------------


def test_paper_pdf_returns_pdf(tmp_path: Path):
    lib_dir = _seed_library(tmp_path)
    lib = Library(lib_dir)
    key = lib.list_papers()[0].citation_key
    client = _client_for_library(lib_dir)

    response = client.get(f"/paper/{key}/pdf")
    assert response.status_code == 200
    assert response.content_type == "application/pdf"


def test_paper_pdf_unknown_key_returns_404(tmp_path: Path):
    client = _client_for_library(_seed_library(tmp_path))
    response = client.get("/paper/ghost2000key/pdf")
    assert response.status_code == 404


def test_paper_pdf_no_pdf_returns_404(tmp_path: Path):
    lib_dir, key = _seed_library_no_pdf(tmp_path)
    client = _client_for_library(lib_dir)
    response = client.get(f"/paper/{key}/pdf")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Paper notes route
# ---------------------------------------------------------------------------


def test_paper_notes_get_returns_form(tmp_path: Path):
    lib_dir = _seed_library(tmp_path)
    lib = Library(lib_dir)
    key = lib.list_papers()[0].citation_key
    client = _client_for_library(lib_dir)

    response = client.get(f"/paper/{key}/notes")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert 'name="notes"' in html


def test_paper_notes_get_returns_existing_content(tmp_path: Path):
    lib_dir = _seed_library(tmp_path)
    lib = Library(lib_dir)
    key = lib.list_papers()[0].citation_key
    lib.notes_path(key).write_text("# Existing notes\n", encoding="utf-8")
    client = _client_for_library(lib_dir)

    response = client.get(f"/paper/{key}/notes")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Existing notes" in html


def test_paper_notes_post_saves_and_redirects(tmp_path: Path):
    lib_dir = _seed_library(tmp_path)
    lib = Library(lib_dir)
    key = lib.list_papers()[0].citation_key
    client = _client_for_library(lib_dir)

    response = client.post(
        f"/paper/{key}/notes",
        data={"notes": "# New notes\n\nSome content."},
        follow_redirects=True,
    )
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Notes saved" in html
    assert lib.notes_path(key).read_text(encoding="utf-8") == "# New notes\n\nSome content."


def test_paper_notes_unknown_key_returns_404(tmp_path: Path):
    client = _client_for_library(_seed_library(tmp_path))
    response = client.get("/paper/ghost2000key/notes")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Paper rename route
# ---------------------------------------------------------------------------


def test_paper_rename_succeeds(tmp_path: Path):
    lib_dir = _seed_library(tmp_path)
    lib = Library(lib_dir)
    key = lib.list_papers()[0].citation_key
    client = _client_for_library(lib_dir)

    response = client.post(
        f"/paper/{key}/rename",
        data={"new_key": "renamed2099test"},
        follow_redirects=True,
    )
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "renamed2099test" in html
    assert lib.get("renamed2099test") is not None


def test_paper_rename_empty_key_flashes_error(tmp_path: Path):
    lib_dir = _seed_library(tmp_path)
    lib = Library(lib_dir)
    key = lib.list_papers()[0].citation_key
    client = _client_for_library(lib_dir)

    response = client.post(
        f"/paper/{key}/rename",
        data={"new_key": ""},
        follow_redirects=True,
    )
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "enter a new citation key" in html.lower()


def test_paper_rename_invalid_key_flashes_error(tmp_path: Path):
    lib_dir = _seed_library(tmp_path)
    lib = Library(lib_dir)
    key = lib.list_papers()[0].citation_key
    client = _client_for_library(lib_dir)

    response = client.post(
        f"/paper/{key}/rename",
        data={"new_key": "invalid key!"},
        follow_redirects=True,
    )
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    # The error flash message should be present
    assert "Invalid" in html or "invalid" in html


def test_paper_rename_duplicate_key_flashes_error(tmp_path: Path):
    lib_dir = _seed_library(tmp_path)
    lib = Library(lib_dir)
    papers = lib.list_papers()
    key_a = papers[0].citation_key
    key_b = papers[1].citation_key
    client = _client_for_library(lib_dir)

    response = client.post(
        f"/paper/{key_a}/rename",
        data={"new_key": key_b},
        follow_redirects=True,
    )
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "already exists" in html


def test_paper_rename_unknown_key_returns_404(tmp_path: Path):
    client = _client_for_library(_seed_library(tmp_path))
    response = client.post("/paper/ghost2000key/rename", data={"new_key": "newkey"})
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Paper edit_bibtex route
# ---------------------------------------------------------------------------


def test_paper_edit_bibtex_get(tmp_path: Path):
    lib_dir = _seed_library(tmp_path)
    lib = Library(lib_dir)
    key = lib.list_papers()[0].citation_key
    client = _client_for_library(lib_dir)

    response = client.get(f"/paper/{key}/edit_bibtex")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert 'name="bibtex"' in html
    assert "@article" in html


def test_paper_edit_bibtex_post_valid(tmp_path: Path):
    lib_dir = _seed_library(tmp_path)
    lib = Library(lib_dir)
    key = lib.list_papers()[0].citation_key
    client = _client_for_library(lib_dir)

    new_bib = (
        f"@article{{{key},\n"
        "  title  = {Updated Via Web},\n"
        "  author = {Web, Author},\n"
        "  year   = {2025},\n"
        "}\n"
    )
    response = client.post(
        f"/paper/{key}/edit_bibtex",
        data={"bibtex": new_bib},
        follow_redirects=True,
    )
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Updated" in html or "updated" in html
    assert lib.get(key).title == "Updated Via Web"


def test_paper_edit_bibtex_post_invalid(tmp_path: Path):
    lib_dir = _seed_library(tmp_path)
    lib = Library(lib_dir)
    key = lib.list_papers()[0].citation_key
    client = _client_for_library(lib_dir)

    response = client.post(
        f"/paper/{key}/edit_bibtex",
        data={"bibtex": "not valid bibtex at all"},
        follow_redirects=True,
    )
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    # Error flash or re-render of form
    assert 'name="bibtex"' in html


def test_paper_edit_bibtex_unknown_key_returns_404(tmp_path: Path):
    client = _client_for_library(_seed_library(tmp_path))
    response = client.get("/paper/ghost2000key/edit_bibtex")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Paper remove route
# ---------------------------------------------------------------------------


def test_paper_remove_redirects_to_index(tmp_path: Path):
    lib_dir = _seed_library(tmp_path)
    lib = Library(lib_dir)
    key = lib.list_papers()[0].citation_key
    client = _client_for_library(lib_dir)

    response = client.post(f"/paper/{key}/remove", follow_redirects=True)
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    # Paper is gone from library
    assert not any(p.citation_key == key for p in lib.list_papers())


def test_paper_remove_unknown_key_returns_404(tmp_path: Path):
    client = _client_for_library(_seed_library(tmp_path))
    response = client.post("/paper/ghost2000key/remove")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Add paper route (/add)
# ---------------------------------------------------------------------------


def test_add_route_get_returns_form(tmp_path: Path):
    client = _client_for_library(tmp_path / "addformlib")
    response = client.get("/add")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert 'name="bib_text"' in html


def test_add_route_post_no_bib_shows_error(tmp_path: Path):
    client = _client_for_library(tmp_path / "addformlib")
    response = client.post("/add", data={}, follow_redirects=True)
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "BibTeX" in html


def test_add_route_post_with_bib_file(tmp_path: Path):
    lib_dir = tmp_path / "addfilelib"
    client = _client_for_library(lib_dir)

    bib_content = (
        "@article{test2025file,\n"
        "  title  = {File Upload Test},\n"
        "  author = {Uploader, A},\n"
        "  year   = {2025},\n"
        "}\n"
    )
    bib_bytes = bib_content.encode("utf-8")

    response = client.post(
        "/add",
        data={"bib": (io.BytesIO(bib_bytes), "test.bib")},
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "File Upload Test" in html or "test2025file" in html


def test_add_route_post_invalid_pdf_shows_error(tmp_path: Path):
    """Uploading a file that is not a real PDF shows an error (line 629-631)."""
    lib_dir = tmp_path / "addpdflib"
    client = _client_for_library(lib_dir)

    bib_content = (
        "@article{test2025pdf,\n"
        "  title  = {PDF Validation Test},\n"
        "  author = {Tester, A},\n"
        "  year   = {2025},\n"
        "}\n"
    )
    # Provide a fake PDF that doesn't start with %PDF
    response = client.post(
        "/add",
        data={
            "bib_text": bib_content,
            "pdf": (io.BytesIO(b"NOT A PDF CONTENT"), "fake.pdf"),
        },
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "does not appear to be a valid PDF" in html


def test_add_route_post_duplicate_key_shows_error(tmp_path: Path):
    """Adding a paper that already exists shows an error (lines 640-642)."""
    lib_dir = tmp_path / "adddupelib"
    client = _client_for_library(lib_dir)

    bib_content = (
        "@article{test2025dupe,\n"
        "  title  = {Duplicate Paper},\n"
        "  author = {Author, A},\n"
        "  year   = {2025},\n"
        "}\n"
    )

    # Add the paper once
    client.post("/add", data={"bib_text": bib_content}, follow_redirects=True)

    # Add the same paper again
    response = client.post(
        "/add", data={"bib_text": bib_content}, follow_redirects=True
    )
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "already exists" in html


def test_add_route_post_unsafe_url_shows_error(tmp_path: Path):
    """An unsafe (private/loopback) PDF URL is rejected (lines 598-603)."""
    lib_dir = tmp_path / "addurlssrf"
    client = _client_for_library(lib_dir)

    bib_content = (
        "@article{test2025ssrf,\n"
        "  title  = {SSRF Test},\n"
        "  author = {Tester, A},\n"
        "  year   = {2025},\n"
        "}\n"
    )

    # localhost should be rejected by _is_safe_url
    response = client.post(
        "/add",
        data={"bib_text": bib_content, "pdf_url": "http://127.0.0.1/secret.pdf"},
        follow_redirects=True,
    )
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "public host" in html


# ---------------------------------------------------------------------------
# Add PDF via URL route
# ---------------------------------------------------------------------------


def test_add_pdf_unknown_key_returns_404(tmp_path: Path):
    client = _client_for_library(_seed_library(tmp_path))
    response = client.get("/paper/ghost2000key/add_pdf")
    assert response.status_code == 404


def test_add_pdf_url_unsafe_shows_error(tmp_path: Path):
    """Providing a loopback PDF URL in add_pdf route is rejected (line 672-677)."""
    lib_dir, key = _seed_library_no_pdf(tmp_path)
    client = _client_for_library(lib_dir)

    response = client.post(
        f"/paper/{key}/add_pdf",
        data={"pdf_url": "http://127.0.0.1/secret.pdf"},
        follow_redirects=True,
    )
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "public host" in html


def test_add_pdf_invalid_file_content_shows_error(tmp_path: Path):
    """Uploading a non-PDF file to add_pdf shows an error (lines 700-704)."""
    lib_dir, key = _seed_library_no_pdf(tmp_path)
    client = _client_for_library(lib_dir)

    response = client.post(
        f"/paper/{key}/add_pdf",
        data={"pdf": (io.BytesIO(b"NOTAPDF"), "fake.pdf")},
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "does not appear to be a valid PDF" in html


# ---------------------------------------------------------------------------
# Export bib – invalid year param
# ---------------------------------------------------------------------------


def test_export_bib_invalid_year_redirects(tmp_path: Path):
    """export_bib with a non-numeric year redirects to index (lines 482-486)."""
    client = _client_for_library(_seed_library(tmp_path))

    response = client.get("/export_bib?year=notanumber", follow_redirects=False)

    # Should redirect to index
    assert response.status_code == 302


# ---------------------------------------------------------------------------
# Index sorting – additional sort columns and invalid sort params
# ---------------------------------------------------------------------------


def test_index_sorting_by_authors(tmp_path: Path):
    client = _client_for_library(_seed_library(tmp_path))

    response = client.get("/?sort_by=authors&sort_dir=asc")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    # All three papers should still appear
    assert "Alpha Study" in html
    assert "Beta Models" in html


def test_index_sorting_by_citation_key(tmp_path: Path):
    client = _client_for_library(_seed_library(tmp_path))

    response = client.get("/?sort_by=citation_key&sort_dir=desc")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Alpha Study" in html


def test_index_invalid_sort_params_use_defaults(tmp_path: Path):
    """Invalid sort_by and sort_dir values silently fall back to defaults."""
    client = _client_for_library(_seed_library(tmp_path))

    response = client.get("/?sort_by=INVALID&sort_dir=BADVALUE")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Alpha Study" in html


def test_index_filter_by_author_builds_sort_links_with_author(tmp_path: Path):
    """Index with author filter sets author param in sort/export links (lines 141, 170)."""
    client = _client_for_library(_seed_library(tmp_path))

    response = client.get("/?author=Doe")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    # The sort links should embed author=Doe so it persists across sorting
    assert "author=Doe" in html
    assert "Alpha Study" in html


def test_index_filter_by_keyword_builds_sort_links_with_keyword(tmp_path: Path):
    """Index with keyword filter sets keyword param in sort/export links (lines 145, 174)."""
    client = _client_for_library(_seed_library(tmp_path))

    response = client.get("/?keyword=nlp")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    # The sort links should embed keyword=nlp
    assert "keyword=nlp" in html
    assert "Beta Models" in html


# ---------------------------------------------------------------------------
# Tag management routes – error paths
# ---------------------------------------------------------------------------


def test_tag_create_invalid_name_flashes_error(tmp_path: Path):
    """Creating a tag with invalid chars flashes an error (lines 523-524)."""
    client = _client_for_library(_seed_library(tmp_path))

    response = client.post(
        "/tags/create", data={"tag": "bad!tag#"}, follow_redirects=True
    )
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Invalid" in html or "invalid" in html or "error" in html.lower()


def test_tag_delete_empty_tag_flashes_error(tmp_path: Path):
    """Deleting with no tag name specified flashes an error (lines 531-532)."""
    client = _client_for_library(_seed_library(tmp_path))

    response = client.post(
        "/tags/delete", data={"tag": ""}, follow_redirects=True
    )
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "No tag specified" in html


def test_tag_delete_nonexistent_flashes_error(tmp_path: Path):
    """Deleting a tag that doesn't exist flashes an error (lines 536-537)."""
    client = _client_for_library(_seed_library(tmp_path))

    response = client.post(
        "/tags/delete", data={"tag": "ghost-tag"}, follow_redirects=True
    )
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "ghost-tag" in html or "not found" in html.lower()


def test_paper_tag_add_empty_flashes_error(tmp_path: Path):
    """Adding an empty tag to a paper flashes an error (lines 544-545)."""
    lib_dir = _seed_library(tmp_path)
    lib = Library(lib_dir)
    key = lib.list_papers()[0].citation_key
    client = _client_for_library(lib_dir)

    response = client.post(
        f"/paper/{key}/tags/add", data={"tag": ""}, follow_redirects=True
    )
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "enter a tag name" in html.lower()


def test_paper_tag_add_invalid_tag_flashes_error(tmp_path: Path):
    """Adding a tag with invalid chars flashes an error (lines 551-552)."""
    lib_dir = _seed_library(tmp_path)
    lib = Library(lib_dir)
    key = lib.list_papers()[0].citation_key
    client = _client_for_library(lib_dir)

    response = client.post(
        f"/paper/{key}/tags/add",
        data={"tag": "bad!tag#"},
        follow_redirects=True,
    )
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Invalid" in html or "invalid" in html


def test_paper_tag_add_unknown_key_returns_404(tmp_path: Path):
    """Adding a tag to an unknown paper returns 404 (line 549-550)."""
    client = _client_for_library(_seed_library(tmp_path))

    response = client.post("/paper/ghost2000key/tags/add", data={"tag": "ml"})
    assert response.status_code == 404


def test_paper_tag_remove_empty_flashes_error(tmp_path: Path):
    """Removing with no tag name specified flashes an error (lines 559-560)."""
    lib_dir = _seed_library(tmp_path)
    lib = Library(lib_dir)
    key = lib.list_papers()[0].citation_key
    client = _client_for_library(lib_dir)

    response = client.post(
        f"/paper/{key}/tags/remove", data={"tag": ""}, follow_redirects=True
    )
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "No tag specified" in html


def test_paper_tag_remove_unknown_key_returns_404(tmp_path: Path):
    """Removing a tag from an unknown paper returns 404 (lines 564-565)."""
    client = _client_for_library(_seed_library(tmp_path))

    response = client.post("/paper/ghost2000key/tags/remove", data={"tag": "ml"})
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Paper detail – 404 for unknown key
# ---------------------------------------------------------------------------


def test_paper_detail_unknown_key_returns_404(tmp_path: Path):
    client = _client_for_library(_seed_library(tmp_path))
    response = client.get("/paper/ghost2000key")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# export_bib – fallback to paper.to_bibtex() when bib file is missing
# ---------------------------------------------------------------------------


def test_export_bib_fallback_to_bibtex_method(tmp_path: Path):
    """export_bib falls back to paper.to_bibtex() when .bib file is absent (line 503)."""
    lib_dir = _seed_library(tmp_path)
    lib = Library(lib_dir)
    key = lib.list_papers()[0].citation_key
    # Remove the stored bib file to trigger the fallback path
    bib_file = lib.bib_path(key)
    bib_file.unlink()
    client = _client_for_library(lib_dir)

    response = client.get("/export_bib")

    assert response.status_code == 200
    content = response.get_data(as_text=True)
    assert "@article" in content


# ---------------------------------------------------------------------------
# PDF URL download paths – /add and /paper/<key>/add_pdf (mocked urlopen)
# ---------------------------------------------------------------------------


class _FakeHTTPResponse:
    """Minimal fake for urllib.request.urlopen context manager."""

    def __init__(self, data: bytes):
        self._data = data
        self._offset = 0

    def read(self, size: int) -> bytes:
        chunk = self._data[self._offset: self._offset + size]
        self._offset += size
        return chunk

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


def test_add_route_post_pdf_url_success(tmp_path: Path):
    """Providing a valid public PDF URL downloads and stores the PDF (lines 604-624)."""
    lib_dir = tmp_path / "addurllib"
    client = _client_for_library(lib_dir)

    bib_content = (
        "@article{urltest2025paper,\n"
        "  title  = {URL Download Test},\n"
        "  author = {Downloader, A},\n"
        "  year   = {2025},\n"
        "}\n"
    )

    fake_pdf = b"%PDF-1.4 fake content"
    fake_resp = _FakeHTTPResponse(fake_pdf)

    public_addr = [(socket.AF_INET, None, None, "", ("93.184.216.34", 0))]
    with patch("socket.getaddrinfo", return_value=public_addr):
        with patch("urllib.request.urlopen", return_value=fake_resp):
            response = client.post(
                "/add",
                data={
                    "bib_text": bib_content,
                    "pdf_url": "https://example.com/paper.pdf",
                },
                follow_redirects=True,
            )

    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "URL Download Test" in html or "urltest2025paper" in html


def test_add_route_post_pdf_url_download_error(tmp_path: Path):
    """URLError during PDF download flashes an error (lines 622-624)."""
    import urllib.error

    lib_dir = tmp_path / "addurlerr"
    client = _client_for_library(lib_dir)

    bib_content = (
        "@article{urlerr2025paper,\n"
        "  title  = {URL Error Test},\n"
        "  author = {Author, A},\n"
        "  year   = {2025},\n"
        "}\n"
    )

    public_addr = [(socket.AF_INET, None, None, "", ("93.184.216.34", 0))]
    with patch("socket.getaddrinfo", return_value=public_addr):
        with patch(
            "urllib.request.urlopen",
            side_effect=urllib.error.URLError("connection refused"),
        ):
            response = client.post(
                "/add",
                data={
                    "bib_text": bib_content,
                    "pdf_url": "https://example.com/paper.pdf",
                },
                follow_redirects=True,
            )

    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "Failed to download" in html


def test_add_pdf_route_post_pdf_url_success(tmp_path: Path):
    """Providing a valid public PDF URL to add_pdf downloads and stores the PDF (lines 678-698)."""
    lib_dir, key = _seed_library_no_pdf(tmp_path)
    client = _client_for_library(lib_dir)

    fake_pdf = b"%PDF-1.4 content"
    fake_resp = _FakeHTTPResponse(fake_pdf)

    public_addr = [(socket.AF_INET, None, None, "", ("93.184.216.34", 0))]
    with patch("socket.getaddrinfo", return_value=public_addr):
        with patch("urllib.request.urlopen", return_value=fake_resp):
            response = client.post(
                f"/paper/{key}/add_pdf",
                data={"pdf_url": "https://example.com/paper.pdf"},
                follow_redirects=True,
            )

    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "PDF added successfully" in html


def test_add_pdf_route_post_pdf_url_download_error(tmp_path: Path):
    """URLError during PDF URL download in add_pdf flashes error (lines 696-698)."""
    import urllib.error

    lib_dir, key = _seed_library_no_pdf(tmp_path)
    client = _client_for_library(lib_dir)

    public_addr = [(socket.AF_INET, None, None, "", ("93.184.216.34", 0))]
    with patch("socket.getaddrinfo", return_value=public_addr):
        with patch(
            "urllib.request.urlopen",
            side_effect=urllib.error.URLError("timed out"),
        ):
            response = client.post(
                f"/paper/{key}/add_pdf",
                data={"pdf_url": "https://example.com/paper.pdf"},
                follow_redirects=True,
            )

    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "Failed to download" in html


# ---------------------------------------------------------------------------
# PDF too large – /add and /paper/<key>/add_pdf (lines 614-619, 688-693)
# ---------------------------------------------------------------------------


class _OversizeFakeHTTPResponse:
    """Fake HTTP response that returns chunks until the 50 MB limit is exceeded."""

    def __init__(self, chunk_size: int = 64 * 1024):
        self._chunk = b"X" * chunk_size

    def read(self, size: int) -> bytes:
        return self._chunk[:size]

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


def test_add_route_post_pdf_url_too_large(tmp_path: Path):
    """PDF download exceeding 50 MB limit flashes an error (lines 614-619)."""
    lib_dir = tmp_path / "addurlbig"
    client = _client_for_library(lib_dir)

    bib_content = (
        "@article{bigpdf2025paper,\n"
        "  title  = {Big PDF Test},\n"
        "  author = {Author, A},\n"
        "  year   = {2025},\n"
        "}\n"
    )

    public_addr = [(socket.AF_INET, None, None, "", ("93.184.216.34", 0))]
    with patch("socket.getaddrinfo", return_value=public_addr):
        with patch(
            "urllib.request.urlopen",
            return_value=_OversizeFakeHTTPResponse(),
        ):
            response = client.post(
                "/add",
                data={
                    "bib_text": bib_content,
                    "pdf_url": "https://example.com/huge.pdf",
                },
                follow_redirects=True,
            )

    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "50 MB" in html or "maximum" in html.lower()


def test_add_pdf_route_post_pdf_url_too_large(tmp_path: Path):
    """PDF download exceeding 50 MB limit flashes an error for add_pdf (lines 688-693)."""
    lib_dir, key = _seed_library_no_pdf(tmp_path)
    client = _client_for_library(lib_dir)

    public_addr = [(socket.AF_INET, None, None, "", ("93.184.216.34", 0))]
    with patch("socket.getaddrinfo", return_value=public_addr):
        with patch(
            "urllib.request.urlopen",
            return_value=_OversizeFakeHTTPResponse(),
        ):
            response = client.post(
                f"/paper/{key}/add_pdf",
                data={"pdf_url": "https://example.com/huge.pdf"},
                follow_redirects=True,
            )

    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "50 MB" in html or "maximum" in html.lower()


# ---------------------------------------------------------------------------
# add_pdf route – lib.add_pdf exception path (lines 708-710)
# ---------------------------------------------------------------------------


def test_add_pdf_route_post_lib_error_shows_error(tmp_path: Path):
    """When lib.add_pdf raises an error it is flashed to the user (lines 708-710)."""
    lib_dir, key = _seed_library_no_pdf(tmp_path)
    client = _client_for_library(lib_dir)

    with patch(
        "liber.library.Library.add_pdf",
        side_effect=FileNotFoundError("PDF source vanished"),
    ):
        response = client.post(
            f"/paper/{key}/add_pdf",
            data={"pdf": (io.BytesIO(b"%PDF-1.4 ok"), "ok.pdf")},
            content_type="multipart/form-data",
            follow_redirects=True,
        )

    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "PDF source vanished" in html or "error" in html.lower()
