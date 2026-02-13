"""LLM integration service for BibTeX Manager."""
import json
import logging
import os
import re
import httpx

from models.entry import BibEntry

logger = logging.getLogger(__name__)

CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'llm_config.json')

VALID_ENTRY_TYPES = {
    'article', 'inproceedings', 'book', 'incollection', 'phdthesis',
    'mastersthesis', 'techreport', 'misc', 'unpublished', 'proceedings',
    'inbook', 'booklet', 'manual', 'conference',
}

VALID_MONTHS = {
    'jan', 'feb', 'mar', 'apr', 'may', 'jun',
    'jul', 'aug', 'sep', 'oct', 'nov', 'dec',
}

# Fields the LLM is allowed to propose changes to
ALLOWED_FIELDS = BibEntry.KNOWN_FIELDS | {'entry_type'}

SYSTEM_PROMPT_BASE = """You are a BibTeX metadata assistant. You will receive one or more BibTeX entries as JSON objects.
Your task is to propose modifications according to the user's instruction.

You MUST respond with ONLY a JSON array. Each element corresponds to one input entry and has this exact schema:
{
  "citation_key": "<the original citation_key, unchanged>",
  "changes": {
    "<field_name>": "<new_value>",
    ...
  }
}

Rules:
- citation_key in your response MUST exactly match the input entry's citation_key.
- Only include fields that you are actually changing in "changes". Do NOT echo unchanged fields.
- Never set a field to empty string "" or null if the original entry already has a value for it.
- Allowed field names: citation_key, entry_type, title, author, year, month, journal, booktitle, volume, number, pages, doi, arxiv_id, url, abstract, publisher, editor, series, address, organization, school, institution, note, keywords.
- entry_type must be one of: article, inproceedings, book, incollection, phdthesis, mastersthesis, techreport, misc, unpublished.
- year must be a 4-digit string like "2024".
- doi must start with "10.".
- month must be a 3-letter abbreviation: jan, feb, mar, apr, may, jun, jul, aug, sep, oct, nov, dec.
- pages should use double-dash format like "1--10".
- Do NOT include any explanation, markdown fences, or text outside the JSON array.
"""

PRESET_PROMPTS = {
    'complete_fields': 'Based on the information available in each entry (title, authors, DOI, arXiv ID, etc.), fill in any missing fields that you can confidently determine. For example, if you know the venue from the title or DOI, add the journal or booktitle. If the year is missing but can be inferred, add it. Only add fields you are confident about.',
    'fix_format': 'Fix formatting issues in the entries: standardize author names to "Last, First and Last, First" format, fix page ranges to use double-dash (e.g. "1--10"), ensure months use 3-letter abbreviations, fix any obvious typos in field values, and ensure titles use proper capitalization.',
    'generate_abstract': 'For entries that are missing an abstract, generate a concise academic abstract (2-3 sentences) based on the title, authors, and venue. Also suggest relevant keywords if the keywords field is empty.',
    'check_entry_type': 'Check if each entry has the correct entry_type based on its venue. For example: entries in journals should be "article", entries in conference proceedings should be "inproceedings", arXiv preprints without a published venue should be "misc", dissertations should be "phdthesis" or "mastersthesis". Fix any mismatched entry_types.',
}


def load_config() -> dict:
    """Load LLM configuration from file."""
    try:
        with open(CONFIG_PATH, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {'base_url': '', 'api_key': '', 'model': ''}


def save_config(config: dict) -> None:
    """Save LLM configuration to file."""
    safe = {
        'base_url': str(config.get('base_url', '')).strip(),
        'api_key': str(config.get('api_key', '')).strip(),
        'model': str(config.get('model', '')).strip(),
    }
    with open(CONFIG_PATH, 'w') as f:
        json.dump(safe, f, indent=2)


def mask_api_key(key: str) -> str:
    """Mask API key for display, showing only last 4 characters."""
    if not key or len(key) <= 4:
        return key
    return '*' * (len(key) - 4) + key[-4:]


def call_llm(entries: list[dict], preset: str = None, custom_prompt: str = None) -> dict:
    """Call LLM API and return validated proposals.

    Args:
        entries: list of entry dicts (from BibEntry.to_dict())
        preset: one of PRESET_PROMPTS keys
        custom_prompt: freeform user instruction (used if preset is None)

    Returns:
        dict with 'proposals' (list) and 'filtered' (list of warning messages)
    """
    config = load_config()
    if not config.get('base_url') or not config.get('api_key') or not config.get('model'):
        raise ValueError('LLM not configured. Please set base_url, api_key, and model in LLM Settings.')

    # Build user prompt
    if preset and preset in PRESET_PROMPTS:
        user_instruction = PRESET_PROMPTS[preset]
    elif custom_prompt:
        user_instruction = custom_prompt
    else:
        raise ValueError('No preset or custom prompt provided.')

    # Prepare entry data — only send relevant fields, not internal metadata
    clean_entries = []
    for e in entries:
        clean = {k: v for k, v in e.items()
                 if k in ALLOWED_FIELDS and v is not None and v != '' and v != []}
        clean_entries.append(clean)

    user_message = f"Instruction: {user_instruction}\n\nEntries:\n{json.dumps(clean_entries, indent=2)}"

    # Call API (OpenAI-compatible)
    base_url = config['base_url'].rstrip('/')
    headers = {
        'Authorization': f"Bearer {config['api_key']}",
        'Content-Type': 'application/json',
    }
    payload = {
        'model': config['model'],
        'temperature': 0.2,
        'messages': [
            {'role': 'system', 'content': SYSTEM_PROMPT_BASE},
            {'role': 'user', 'content': user_message},
        ],
    }

    try:
        with httpx.Client(timeout=60.0) as client:
            resp = client.post(f"{base_url}/chat/completions", headers=headers, json=payload)
            resp.raise_for_status()
            result = resp.json()
    except httpx.HTTPStatusError as e:
        raise ValueError(f"LLM API error: {e.response.status_code} {e.response.text[:200]}")
    except Exception as e:
        raise ValueError(f"LLM API request failed: {e}")

    content = result.get('choices', [{}])[0].get('message', {}).get('content', '')
    if not content:
        raise ValueError('LLM returned empty response.')

    raw_proposals = parse_llm_response(content)
    proposals, filtered = validate_proposals(raw_proposals, entries)
    return {'proposals': proposals, 'filtered': filtered}


def parse_llm_response(content: str) -> list[dict]:
    """Parse LLM response text into a list of proposal dicts."""
    # Strip markdown code fences if present
    content = content.strip()
    content = re.sub(r'^```(?:json)?\s*\n?', '', content)
    content = re.sub(r'\n?```\s*$', '', content)
    content = content.strip()

    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as e:
        raise ValueError(f"LLM response is not valid JSON: {e}")

    if isinstance(parsed, dict):
        parsed = [parsed]
    if not isinstance(parsed, list):
        raise ValueError('LLM response must be a JSON array of proposal objects.')

    return parsed


def validate_proposals(proposals: list[dict], original_entries: list[dict]) -> tuple[list[dict], list[str]]:
    """Validate and sanitize LLM proposals against original entries.

    Returns:
        (valid_proposals, filtered_warnings)
    """
    original_map = {e['citation_key']: e for e in original_entries}
    valid = []
    warnings = []

    for proposal in proposals:
        if not isinstance(proposal, dict):
            warnings.append('Skipped non-dict proposal.')
            continue

        ckey = proposal.get('citation_key')
        if not ckey or ckey not in original_map:
            warnings.append(f"Skipped proposal with unknown citation_key: {ckey}")
            continue

        changes = proposal.get('changes', {})
        if not isinstance(changes, dict):
            warnings.append(f"[{ckey}] Skipped: changes is not a dict.")
            continue

        original = original_map[ckey]
        safe_changes = {}

        for field, new_val in changes.items():
            # 1. Field name whitelist
            if field not in ALLOWED_FIELDS:
                warnings.append(f"[{ckey}] Blocked unknown field: {field}")
                continue

            # 2. Don't allow setting citation_key (immutable in proposals)
            if field == 'citation_key':
                warnings.append(f"[{ckey}] Blocked attempt to change citation_key.")
                continue

            # 3. Value must be a string
            if not isinstance(new_val, str):
                warnings.append(f"[{ckey}] Blocked non-string value for {field}.")
                continue

            new_val = new_val.strip()

            # 4. Prevent deleting fields that have values
            original_val = original.get(field)
            if original_val and (not new_val):
                warnings.append(f"[{ckey}] Blocked empty value for existing field: {field}")
                continue

            # 5. Skip if no actual change
            if original_val and original_val.strip() == new_val:
                continue

            # 6. Format validation for specific fields
            if field == 'entry_type':
                if new_val.lower() not in VALID_ENTRY_TYPES:
                    warnings.append(f"[{ckey}] Blocked invalid entry_type: {new_val}")
                    continue
                new_val = new_val.lower()

            if field == 'year':
                if not re.match(r'^\d{4}$', new_val):
                    warnings.append(f"[{ckey}] Blocked invalid year: {new_val}")
                    continue

            if field == 'doi':
                if not re.match(r'^10\.\d{4,}/', new_val):
                    warnings.append(f"[{ckey}] Blocked invalid DOI: {new_val}")
                    continue

            if field == 'month':
                if new_val.lower() not in VALID_MONTHS:
                    warnings.append(f"[{ckey}] Blocked invalid month: {new_val}")
                    continue
                new_val = new_val.lower()

            if field == 'pages':
                # Allow formats like "1--10", "1-10", "e123", "123"
                if not re.match(r'^[\d]+(\s*-{1,2}\s*[\d]+)?$', new_val) and not re.match(r'^[a-zA-Z]?\d+$', new_val):
                    warnings.append(f"[{ckey}] Blocked suspicious pages format: {new_val}")
                    continue

            safe_changes[field] = new_val

        if safe_changes:
            valid.append({
                'citation_key': ckey,
                'changes': safe_changes,
            })

    return valid, warnings
