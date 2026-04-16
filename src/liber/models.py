"""Data models for liber."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Paper:
    """Represents a single piece of academic literature in the library."""

    title: str
    year: int
    authors: list[str]
    keywords: list[str]
    doi: str
    citation_key: str

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "year": self.year,
            "authors": self.authors,
            "keywords": self.keywords,
            "doi": self.doi,
            "citation_key": self.citation_key,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Paper":
        return cls(
            title=data["title"],
            year=int(data["year"]),
            authors=data["authors"],
            keywords=data["keywords"],
            doi=data.get("doi", ""),
            citation_key=data["citation_key"],
        )

    def to_bibtex(self) -> str:
        """Return a BibTeX representation of this paper."""
        authors_str = " and ".join(self.authors)
        keywords_str = ", ".join(self.keywords)
        lines = [
            f"@article{{{self.citation_key},",
            f"  title     = {{{self.title}}},",
            f"  author    = {{{authors_str}}},",
            f"  year      = {{{self.year}}},",
        ]
        if self.keywords:
            lines.append(f"  keywords  = {{{keywords_str}}},")
        if self.doi:
            lines.append(f"  doi       = {{{self.doi}}},")
        lines.append("}")
        return "\n".join(lines)
