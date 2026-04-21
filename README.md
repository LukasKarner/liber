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

```bash
liber add paper.pdf paper.bib
```

Metadata (title, year, authors, keywords, DOI) is extracted directly from the
BibTeX file.  The citation key in the stored copy is rewritten to the
author-year-title format; all other BibTeX fields are preserved unchanged.
Papers without a DOI are added gracefully.

Use `--key <custom_key>` to override the auto-generated citation key:

```bash
liber add paper.pdf paper.bib --key lecun2015deep
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

Launch a locally hosted website for browsing and managing your library:

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

### Auto-start on boot

#### Linux (systemd)

Create a systemd user service so that `liber serve` starts automatically when
you log in:

**1. Create the service file**

```bash
mkdir -p ~/.config/systemd/user
cat > ~/.config/systemd/user/liber.service << 'EOF'
[Unit]
Description=liber web interface
After=network.target

[Service]
ExecStart=/path/to/.venv/bin/liber serve
Restart=on-failure

[Install]
WantedBy=default.target
EOF
```

Replace `/path/to/.venv/bin/liber` with the actual path to the `liber`
executable (run `which liber` to find it).

**2. Enable and start the service**

```bash
systemctl --user daemon-reload
systemctl --user enable --now liber.service
```

**3. Allow the service to run without an active login session** *(optional)*

```bash
loginctl enable-linger $USER
```

To check the service status or view logs:

```bash
systemctl --user status liber.service
journalctl --user -u liber.service
```

#### macOS (launchd)

Create a launch agent so that `liber serve` starts automatically at login:

**1. Create the plist file**

```bash
cat > ~/Library/LaunchAgents/liber.plist << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>liber</string>
    <key>ProgramArguments</key>
    <array>
        <string>/path/to/.venv/bin/liber</string>
        <string>serve</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/tmp/liber.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/liber.err</string>
</dict>
</plist>
EOF
```

Replace `/path/to/.venv/bin/liber` with the actual path to the `liber`
executable (run `which liber` to find it).

**2. Load the launch agent**

```bash
launchctl load ~/Library/LaunchAgents/liber.plist
```

To stop and unload the agent:

```bash
launchctl unload ~/Library/LaunchAgents/liber.plist
```

## Library structure

```txt
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
python3 -m pytest tests/
```
