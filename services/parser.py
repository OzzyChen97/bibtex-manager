"""BibTeX parser and writer using bibtexparser."""
import bibtexparser
from bibtexparser.bparser import BibTexParser
from bibtexparser.bwriter import BibTexWriter
from bibtexparser.bibdatabase import BibDatabase
from models.entry import BibEntry
import re

# Export field sets for different modes
EXPORT_FIELDS = {
    'detailed': None,  # None means include all fields
    'standard': {
        'author', 'title', 'journal', 'booktitle', 'year', 'volume', 'number',
        'pages', 'doi', 'month', 'publisher', 'editor', 'school', 'institution',
        'series', 'eprint', 'archiveprefix',
    },
    'minimal': {
        'author', 'title', 'journal', 'booktitle', 'year',
        'eprint', 'archiveprefix',
    },
}


def parse_bibtex(bibtex_string: str) -> list[BibEntry]:
    """Parse a BibTeX string into a list of BibEntry objects."""
    parser = BibTexParser(common_strings=True)
    parser.ignore_nonstandard_types = False
    parser.homogenize_fields = True

    try:
        bib_db = bibtexparser.loads(bibtex_string, parser=parser)
    except Exception as e:
        raise ValueError(f"Failed to parse BibTeX: {e}")

    entries = []
    for record in bib_db.entries:
        entry = _record_to_entry(record)
        entry.raw_bibtex = _single_entry_to_bibtex(record)
        entries.append(entry)
    return entries


def _record_to_entry(record: dict) -> BibEntry:
    """Convert a bibtexparser record dict to a BibEntry."""
    entry_type = record.get('ENTRYTYPE', 'misc').lower()
    citation_key = record.get('ID', 'unknown')

    field_map = {
        'title': 'title',
        'author': 'author',
        'year': 'year',
        'month': 'month',
        'journal': 'journal',
        'booktitle': 'booktitle',
        'volume': 'volume',
        'number': 'number',
        'pages': 'pages',
        'doi': 'doi',
        'url': 'url',
        'abstract': 'abstract',
        'publisher': 'publisher',
        'editor': 'editor',
        'series': 'series',
        'address': 'address',
        'organization': 'organization',
        'school': 'school',
        'institution': 'institution',
        'note': 'note',
        'keywords': 'keywords',
    }

    kwargs = {
        'citation_key': citation_key,
        'entry_type': entry_type,
    }

    extra_fields = {}
    skip_keys = {'ENTRYTYPE', 'ID'}

    for key, value in record.items():
        if key in skip_keys:
            continue
        lower_key = key.lower()
        if lower_key in field_map:
            kwargs[field_map[lower_key]] = _clean_field(value)
        elif lower_key == 'eprint':
            kwargs['arxiv_id'] = _clean_field(value)
        elif lower_key in ('archiveprefix', 'primaryclass'):
            continue  # skip, reconstructed on export
        else:
            extra_fields[lower_key] = _clean_field(value)

    entry = BibEntry(**kwargs)
    entry._extra_fields = extra_fields
    return entry


def _clean_field(value: str) -> str:
    """Clean a BibTeX field value."""
    if not isinstance(value, str):
        return str(value)
    # Remove surrounding braces if present
    value = value.strip()
    if value.startswith('{') and value.endswith('}'):
        value = value[1:-1]
    # Collapse whitespace
    value = re.sub(r'\s+', ' ', value).strip()
    return value


def _single_entry_to_bibtex(record: dict) -> str:
    """Convert a single bibtexparser record to a BibTeX string."""
    db = BibDatabase()
    db.entries = [record]
    writer = BibTexWriter()
    writer.indent = '  '
    return writer.write(db).strip()


def entry_to_bibtex(entry: BibEntry, use_abbreviations: bool = False, mode: str = 'detailed') -> str:
    """Convert a BibEntry to a formatted BibTeX string."""
    fields = entry.get_bibtex_fields()

    # Filter fields based on export mode
    allowed = EXPORT_FIELDS.get(mode)
    if allowed is not None:
        fields = {k: v for k, v in fields.items() if k in allowed}

    # Order fields nicely
    field_order = [
        'author', 'title', 'journal', 'booktitle', 'year', 'month',
        'volume', 'number', 'pages', 'doi', 'url', 'eprint',
        'archiveprefix', 'publisher', 'editor', 'series', 'address',
        'organization', 'school', 'institution', 'note', 'keywords', 'abstract',
    ]

    lines = [f"@{entry.entry_type}{{{entry.citation_key},"]
    ordered_keys = []
    for k in field_order:
        if k in fields:
            ordered_keys.append(k)
    for k in sorted(fields.keys()):
        if k not in ordered_keys:
            ordered_keys.append(k)

    for i, key in enumerate(ordered_keys):
        value = fields[key]
        # Decide whether to brace-protect
        if key in ('month',) and value in ('jan', 'feb', 'mar', 'apr', 'may', 'jun',
                                            'jul', 'aug', 'sep', 'oct', 'nov', 'dec'):
            formatted = f"  {key} = {value}"
        else:
            formatted = f"  {key} = {{{value}}}"
        if i < len(ordered_keys) - 1:
            formatted += ","
        lines.append(formatted)
    lines.append("}")
    return "\n".join(lines)


def entries_to_bibtex(entries: list[BibEntry], use_abbreviations: bool = False, mode: str = 'detailed') -> str:
    """Convert a list of BibEntry objects to a full BibTeX string."""
    parts = [entry_to_bibtex(e, use_abbreviations, mode=mode) for e in entries]
    return "\n\n".join(parts) + "\n"
