"""Tests for the Flask web interface."""

from __future__ import annotations

from pathlib import Path

from liber.library import Library
from liber.web import create_app
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
