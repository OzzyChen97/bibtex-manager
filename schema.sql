CREATE TABLE IF NOT EXISTS entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    citation_key TEXT UNIQUE NOT NULL,
    entry_type TEXT NOT NULL,
    title TEXT,
    author TEXT,
    year TEXT,
    month TEXT,
    journal TEXT,
    booktitle TEXT,
    volume TEXT,
    number TEXT,
    pages TEXT,
    doi TEXT,
    arxiv_id TEXT,
    url TEXT,
    abstract TEXT,
    publisher TEXT,
    editor TEXT,
    series TEXT,
    address TEXT,
    organization TEXT,
    school TEXT,
    institution TEXT,
    note TEXT,
    keywords TEXT,
    raw_bibtex TEXT,
    validation_status TEXT DEFAULT 'unchecked',
    validation_messages TEXT DEFAULT '[]',
    source TEXT DEFAULT 'manual',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_entries_doi ON entries(doi);
CREATE INDEX IF NOT EXISTS idx_entries_arxiv_id ON entries(arxiv_id);
CREATE INDEX IF NOT EXISTS idx_entries_title ON entries(title);
CREATE INDEX IF NOT EXISTS idx_entries_year ON entries(year);
