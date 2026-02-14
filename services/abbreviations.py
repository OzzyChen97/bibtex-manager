"""Journal and conference name abbreviation engine."""
import json
import os
from difflib import SequenceMatcher


_abbrev_cache = None


def _load_abbreviations() -> dict:
    global _abbrev_cache
    if _abbrev_cache is not None:
        return _abbrev_cache
    data_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                             'data', 'journal_abbrevs.json')
    # PyInstaller compatibility
    import sys
    if getattr(sys, 'frozen', False):
        from config import BASE_PATH
        data_path = os.path.join(BASE_PATH, 'data', 'journal_abbrevs.json')
    with open(data_path) as f:
        _abbrev_cache = json.load(f)
    return _abbrev_cache


def abbreviate(name: str, threshold: float = 0.85) -> str:
    """Look up abbreviation for a journal/conference name.

    Uses exact match first, then fuzzy matching above threshold.
    Returns original name if no match found.
    """
    if not name:
        return name

    abbrevs = _load_abbreviations()
    name_clean = name.strip()
    name_lower = name_clean.lower()

    # Exact match (case-insensitive)
    for full_name, abbrev in abbrevs.items():
        if full_name.lower() == name_lower:
            return abbrev

    # Fuzzy match
    best_score = 0.0
    best_abbrev = None
    for full_name, abbrev in abbrevs.items():
        score = SequenceMatcher(None, name_lower, full_name.lower()).ratio()
        if score > best_score:
            best_score = score
            best_abbrev = abbrev

    if best_score >= threshold and best_abbrev:
        return best_abbrev

    return name_clean


def expand(abbrev: str) -> str:
    """Look up full name for an abbreviation."""
    if not abbrev:
        return abbrev

    abbrevs = _load_abbreviations()
    abbrev_lower = abbrev.strip().lower()

    for full_name, ab in abbrevs.items():
        if ab.lower() == abbrev_lower:
            return full_name

    return abbrev


def reload_abbreviations():
    """Force reload of abbreviation data."""
    global _abbrev_cache
    _abbrev_cache = None
    _load_abbreviations()
