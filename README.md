# liber

📚✨ *Stop losing track of papers.*

**liber** is a minimalist, local-first reference manager that keeps your research organised with precision and transparency.
No lock-in, no clutter—just your literature, structured, searchable, and entirely yours.

## ⚡ Quick example

```bash
# initialise your library
liber init

# add a paper
liber add paper.bib --pdf paper.pdf

# search your collection
liber search --keyword transformers

# launch web interface
liber serve
```

## 🧠 Why liber?

* **Transparent by design** — plain files, no hidden databases
* **Reproducible workflow** — BibTeX + Markdown + predictable structure
* **Local-first** — your data stays yours
* **Fast & scriptable** — built for researchers and developers alike

👉 Scroll down for installation and full usage.

## Overview

**liber** organises papers in a dedicated library directory.
Each paper lives in its own sub-directory named after its *citation key*
and contains:

- **`<key>.bib`** — a BibTeX entry *(required)*
- **`<key>.pdf`** *(optional)* — a copy of the paper
- **`<key>.md`** *(optional)* — personal notes

A central index file (`.liber_index.json`) tracks every paper's title,
publication year, authors, keywords, DOI, and tags.

### Citation-key format

Keys follow the **author–year–title** convention:

```txt
{first_author_last_name}{year}{first_significant_title_word}
```

Examples:

- `vaswani2017attention` — Vaswani et al. (2017) "Attention Is All You Need"
- `lecun2015deep` — LeCun et al. (2015) "Deep Learning"

### Web interface features

Launch a locally hosted website for browsing and managing your library.

```bash
liber serve
```

Then open <http://127.0.0.1:5000> in your browser.

The web interface provides a graphical view of the same library and exposes all
CLI features plus a few convenience additions, for example:

- Browse and sort the full paper list by citation key, year, title, or authors.
- Add papers by uploading a BibTeX file or pasting BibTeX text, with an
  optional PDF upload or URL.
- View the full details of each paper including the BibTeX entry and rendered
  Markdown notes.
- Edit and save the BibTeX entry and Markdown notes directly in the browser.
- Manage tags: create and delete global tags, assign and remove tags on papers.
- Export the full library or a filtered subset as a `.bib` file.

For the full list of features, see the [Features](#features) section below.

## Installation

### Prerequisites

- Python ≥ 3.9
- [git](https://git-scm.com/)

### Step-by-step

**1. Clone the repository**

```bash
git clone https://github.com/LukasKarner/liber.git
cd liber
```

**2. Create and activate a virtual environment** *(recommended)*

```bash
python3 -m venv .venv
source .venv/bin/activate   # on Windows: .venv\Scripts\activate
```

**3. Install liber**

```bash
pip install .
```

After installation the `liber` command is available in your shell. Verify it
with:

```bash
liber --help
```

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

Only a BibTeX file is required. A PDF can be provided optionally.

```bash
liber add paper.bib
liber add paper.bib --pdf paper.pdf
```

Metadata (title, year, authors, keywords, DOI) is extracted directly from the
BibTeX file.  The citation key in the stored copy is rewritten to the
author-year-title format; all other BibTeX fields are preserved unchanged.
Papers without a DOI are added gracefully.

Use `--key <custom_key>` to override the auto-generated citation key:

```bash
liber add paper.bib --key lecun2015deep
liber add paper.bib --pdf paper.pdf --key lecun2015deep
```

### Add a PDF to an existing paper

Attach or replace the PDF for a paper that was added without one:

```bash
liber add-pdf vaswani2017attention paper.pdf
```

### Delete the PDF of a paper

Remove the PDF file for a paper while keeping the entry and BibTeX file:

```bash
liber delete-pdf vaswani2017attention
```

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
liber search --tag "machine learning"
# combine filters (AND logic)
liber search --keyword transformers --year 2019
```

### Show paper details

Displays the citation key, title, year, authors, keywords, tags, DOI, PDF
status, directory, and notes status:

```bash
liber show vaswani2017attention
```

### Rename a citation key

Rename a paper's citation key — all associated files and the BibTeX entry are
updated automatically:

```bash
liber rename-key vaswani2017attention attention2017vaswani
```

### Edit a BibTeX entry

Open the stored BibTeX file in `$EDITOR` (default: `nano`).  After saving, the
index is updated from the new content:

```bash
liber edit-bibtex vaswani2017attention
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

### Manage tags

Tags are short labels (letters, digits, spaces, hyphens, underscores) used to
organise papers.

```bash
# list all tags
liber tag list

# create a new tag
liber tag create "machine learning"

# delete a tag (removes it from all papers too)
liber tag delete "machine learning"

# assign a tag to a paper (creates the tag automatically if needed)
liber tag add vaswani2017attention transformers

# remove a tag from a paper (tag stays in global registry)
liber tag remove vaswani2017attention transformers
```

### Export bibliographies

Export all papers (or a filtered subset) as a combined BibTeX file:

```bash
# print to stdout
liber export

# write to a file
liber export --output bibliography.bib

# filter the export (same flags as search)
liber export --tag transformers --output transformers.bib
liber export --author Vaswani --year 2017 --output vaswani.bib
```

### Start the web interface

Launch a locally hosted website for browsing and managing your library.

```bash
liber serve
```

Then open <http://127.0.0.1:5000> in your browser.

Additional options:

```bash
liber serve --port 8080            # use a different port
liber serve --host 0.0.0.0         # listen on all network interfaces
liber --library-dir /path/to/lib serve  # use a custom library directory
```

#### Features

The web interface provides a graphical view of the same library and exposes all
CLI features plus a few convenience additions:

- Browse and sort the full paper list by citation key, year, title, or authors.
- Filter papers by title, author, year, keyword, or tag.
- Add papers by uploading a BibTeX file or pasting BibTeX text, with an
  optional PDF upload or URL.
- View the full details of each paper including the rendered BibTeX entry and
  Markdown notes.
- Edit and save the Markdown notes for a paper directly in the browser.
- Edit the BibTeX entry for a paper in the browser.
- Rename a paper's citation key.
- Upload or replace the PDF for a paper (file upload or URL).
- Delete the PDF for a paper.
- Remove a paper entirely from the library.
- Manage tags: create and delete global tags, assign and remove tags on papers.
- Export the full library or a filtered subset as a `.bib` file.

## Library structure

```txt
~/liber/
└── library/
    ├── .liber_index.json
    ├── .liber_tags.json
    ├── vaswani2017attention/
    │   ├── vaswani2017attention.bib
    │   ├── vaswani2017attention.pdf   ← optional
    │   └── vaswani2017attention.md   ← optional notes
    └── lecun2015deep/
        ├── lecun2015deep.bib
        └── lecun2015deep.pdf         ← optional
```

## Running tests

```bash
pip install pytest
python3 -m pytest tests/
```
