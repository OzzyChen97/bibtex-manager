from dataclasses import dataclass, field, asdict
from typing import Optional
import json


@dataclass
class BibEntry:
    """Represents a single BibTeX entry."""
    citation_key: str
    entry_type: str
    title: Optional[str] = None
    author: Optional[str] = None
    year: Optional[str] = None
    month: Optional[str] = None
    journal: Optional[str] = None
    booktitle: Optional[str] = None
    volume: Optional[str] = None
    number: Optional[str] = None
    pages: Optional[str] = None
    doi: Optional[str] = None
    arxiv_id: Optional[str] = None
    url: Optional[str] = None
    abstract: Optional[str] = None
    publisher: Optional[str] = None
    editor: Optional[str] = None
    series: Optional[str] = None
    address: Optional[str] = None
    organization: Optional[str] = None
    school: Optional[str] = None
    institution: Optional[str] = None
    note: Optional[str] = None
    keywords: Optional[str] = None
    raw_bibtex: Optional[str] = None
    validation_status: str = 'unchecked'
    validation_messages: str = '[]'
    source: str = 'manual'
    id: Optional[int] = None

    KNOWN_FIELDS = {
        'citation_key', 'entry_type', 'title', 'author', 'year', 'month',
        'journal', 'booktitle', 'volume', 'number', 'pages', 'doi',
        'arxiv_id', 'url', 'abstract', 'publisher', 'editor', 'series',
        'address', 'organization', 'school', 'institution', 'note', 'keywords',
    }

    # Extra fields not in the dataclass but present in the bibtex
    _extra_fields: dict = field(default_factory=dict, repr=False)

    def to_dict(self):
        d = asdict(self)
        d.pop('_extra_fields', None)
        if isinstance(d.get('validation_messages'), str):
            try:
                d['validation_messages'] = json.loads(d['validation_messages'])
            except (json.JSONDecodeError, TypeError):
                d['validation_messages'] = []
        return d

    def get_bibtex_fields(self) -> dict:
        """Return all fields suitable for BibTeX output."""
        fields = {}
        for f in self.KNOWN_FIELDS:
            if f in ('citation_key', 'entry_type'):
                continue
            val = getattr(self, f, None)
            if val:
                # Map arxiv_id to eprint for bibtex
                if f == 'arxiv_id':
                    fields['eprint'] = val
                    fields['archiveprefix'] = 'arXiv'
                else:
                    fields[f] = val
        fields.update(self._extra_fields)
        return fields

    @classmethod
    def from_db_row(cls, row):
        """Create a BibEntry from a database row (sqlite3.Row)."""
        d = dict(row)
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})
