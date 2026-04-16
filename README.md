# liber

A command-line tool to manage academic research literature.

## Overview

**liber** organises papers in a dedicated library directory.
Each paper lives in its own sub-directory named after its *citation key*
and contains:

- **`<key>.pdf`** — a copy of the paper
- **`<key>.bib`** — a BibTeX entry
- **`<key>.md`** *(optional)* — personal notes

A central index file (`.liber_index.json`) tracks every paper's title,
publication year, authors, keywords, and DOI.

### Citation-key format

Keys follow the **author–year–title** convention:

```
{first_author_last_name}{year}{first_significant_title_word}
```

Examples:
- `vaswani2017attention` — Vaswani et al. (2017) "Attention Is All You Need"
- `lecun2015deep` — LeCun et al. (2015) "Deep Learning"

## Installation

```bash
pip install .
```

Requires Python ≥ 3.9.

## Usage

The library directory defaults to `~/liber/`.
Override it with `--library-dir` or the `LIBER_DIR` environment variable.

### Initialise a library

```bash
liber init
# or specify a directory
liber --library-dir /path/to/lib init
```

### Add a paper

```bash
liber add paper.pdf \
    --title "Attention Is All You Need" \
    --year 2017 \
    --author "Vaswani, Ashish" \
    --author "Shazeer, Noam" \
    --keyword "transformers" \
    --keyword "attention" \
    --doi 10.48550/arXiv.1706.03762
```

Use `--key <custom_key>` to override the auto-generated citation key.

### List all papers

```bash
liber list
```

### Search papers

```bash
liber search --keyword transformers
liber search --author Vaswani
liber search --year 2017
liber search --title "attention"
# combine filters (AND logic)
liber search --keyword transformers --year 2019
```

### Show paper details

```bash
liber show vaswani2017attention
```

### Remove a paper

```bash
liber remove vaswani2017attention          # deletes files too
liber remove vaswani2017attention --keep-files  # index only
```

### Edit notes

Opens the paper's Markdown notes file in `$EDITOR` (default: `nano`).

```bash
liber note vaswani2017attention
```

## Library structure

```
~/liber/
├── .liber_index.json
├── vaswani2017attention/
│   ├── vaswani2017attention.pdf
│   ├── vaswani2017attention.bib
│   └── vaswani2017attention.md   ← optional notes
└── lecun2015deep/
    ├── lecun2015deep.pdf
    └── lecun2015deep.bib
```

## Running tests

```bash
pip install pytest
pytest
```
