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

    lib.add(pdf_path=pdf, bib_path=bib1)
    lib.add(pdf_path=pdf, bib_path=bib2)
    lib.add(pdf_path=pdf, bib_path=bib3)

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
