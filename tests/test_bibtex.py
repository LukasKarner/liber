"""Tests for liber.bibtex parser and utilities."""

from __future__ import annotations

from pathlib import Path

import pytest

from liber.bibtex import (
    _parse_fields,
    _read_brace_content,
    _read_quoted_content,
    get_authors,
    get_doi,
    get_keywords,
    get_title,
    get_year,
    parse_bib_file,
    parse_bibtex,
    rewrite_key,
)

# ---------------------------------------------------------------------------
# Sample BibTeX strings
# ---------------------------------------------------------------------------

_FULL_ENTRY = """\
@article{vaswani2017attention,
  title    = {Attention Is All You Need},
  author   = {Vaswani, Ashish and Shazeer, Noam and Parmar, Niki},
  year     = {2017},
  keywords = {transformers, attention, neural networks},
  doi      = {10.48550/arXiv.1706.03762},
}
"""

_NO_DOI_ENTRY = """\
@inproceedings{smith2020nodoi,
  title  = {A Paper Without DOI},
  author = {Smith, John},
  year   = {2020},
}
"""

_NO_KEYWORDS_ENTRY = """\
@article{jones2019nokw,
  title  = {No Keywords Here},
  author = {Jones, Alice},
  year   = {2019},
  doi    = {10.1/test},
}
"""

_QUOTED_VALUES_ENTRY = """\
@article{doe2018quoted,
  title  = "Quoted Values Paper",
  author = "Doe, John",
  year   = "2018",
}
"""

_BARE_YEAR_ENTRY = """\
@article{bare2021,
  title  = {Bare Year},
  author = {Author, A},
  year   = 2021,
}
"""

_NESTED_BRACES_ENTRY = """\
@article{nested2022,
  title  = {{BERT}: Pre-training of Deep Bidirectional Transformers},
  author = {Devlin, Jacob and Chang, Ming-Wei},
  year   = {2022},
}
"""


# ---------------------------------------------------------------------------
# parse_bibtex
# ---------------------------------------------------------------------------


class TestParseBibtex:
    def test_extracts_type(self):
        fields = parse_bibtex(_FULL_ENTRY)
        assert fields["_type"] == "article"

    def test_extracts_key(self):
        fields = parse_bibtex(_FULL_ENTRY)
        assert fields["_key"] == "vaswani2017attention"

    def test_extracts_title(self):
        fields = parse_bibtex(_FULL_ENTRY)
        assert fields["title"] == "Attention Is All You Need"

    def test_extracts_year(self):
        fields = parse_bibtex(_FULL_ENTRY)
        assert fields["year"] == "2017"

    def test_extracts_author(self):
        fields = parse_bibtex(_FULL_ENTRY)
        assert "Vaswani, Ashish" in fields["author"]
        assert "Shazeer, Noam" in fields["author"]

    def test_extracts_doi(self):
        fields = parse_bibtex(_FULL_ENTRY)
        assert fields["doi"] == "10.48550/arXiv.1706.03762"

    def test_extracts_keywords(self):
        fields = parse_bibtex(_FULL_ENTRY)
        assert "transformers" in fields["keywords"]

    def test_no_doi_field_absent(self):
        fields = parse_bibtex(_NO_DOI_ENTRY)
        assert "doi" not in fields

    def test_quoted_values(self):
        fields = parse_bibtex(_QUOTED_VALUES_ENTRY)
        assert fields["title"] == "Quoted Values Paper"
        assert fields["author"] == "Doe, John"

    def test_bare_year(self):
        fields = parse_bibtex(_BARE_YEAR_ENTRY)
        assert fields["year"] == "2021"

    def test_nested_braces_in_title(self):
        fields = parse_bibtex(_NESTED_BRACES_ENTRY)
        assert "BERT" in fields["title"]
        assert "Bidirectional" in fields["title"]

    def test_inproceedings_type(self):
        fields = parse_bibtex(_NO_DOI_ENTRY)
        assert fields["_type"] == "inproceedings"

    def test_missing_entry_raises(self):
        with pytest.raises(ValueError, match="No BibTeX entry"):
            parse_bibtex("This is not a bib file")

    def test_no_citation_key_raises(self):
        """Entry with no citation key before comma raises ValueError."""
        with pytest.raises(ValueError, match="citation key"):
            parse_bibtex("@article{ }")  # no comma → key_match fails


# ---------------------------------------------------------------------------
# get_* helpers
# ---------------------------------------------------------------------------


class TestGetAuthors:
    def test_multiple_authors(self):
        fields = parse_bibtex(_FULL_ENTRY)
        authors = get_authors(fields)
        assert authors == ["Vaswani, Ashish", "Shazeer, Noam", "Parmar, Niki"]

    def test_single_author(self):
        fields = parse_bibtex(_NO_DOI_ENTRY)
        authors = get_authors(fields)
        assert authors == ["Smith, John"]

    def test_missing_author_returns_empty(self):
        fields = {"_type": "article", "_key": "k"}
        assert get_authors(fields) == []


class TestGetYear:
    def test_braced_year(self):
        fields = parse_bibtex(_FULL_ENTRY)
        assert get_year(fields) == 2017

    def test_bare_year(self):
        fields = parse_bibtex(_BARE_YEAR_ENTRY)
        assert get_year(fields) == 2021

    def test_missing_year_raises(self):
        with pytest.raises(ValueError, match="year"):
            get_year({"_type": "article", "_key": "k"})

    def test_non_digit_year_raises(self):
        with pytest.raises(ValueError, match="year"):
            get_year({"_type": "article", "_key": "k", "year": "abc"})


class TestGetTitle:
    def test_basic(self):
        fields = parse_bibtex(_FULL_ENTRY)
        assert get_title(fields) == "Attention Is All You Need"

    def test_nested_braces_stripped(self):
        fields = parse_bibtex(_NESTED_BRACES_ENTRY)
        # Inner braces stripped; title content intact
        title = get_title(fields)
        assert "BERT" in title

    def test_missing_title_raises(self):
        with pytest.raises(ValueError, match="title"):
            get_title({"_type": "article", "_key": "k"})


class TestGetDoi:
    def test_present(self):
        fields = parse_bibtex(_FULL_ENTRY)
        assert get_doi(fields) == "10.48550/arXiv.1706.03762"

    def test_absent_returns_empty_string(self):
        fields = parse_bibtex(_NO_DOI_ENTRY)
        assert get_doi(fields) == ""


class TestGetKeywords:
    def test_comma_separated(self):
        fields = parse_bibtex(_FULL_ENTRY)
        kws = get_keywords(fields)
        assert "transformers" in kws
        assert "attention" in kws
        assert "neural networks" in kws

    def test_absent_returns_empty_list(self):
        fields = parse_bibtex(_NO_KEYWORDS_ENTRY)
        assert get_keywords(fields) == []


# ---------------------------------------------------------------------------
# rewrite_key
# ---------------------------------------------------------------------------


class TestRewriteKey:
    def test_key_replaced(self):
        new = rewrite_key(_FULL_ENTRY, "newkey2023")
        assert "@article{newkey2023," in new
        assert "vaswani2017attention" not in new

    def test_fields_untouched(self):
        new = rewrite_key(_FULL_ENTRY, "newkey2023")
        assert "Attention Is All You Need" in new
        assert "Vaswani, Ashish" in new
        assert "10.48550/arXiv.1706.03762" in new

    def test_original_unchanged(self):
        """rewrite_key must not mutate the original string."""
        original = _FULL_ENTRY
        rewrite_key(original, "changed")
        assert "vaswani2017attention" in original


# ---------------------------------------------------------------------------
# parse_bib_file (round-trip via file)
# ---------------------------------------------------------------------------


class TestParseBibFile:
    def test_reads_file(self, tmp_path: Path):
        bib = tmp_path / "test.bib"
        bib.write_text(_FULL_ENTRY, encoding="utf-8")
        fields = parse_bib_file(bib)
        assert fields["title"] == "Attention Is All You Need"

    def test_missing_file_raises(self, tmp_path: Path):
        with pytest.raises(FileNotFoundError):
            parse_bib_file(tmp_path / "nonexistent.bib")


# ---------------------------------------------------------------------------
# get_authors – case-insensitive AND separator
# ---------------------------------------------------------------------------


class TestGetAuthorsExtended:
    def test_uppercase_and_separator(self):
        """'AND' (uppercase) must split authors correctly."""
        fields = {"author": "Smith, John AND Doe, Jane"}
        authors = get_authors(fields)
        assert authors == ["Smith, John", "Doe, Jane"]

    def test_mixed_case_and_separator(self):
        """'And' (mixed case) must split authors correctly."""
        fields = {"author": "Smith, John And Doe, Jane"}
        authors = get_authors(fields)
        assert authors == ["Smith, John", "Doe, Jane"]

    def test_whitespace_around_and(self):
        """Extra whitespace around 'and' is handled."""
        fields = {"author": "  Smith, John  and  Doe, Jane  "}
        authors = get_authors(fields)
        assert authors == ["Smith, John", "Doe, Jane"]


# ---------------------------------------------------------------------------
# _read_brace_content – internal error paths
# ---------------------------------------------------------------------------


class TestReadBraceContent:
    def test_non_brace_start_raises(self):
        """Raises ValueError when position does not point to '{'."""
        with pytest.raises(ValueError, match="Expected"):
            _read_brace_content("x}", 0)

    def test_unbalanced_braces_raises(self):
        """Raises ValueError when closing brace is never found."""
        with pytest.raises(ValueError, match="Unbalanced"):
            _read_brace_content("{unclosed content", 0)

    def test_balanced_braces_returns_content(self):
        """Normal case: returns inner content and end position."""
        content, end = _read_brace_content("{hello}", 0)
        assert content == "hello"
        assert end == 6  # index of closing '}'

    def test_nested_braces(self):
        """Nested braces are preserved in returned content."""
        content, _ = _read_brace_content("{{nested}}", 0)
        assert content == "{nested}"


# ---------------------------------------------------------------------------
# _read_quoted_content – internal error paths
# ---------------------------------------------------------------------------


class TestReadQuotedContent:
    def test_non_quote_start_raises(self):
        """Raises ValueError when position does not point to '\"'."""
        with pytest.raises(ValueError, match="Expected"):
            _read_quoted_content('x"hello"', 0)

    def test_unterminated_quote_raises(self):
        """Raises ValueError when closing quote is never found."""
        with pytest.raises(ValueError, match="Unterminated"):
            _read_quoted_content('"unclosed content', 0)

    def test_basic_quoted_content(self):
        """Normal case: returns inner content and end position."""
        content, end = _read_quoted_content('"hello"', 0)
        assert content == "hello"
        assert end == 6


# ---------------------------------------------------------------------------
# _parse_fields – edge cases
# ---------------------------------------------------------------------------


class TestParseFieldsEdgeCases:
    def test_field_name_at_end_of_content_triggers_break(self):
        """Field name with no value at end of content (line 228: i >= n → break)."""
        # Content ends immediately after '= ' with no value
        text = "@article{key, year =}"
        # Should not raise; year field simply has no value
        fields = parse_bibtex(text)
        assert fields["_key"] == "key"
        assert "year" not in fields

    def test_bare_value_empty_skipped(self):
        """Bare value starting with comma is skipped (lines 244-245)."""
        # 'year = ,' means the bare value starts with comma → match fails → skip
        text = (
            "@article{key,\n"
            "  year = ,\n"
            "  title = {Bare Skip Test},\n"
            "  author = {Author, A},\n"
            "}"
        )
        fields = parse_bibtex(text)
        assert fields["title"] == "Bare Skip Test"
        assert "year" not in fields

    def test_stray_non_field_chars_skipped(self):
        """Characters that don't form a 'name = value' pair are skipped (lines 221-222)."""
        text = (
            "@article{key,\n"
            "  ! stray char\n"
            "  title = {Stray Test},\n"
            "  author = {Author, A},\n"
            "  year = {2024},\n"
            "}"
        )
        fields = parse_bibtex(text)
        assert fields["title"] == "Stray Test"
        assert fields["year"] == "2024"

    def test_semicolon_keywords_split(self):
        """Keywords separated by semicolons are handled."""
        fields = {"keywords": "deep learning; neural networks; attention"}
        kws = get_keywords(fields)
        assert "deep learning" in kws
        assert "neural networks" in kws
        assert "attention" in kws

    def test_keyword_singular_field(self):
        """'keyword' (singular) field is recognised as fallback."""
        fields = {"keyword": "nlp, transformers"}
        kws = get_keywords(fields)
        assert "nlp" in kws
        assert "transformers" in kws
