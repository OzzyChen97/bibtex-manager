"""Duplicate detection and merging for BibTeX entries."""
from difflib import SequenceMatcher
from models.entry import BibEntry
from unidecode import unidecode
import re


def find_duplicates(entries: list[BibEntry], threshold: float = 0.85) -> list[dict]:
    """Find duplicate pairs among entries.

    Returns list of dicts: {entry1_id, entry2_id, confidence, reason}
    """
    duplicates = []
    for i in range(len(entries)):
        for j in range(i + 1, len(entries)):
            result = check_duplicate(entries[i], entries[j])
            if result and result['confidence'] >= threshold:
                duplicates.append(result)
    return sorted(duplicates, key=lambda x: -x['confidence'])


def check_duplicate(a: BibEntry, b: BibEntry) -> dict | None:
    """Check if two entries are duplicates. Returns match info or None."""
    # Exact DOI match
    if a.doi and b.doi and _normalize_str(a.doi) == _normalize_str(b.doi):
        return {
            'entry1_id': a.id,
            'entry2_id': b.id,
            'confidence': 1.00,
            'reason': f'Exact DOI match: {a.doi}',
        }

    # arXiv ID match (ignoring version)
    if a.arxiv_id and b.arxiv_id:
        a_base = a.arxiv_id.split('v')[0]
        b_base = b.arxiv_id.split('v')[0]
        if a_base == b_base:
            return {
                'entry1_id': a.id,
                'entry2_id': b.id,
                'confidence': 0.98,
                'reason': f'arXiv ID match: {a_base}',
            }

    # Title similarity + same year
    title_sim = _title_similarity(a.title, b.title)
    if title_sim >= 0.88 and a.year and b.year and a.year == b.year:
        return {
            'entry1_id': a.id,
            'entry2_id': b.id,
            'confidence': 0.95,
            'reason': f'Title similarity {title_sim:.2f} + same year {a.year}',
        }

    # Title + author similarity
    author_sim = _author_similarity(a.author, b.author)
    if title_sim >= 0.75 and author_sim >= 0.80:
        return {
            'entry1_id': a.id,
            'entry2_id': b.id,
            'confidence': 0.85,
            'reason': f'Title similarity {title_sim:.2f} + author similarity {author_sim:.2f}',
        }

    return None


def merge_entries(primary: BibEntry, secondary: BibEntry) -> BibEntry:
    """Merge two entries, preferring fields from primary.

    Fields present in primary are kept; missing fields are filled from secondary.
    """
    fields = [
        'title', 'author', 'year', 'month', 'journal', 'booktitle',
        'volume', 'number', 'pages', 'doi', 'arxiv_id', 'url',
        'abstract', 'publisher', 'editor', 'series', 'address',
        'organization', 'school', 'institution', 'note', 'keywords',
    ]
    for field in fields:
        primary_val = getattr(primary, field, None)
        secondary_val = getattr(secondary, field, None)
        if not primary_val and secondary_val:
            setattr(primary, field, secondary_val)

    return primary


def _normalize_str(s: str) -> str:
    if not s:
        return ''
    return unidecode(s).lower().strip()


def _title_similarity(t1: str | None, t2: str | None) -> float:
    if not t1 or not t2:
        return 0.0
    # Remove braces, punctuation, normalize
    c1 = re.sub(r'[{}()\[\]:,.\-]', '', _normalize_str(t1))
    c2 = re.sub(r'[{}()\[\]:,.\-]', '', _normalize_str(t2))
    c1 = re.sub(r'\s+', ' ', c1).strip()
    c2 = re.sub(r'\s+', ' ', c2).strip()
    return SequenceMatcher(None, c1, c2).ratio()


def _author_similarity(a1: str | None, a2: str | None) -> float:
    if not a1 or not a2:
        return 0.0
    c1 = _normalize_str(a1)
    c2 = _normalize_str(a2)
    return SequenceMatcher(None, c1, c2).ratio()
