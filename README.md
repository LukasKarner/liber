# liber

A command-line tool to manage academic research literature.

## Overview

**liber** organises papers in a dedicated library directory.
Each paper lives in its own sub-directory named after its *citation key*
and contains:

- **`<key>.bib`** — a BibTeX entry *(required)*
- **`<key>.pdf`** *(optional)* — a copy of the paper
- **`<key>.md`** *(optional)* — personal notes

A central index file (`.liber_index.json`) tracks every paper's title,
publication year, authors, keywords, and DOI.

### Citation-key format

Keys follow the **author–year–title** convention:

```txt
{first_author_last_name}{year}{first_significant_title_word}
```

Examples:

- `vaswani2017attention` — Vaswani et al. (2017) "Attention Is All You Need"
- `lecun2015deep` — LeCun et al. (2015) "Deep Learning"

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
Papers without a DOI are added gracefully.  If no PDF is supplied at add time,
a PDF can be attached later via the web interface.

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

### Start the web interface

Launch a locally hosted website for browsing and managing your library.
The web interface also allows you to add or replace the PDF for any paper
after it has been added.

```bash
liber serve
```

To keep the service running in the background after closing the terminal window:

```bash
nohup liber serve
```

Then open <http://127.0.0.1:5000> in your browser.

Additional options:

```bash
liber serve --port 8080            # use a different port
liber serve --host 0.0.0.0         # listen on all network interfaces
liber --library-dir /path/to/lib serve  # use a custom library directory
```

## Library structure

```txt
~/liber/
└── library/
    ├── .liber_index.json
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
