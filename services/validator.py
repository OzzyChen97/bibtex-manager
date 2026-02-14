"""Field completeness and format validation for BibTeX entries."""
import re
import json
import os
from models.entry import BibEntry


_field_rules = None


def _load_field_rules() -> dict:
    global _field_rules
    if _field_rules is not None:
        return _field_rules
    data_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                             'data', 'field_rules.json')
    # PyInstaller compatibility
    import sys
    if getattr(sys, 'frozen', False):
        from config import BASE_PATH
        data_path = os.path.join(BASE_PATH, 'data', 'field_rules.json')
    with open(data_path) as f:
        _field_rules = json.load(f)
    return _field_rules


def validate_entry(entry: BibEntry) -> tuple[str, list[str]]:
    """Validate a BibTeX entry.

    Returns (status, messages) where status is 'valid', 'warning', or 'error'.
    """
    rules = _load_field_rules()
    messages = []
    has_error = False
    has_warning = False

    entry_type = entry.entry_type.lower()
    type_rules = rules.get(entry_type, rules.get('misc', {}))

    # Check required fields
    for field in type_rules.get('required', []):
        value = getattr(entry, field, None)
        if not value:
            messages.append(f"Missing required field: {field}")
            has_error = True

    # Check recommended fields
    for field in type_rules.get('recommended', []):
        value = getattr(entry, field, None)
        if not value:
            messages.append(f"Missing recommended field: {field}")
            has_warning = True

    # Format validations
    if entry.doi:
        if not re.match(r'^10\.\d{4,}/', entry.doi):
            messages.append(f"Invalid DOI format: {entry.doi}")
            has_warning = True

    if entry.year:
        if not re.match(r'^\d{4}$', entry.year):
            messages.append(f"Invalid year format: {entry.year}")
            has_warning = True

    if entry.pages:
        if not re.match(r'^[\d]+\s*--\s*[\d]+$', entry.pages) and not re.match(r'^\d+$', entry.pages):
            messages.append(f"Non-standard page format: {entry.pages}")
            has_warning = True

    if entry.month:
        valid_months = {'jan', 'feb', 'mar', 'apr', 'may', 'jun',
                        'jul', 'aug', 'sep', 'oct', 'nov', 'dec'}
        if entry.month not in valid_months:
            messages.append(f"Non-standard month format: {entry.month}")
            has_warning = True

    if has_error:
        status = 'error'
    elif has_warning:
        status = 'warning'
    else:
        status = 'valid'

    return status, messages


def validate_entries(entries: list[BibEntry]) -> list[BibEntry]:
    """Validate all entries, updating their validation fields."""
    for entry in entries:
        status, messages = validate_entry(entry)
        entry.validation_status = status
        entry.validation_messages = json.dumps(messages)
    return entries
