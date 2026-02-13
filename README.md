# BibTeX Manager

A full-featured BibTeX reference manager with LLM integration, built with Flask.

![Python](https://img.shields.io/badge/Python-3.12-blue)
![Flask](https://img.shields.io/badge/Flask-3.0+-green)
![Platform](https://img.shields.io/badge/Platform-macOS%20(Apple%20Silicon)-lightgrey)

## Features

### Entry Management
- Create, read, update, and delete BibTeX entries
- Automatic validation and normalization
- Citation key auto-generation (`AuthorYear` format)
- Side panel editor with live BibTeX preview

### Import / Export
- Import `.bib` files (drag & drop or paste)
- Duplicate detection during import (fuzzy matching)
- **Three export modes:**
  - **Detailed** — all fields (abstract, keywords, url, note, etc.)
  - **Standard** — common fields (author, title, venue, year, DOI, volume, pages, etc.)
  - **Minimal** — only author, title, venue, year
- Journal/conference name abbreviation on export

### Paper Search
- Search by DOI, arXiv ID, or title
- Sources: Crossref, arXiv API, Semantic Scholar
- One-click add to library with auto-normalization

### LLM Integration
- Batch-modify entries via any OpenAI-compatible LLM API
- **4 preset prompts:**
  - Complete Fields — fill in missing metadata
  - Fix Format — standardize author names, page ranges, months
  - Generate Abstract — create summaries and keywords
  - Check Type — verify and fix entry types
- Custom prompt support
- **Security-first design:**
  - Field name whitelist validation
  - Format checks (DOI, year, month, pages)
  - No-delete protection (LLM cannot erase existing data)
  - Interactive diff preview with per-field accept/reject
  - All changes go through normalize + validate pipeline

### Library Utilities
- Duplicate detection and merging
- Batch normalization
- Filter and sort entries

## Getting Started

### Option 1: Download macOS App (Apple Silicon)

1. Go to [Releases](https://github.com/OzzyChen97/bibtex-manager/releases)
2. Download `BibtexManager-macOS-arm64.dmg`
3. Open the DMG and drag `BibtexManager.app` to Applications
4. Launch the app — your browser will open automatically at `http://127.0.0.1:5001`

### Option 2: Run from Source

```bash
git clone https://github.com/OzzyChen97/bibtex-manager.git
cd bibtex-manager
pip install -r requirements.txt
python app.py
# Open http://localhost:5001
```

## Configuration

### LLM Setup
1. Click **LLM Settings** in the navigation bar
2. Enter your API details:
   - **Base URL** — e.g. `https://api.openai.com/v1`
   - **API Key** — your API key (stored locally, displayed masked)
   - **Model** — e.g. `gpt-4o-mini`
3. Click Save

### Export
Click the **Export .bib** dropdown to choose between Detailed, Standard, or Minimal export modes. All modes apply journal/conference abbreviations by default.

## Tech Stack

- **Backend:** Python, Flask, SQLite
- **Frontend:** Vanilla JS, CSS
- **APIs:** Crossref, arXiv, Semantic Scholar
- **LLM:** OpenAI-compatible API (via httpx)

## Project Structure

```
bibtex-manager/
├── app.py                 # Flask routes
├── config.py              # Configuration
├── schema.sql             # Database schema
├── models/
│   ├── entry.py           # BibEntry dataclass
│   └── database.py        # SQLite operations
├── services/
│   ├── parser.py          # BibTeX parsing & export modes
│   ├── normalizer.py      # Entry normalization
│   ├── validator.py       # Field validation
│   ├── deduplicator.py    # Duplicate detection
│   ├── abbreviations.py   # Journal abbreviations
│   └── llm.py             # LLM integration & security
├── apis/
│   ├── resolver.py        # Multi-source resolver
│   ├── arxiv_api.py       # arXiv API
│   ├── crossref.py        # Crossref API
│   └── semantic_scholar.py
├── static/
│   ├── css/style.css
│   └── js/
│       ├── api.js         # API wrapper
│       ├── app.js         # Main app logic
│       ├── table.js       # Table rendering & selection
│       ├── editor.js      # Entry editor panel
│       ├── import.js      # Import modal
│       ├── search.js      # Search modal
│       └── llm.js         # LLM UI & diff preview
├── templates/
│   └── index.html
└── data/
    ├── field_rules.json
    ├── journal_abbrevs.json
    └── llm_config.json
```

## License

MIT
