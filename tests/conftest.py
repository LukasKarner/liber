"""Shared test fixtures and helpers for liber tests."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture()
def dummy_pdf(tmp_path: Path) -> Path:
    """Return a path to a small dummy PDF file."""
    pdf = tmp_path / "paper.pdf"
    pdf.write_bytes(b"%PDF-1.4 dummy content")
    return pdf


def make_bib(tmp_path: Path, name: str, title: str, year: int,
             authors: list[str], keywords: list[str] = (),
             doi: str = "") -> Path:
    """Write a minimal .bib file and return its path."""
    authors_str = " and ".join(authors)
    lines = [
        f"@article{{tmpkey{year},",
        f"  title    = {{{title}}},",
        f"  author   = {{{authors_str}}},",
        f"  year     = {{{year}}},",
    ]
    if keywords:
        lines.append(f"  keywords = {{{', '.join(keywords)}}},")
    if doi:
        lines.append(f"  doi      = {{{doi}}},")
    lines.append("}\n")
    bib = tmp_path / name
    bib.write_text("\n".join(lines), encoding="utf-8")
    return bib
