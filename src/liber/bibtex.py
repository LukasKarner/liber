"""Lightweight BibTeX parser and writer for liber.

Only handles single-entry ``.bib`` files (one ``@type{key, ...}`` block).
Supports brace-delimited values (possibly nested), quote-delimited values,
and bare numeric values.
"""

from __future__ import annotations

import re
from pathlib import Path


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def parse_bib_file(bib_path: Path) -> dict[str, str]:
    """Parse a ``.bib`` file and return a mapping of field names to values.

    The returned dict also contains the special key ``"_type"`` (the entry
    type, e.g. ``"article"``) and ``"_key"`` (the original citation key).
    All field names are lower-cased.

    Args:
        bib_path: Path to the ``.bib`` file.

    Returns:
        Dict of field names → raw string values (braces/quotes stripped).

    Raises:
        ValueError: If no BibTeX entry is found or the file is malformed.
    """
    text = Path(bib_path).read_text(encoding="utf-8")
    return parse_bibtex(text)


def parse_bibtex(text: str) -> dict[str, str]:
    """Parse a single BibTeX entry from *text*.

    Returns a dict with ``"_type"``, ``"_key"``, and one key per field.

    Raises:
        ValueError: If no ``@type{key, ...}`` entry is found in *text*, or
            if the citation key cannot be extracted.
    """
    # Locate the start: @type{
    header_match = re.search(r"@(\w+)\s*\{", text)
    if not header_match:
        raise ValueError("No BibTeX entry found in the provided text.")

    entry_type = header_match.group(1).lower()
    pos = header_match.end()  # position right after the opening '{'

    # Extract the content of the outer braces
    content, _ = _read_brace_content(text, pos - 1)

    result: dict[str, str] = {"_type": entry_type}

    # The first token before a comma is the citation key
    key_match = re.match(r"\s*([^,\s]+)\s*,", content)
    if not key_match:
        raise ValueError("Could not extract citation key from BibTeX entry.")
    result["_key"] = key_match.group(1).strip()

    # Parse fields after the key
    rest = content[key_match.end():]
    _parse_fields(rest, result)

    return result


def rewrite_key(bib_text: str, new_key: str) -> str:
    """Return *bib_text* with the citation key replaced by *new_key*.

    Only the key in the ``@type{key,`` header line is changed; all field
    values are left untouched.
    """
    return re.sub(
        r"(@\w+\s*\{)\s*[^,\s]+\s*,",
        lambda m: f"{m.group(1)}{new_key},",
        bib_text,
        count=1,
    )


# ---------------------------------------------------------------------------
# Field-level helpers
# ---------------------------------------------------------------------------


def get_authors(fields: dict[str, str]) -> list[str]:
    """Return a list of author strings from a parsed BibTeX field dict.

    Splits the ``author`` field on `` and `` (case-insensitive).
    Returns an empty list if no ``author`` field is present.
    """
    raw = fields.get("author", "").strip()
    if not raw:
        return []
    return [a.strip() for a in re.split(r"\s+and\s+", raw, flags=re.IGNORECASE) if a.strip()]


def get_keywords(fields: dict[str, str]) -> list[str]:
    """Return a list of keyword strings from a parsed BibTeX field dict.

    Checks both ``keywords`` and ``keyword`` fields.  Splits on commas or
    semicolons.  Returns an empty list if neither field is present.
    """
    raw = fields.get("keywords") or fields.get("keyword") or ""
    raw = raw.strip()
    if not raw:
        return []
    return [k.strip() for k in re.split(r"[,;]", raw) if k.strip()]


def get_year(fields: dict[str, str]) -> int:
    """Return the publication year as an integer.

    Raises:
        ValueError: If the ``year`` field is missing or not a valid 4-digit year.
    """
    raw = fields.get("year", "").strip()
    if not raw:
        raise ValueError("BibTeX entry has no 'year' field.")
    digits = re.sub(r"[^\d]", "", raw)
    if not digits:
        raise ValueError(f"BibTeX 'year' field contains no digits: {raw!r}.")
    return int(digits)


def get_title(fields: dict[str, str]) -> str:
    """Return the title string.

    Raises:
        ValueError: If the ``title`` field is missing.
    """
    raw = fields.get("title", "").strip()
    if not raw:
        raise ValueError("BibTeX entry has no 'title' field.")
    return raw


def get_doi(fields: dict[str, str]) -> str:
    """Return the DOI string, or an empty string if absent."""
    return fields.get("doi", "").strip()


# ---------------------------------------------------------------------------
# Internal parsing helpers
# ---------------------------------------------------------------------------


def _read_brace_content(text: str, start: int) -> tuple[str, int]:
    """Read balanced brace content starting at *start* (which must be ``{``).

    Returns ``(inner_content, end_position)`` where *end_position* is the
    index of the closing ``}``.
    """
    if text[start] != "{":
        raise ValueError(f"Expected '{{' at position {start}, got {text[start]!r}.")
    depth = 0
    buf: list[str] = []
    i = start
    while i < len(text):
        c = text[i]
        if c == "{":
            depth += 1
            if depth > 1:
                buf.append(c)
        elif c == "}":
            depth -= 1
            if depth == 0:
                return "".join(buf), i
            buf.append(c)
        else:
            buf.append(c)
        i += 1
    raise ValueError("Unbalanced braces in BibTeX entry.")


def _read_quoted_content(text: str, start: int) -> tuple[str, int]:
    """Read content between double quotes starting at *start* (must be ``"``).

    Returns ``(content, end_position)`` where *end_position* is the index of
    the closing ``"``.
    """
    if text[start] != '"':
        raise ValueError(f"Expected '\"' at position {start}.")
    buf: list[str] = []
    i = start + 1
    while i < len(text):
        c = text[i]
        if c == '"':
            return "".join(buf), i
        buf.append(c)
        i += 1
    raise ValueError("Unterminated quoted string in BibTeX entry.")


def _parse_fields(text: str, result: dict[str, str]) -> None:
    """Parse ``fieldname = value`` pairs from *text* into *result* (in-place).

    Field names are lower-cased.  Values may be ``{...}``, ``"..."``, or
    bare tokens (typically numbers).
    """
    i = 0
    n = len(text)
    while i < n:
        # Skip whitespace and commas
        while i < n and text[i] in " \t\n\r,":
            i += 1
        if i >= n:
            break

        # Read field name (sequence of word chars)
        name_match = re.match(r"([\w-]+)\s*=\s*", text[i:])
        if not name_match:
            # Probably trailing whitespace / closing brace — skip
            i += 1
            continue

        field_name = name_match.group(1).lower()
        i += name_match.end()

        if i >= n:
            break

        # Read value
        if text[i] == "{":
            value, end = _read_brace_content(text, i)
            i = end + 1
        elif text[i] == '"':
            value, end = _read_quoted_content(text, i)
            i = end + 1
        else:
            # Bare value — read until next comma or closing brace
            bare_match = re.match(r"([^,}\s]+)", text[i:])
            if bare_match:
                value = bare_match.group(1)
                i += bare_match.end()
            else:
                i += 1
                continue

        result[field_name] = value
