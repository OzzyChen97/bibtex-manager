"""Flask application entry point for BibTeX Manager."""
import json
import logging
import os
from flask import Flask, request, jsonify, send_file, render_template
from io import BytesIO

from config import DATABASE, SCHOLAR_PROXY, SCHOLAR_MIN_DELAY, SCHOLAR_MAX_DELAY, USE_ABBREVIATIONS, PORT, DEBUG, BASE_PATH
from models.database import Database
from models.entry import BibEntry
from services.parser import parse_bibtex, entries_to_bibtex, entry_to_bibtex
from services.normalizer import normalize_entry
from services.deduplicator import find_duplicates, merge_entries
from services.validator import validate_entry, validate_entries
from services.abbreviations import abbreviate
from services.llm import load_config as llm_load_config, save_config as llm_save_config, mask_api_key, call_llm
from apis.resolver import Resolver

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__,
            template_folder=os.path.join(BASE_PATH, 'templates'),
            static_folder=os.path.join(BASE_PATH, 'static'))
db = Database(DATABASE)
resolver = Resolver(
    scholar_proxy=SCHOLAR_PROXY,
    scholar_min_delay=SCHOLAR_MIN_DELAY,
    scholar_max_delay=SCHOLAR_MAX_DELAY,
)


@app.route('/')
def index():
    return render_template('index.html')


# ── Entry CRUD ────────────────────────────────────────────────

@app.route('/api/entries', methods=['GET'])
def list_entries():
    entries = db.get_all_entries()
    return jsonify([e.to_dict() for e in entries])


@app.route('/api/entries', methods=['POST'])
def create_entry():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    # Accept raw bibtex string
    if 'bibtex' in data:
        try:
            entries = parse_bibtex(data['bibtex'])
            if not entries:
                return jsonify({'error': 'Could not parse BibTeX'}), 400
            existing_keys = {e.citation_key for e in db.get_all_entries()}
            entry = normalize_entry(entries[0], existing_keys)
            status, messages = validate_entry(entry)
            entry.validation_status = status
            entry.validation_messages = json.dumps(messages)
            entry.raw_bibtex = entry_to_bibtex(entry)
            entry_id = db.insert_entry(entry)
            created = db.get_entry(entry_id)
            return jsonify(created.to_dict()), 201
        except Exception as e:
            return jsonify({'error': str(e)}), 400

    # Accept field dict
    required = ('citation_key', 'entry_type')
    for f in required:
        if f not in data:
            return jsonify({'error': f'Missing required field: {f}'}), 400

    entry = BibEntry(**{k: v for k, v in data.items() if k in BibEntry.__dataclass_fields__})
    existing_keys = {e.citation_key for e in db.get_all_entries()}
    entry = normalize_entry(entry, existing_keys)
    status, messages = validate_entry(entry)
    entry.validation_status = status
    entry.validation_messages = json.dumps(messages)
    entry.raw_bibtex = entry_to_bibtex(entry)
    entry_id = db.insert_entry(entry)
    created = db.get_entry(entry_id)
    return jsonify(created.to_dict()), 201


@app.route('/api/entries/<int:entry_id>', methods=['GET'])
def get_entry(entry_id):
    entry = db.get_entry(entry_id)
    if not entry:
        return jsonify({'error': 'Entry not found'}), 404
    return jsonify(entry.to_dict())


@app.route('/api/entries/<int:entry_id>', methods=['PUT'])
def update_entry(entry_id):
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    entry = db.get_entry(entry_id)
    if not entry:
        return jsonify({'error': 'Entry not found'}), 404

    # Update fields
    updatable = [
        'citation_key', 'entry_type', 'title', 'author', 'year', 'month',
        'journal', 'booktitle', 'volume', 'number', 'pages', 'doi',
        'arxiv_id', 'url', 'abstract', 'publisher', 'editor', 'series',
        'address', 'organization', 'school', 'institution', 'note', 'keywords',
    ]
    updates = {k: v for k, v in data.items() if k in updatable}

    # Apply updates to entry object for re-validation
    for k, v in updates.items():
        setattr(entry, k, v)

    status, messages = validate_entry(entry)
    updates['validation_status'] = status
    updates['validation_messages'] = json.dumps(messages)
    updates['raw_bibtex'] = entry_to_bibtex(entry)

    db.update_entry(entry_id, updates)
    updated = db.get_entry(entry_id)
    return jsonify(updated.to_dict())


@app.route('/api/entries/<int:entry_id>', methods=['DELETE'])
def delete_entry(entry_id):
    if db.delete_entry(entry_id):
        return jsonify({'message': 'Deleted'})
    return jsonify({'error': 'Entry not found'}), 404


# ── Import / Export ───────────────────────────────────────────

@app.route('/api/import/bibtex', methods=['POST'])
def import_bibtex():
    bibtex_str = None

    if request.content_type and 'multipart/form-data' in request.content_type:
        f = request.files.get('file')
        if not f:
            return jsonify({'error': 'No file uploaded'}), 400
        bibtex_str = f.read().decode('utf-8', errors='replace')
    else:
        data = request.get_json()
        if data and 'bibtex' in data:
            bibtex_str = data['bibtex']

    if not bibtex_str:
        return jsonify({'error': 'No BibTeX data provided'}), 400

    try:
        entries = parse_bibtex(bibtex_str)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400

    if not entries:
        return jsonify({'error': 'No entries found in BibTeX'}), 400

    existing = db.get_all_entries()
    existing_keys = {e.citation_key for e in existing}
    results = {'imported': [], 'duplicates': [], 'errors': []}

    for entry in entries:
        try:
            entry = normalize_entry(entry, existing_keys)
            status, messages = validate_entry(entry)
            entry.validation_status = status
            entry.validation_messages = json.dumps(messages)
            entry.raw_bibtex = entry_to_bibtex(entry)
            entry.source = 'import'

            # Check for duplicates
            is_dup = False
            for ex in existing:
                from services.deduplicator import check_duplicate
                dup = check_duplicate(entry, ex)
                if dup and dup['confidence'] >= 0.85:
                    results['duplicates'].append({
                        'new_entry': entry.to_dict(),
                        'existing_entry': ex.to_dict(),
                        'confidence': dup['confidence'],
                        'reason': dup['reason'],
                    })
                    is_dup = True
                    break

            if not is_dup:
                entry_id = db.insert_entry(entry)
                existing_keys.add(entry.citation_key)
                created = db.get_entry(entry_id)
                existing.append(created)
                results['imported'].append(created.to_dict())
        except Exception as e:
            results['errors'].append({
                'citation_key': entry.citation_key,
                'error': str(e),
            })

    return jsonify(results)


@app.route('/api/import/resolve-duplicate', methods=['POST'])
def resolve_duplicate():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    action = data.get('action')
    new_entry_data = data.get('new_entry')
    existing_entry_id = data.get('existing_entry_id')

    if action not in ('skip', 'import_anyway', 'replace'):
        return jsonify({'error': 'Invalid action. Use: skip, import_anyway, replace'}), 400
    if not new_entry_data:
        return jsonify({'error': 'Missing new_entry data'}), 400

    if action == 'skip':
        return jsonify({'message': 'Skipped', 'action': 'skip'})

    try:
        # Reconstruct BibEntry from the dict
        field_names = {f for f in BibEntry.__dataclass_fields__}
        skip_fields = {'id', 'created_at', 'updated_at',
                       'validation_status', 'validation_messages',
                       'raw_bibtex', '_extra_fields'}
        entry_kwargs = {}
        for k, v in new_entry_data.items():
            if k in field_names and k not in skip_fields:
                # Skip None values for optional fields (keep only citation_key, entry_type, and non-None)
                if v is not None or k in ('citation_key', 'entry_type'):
                    entry_kwargs[k] = v if v is not None else ''
        new_entry = BibEntry(**entry_kwargs)

        existing_keys = {e.citation_key for e in db.get_all_entries()}

        if action == 'import_anyway':
            new_entry = normalize_entry(new_entry, existing_keys)
            status, messages = validate_entry(new_entry)
            new_entry.validation_status = status
            new_entry.validation_messages = json.dumps(messages)
            new_entry.raw_bibtex = entry_to_bibtex(new_entry)
            new_entry.source = 'import'
            entry_id = db.insert_entry(new_entry)
            created = db.get_entry(entry_id)
            return jsonify({'message': 'Imported', 'action': 'import_anyway', 'entry': created.to_dict()}), 201

        elif action == 'replace':
            if existing_entry_id is None:
                return jsonify({'error': 'Missing existing_entry_id for replace action'}), 400
            existing_entry = db.get_entry(int(existing_entry_id))
            if not existing_entry:
                return jsonify({'error': 'Existing entry not found'}), 404

            # Update existing entry fields with new entry data
            updatable = [
                'citation_key', 'entry_type', 'title', 'author', 'year', 'month',
                'journal', 'booktitle', 'volume', 'number', 'pages', 'doi',
                'arxiv_id', 'url', 'abstract', 'publisher', 'editor', 'series',
                'address', 'organization', 'school', 'institution', 'note', 'keywords',
            ]
            for field in updatable:
                val = new_entry_data.get(field)
                if val is not None:
                    setattr(existing_entry, field, val)

            other_keys = existing_keys - {existing_entry.citation_key}
            existing_entry = normalize_entry(existing_entry, other_keys)
            status, messages = validate_entry(existing_entry)

            updates = {k: v for k, v in existing_entry.to_dict().items()
                       if k not in ('id', '_extra_fields', 'created_at', 'updated_at') and v is not None}
            updates['validation_status'] = status
            updates['validation_messages'] = json.dumps(messages)
            updates['raw_bibtex'] = entry_to_bibtex(existing_entry)

            db.update_entry(int(existing_entry_id), updates)
            updated = db.get_entry(int(existing_entry_id))
            return jsonify({'message': 'Replaced', 'action': 'replace', 'entry': updated.to_dict()})

    except Exception as e:
        logger.error(f"Resolve duplicate failed: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/export/bibtex', methods=['GET'])
def export_bibtex():
    entries = db.get_all_for_export()
    use_abbrev = request.args.get('abbreviations', str(USE_ABBREVIATIONS)).lower() in ('true', '1', 'yes')
    mode = request.args.get('mode', 'detailed')
    if mode not in ('detailed', 'standard', 'minimal'):
        mode = 'detailed'

    if use_abbrev:
        for entry in entries:
            if entry.journal:
                entry.journal = abbreviate(entry.journal)
            if entry.booktitle:
                entry.booktitle = abbreviate(entry.booktitle)

    bibtex_str = entries_to_bibtex(entries, use_abbreviations=use_abbrev, mode=mode)

    filenames = {
        'detailed': 'references_detailed.bib',
        'standard': 'references.bib',
        'minimal': 'references_minimal.bib',
    }

    buf = BytesIO(bibtex_str.encode('utf-8'))
    buf.seek(0)
    return send_file(buf, mimetype='text/plain', as_attachment=True,
                     download_name=filenames[mode])


# ── Search ────────────────────────────────────────────────────

@app.route('/api/search', methods=['GET'])
def search_papers():
    query = request.args.get('q', '').strip()
    if not query:
        return jsonify({'error': 'No query provided'}), 400

    try:
        results = resolver.search(query)
        return jsonify({'results': results, 'query': query})
    except Exception as e:
        logger.error(f"Search failed: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/search/add', methods=['POST'])
def add_search_result():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    query = data.get('query', '').strip()
    bibtex_str = data.get('bibtex')

    existing_keys = {e.citation_key for e in db.get_all_entries()}

    if bibtex_str:
        # Parse provided BibTeX
        try:
            entries = parse_bibtex(bibtex_str)
            if entries:
                entry = entries[0]
                entry.source = 'scholar'
                entry = normalize_entry(entry, existing_keys)
                status, messages = validate_entry(entry)
                entry.validation_status = status
                entry.validation_messages = json.dumps(messages)
                entry.raw_bibtex = entry_to_bibtex(entry)
                entry_id = db.insert_entry(entry)
                created = db.get_entry(entry_id)
                return jsonify(created.to_dict()), 201
        except Exception as e:
            return jsonify({'error': str(e)}), 400

    if query:
        # Resolve the query
        result = resolver.resolve(query, existing_keys)
        if result.get('error') and not result.get('entry'):
            return jsonify({'error': result['error']}), 404
        if result.get('entry'):
            entry = result['entry']
            status, messages = validate_entry(entry)
            entry.validation_status = status
            entry.validation_messages = json.dumps(messages)
            entry.raw_bibtex = entry_to_bibtex(entry)
            entry_id = db.insert_entry(entry)
            created = db.get_entry(entry_id)
            resp = created.to_dict()
            resp['source_info'] = result.get('source_info', {})
            return jsonify(resp), 201

    return jsonify({'error': 'Provide either bibtex or query'}), 400


# ── Library utilities ─────────────────────────────────────────

@app.route('/api/library/duplicates', methods=['GET'])
def find_library_duplicates():
    entries = db.get_all_entries()
    dups = find_duplicates(entries)
    return jsonify({'duplicates': dups})


@app.route('/api/library/merge', methods=['POST'])
def merge_library_entries():
    data = request.get_json()
    primary_id = data.get('primary_id')
    secondary_id = data.get('secondary_id')

    if not primary_id or not secondary_id:
        return jsonify({'error': 'Provide primary_id and secondary_id'}), 400

    primary = db.get_entry(primary_id)
    secondary = db.get_entry(secondary_id)

    if not primary or not secondary:
        return jsonify({'error': 'Entry not found'}), 404

    merged = merge_entries(primary, secondary)
    status, messages = validate_entry(merged)

    updates = {k: v for k, v in merged.to_dict().items()
               if k not in ('id', '_extra_fields', 'created_at', 'updated_at') and v is not None}
    updates['validation_status'] = status
    updates['validation_messages'] = json.dumps(messages)
    updates['raw_bibtex'] = entry_to_bibtex(merged)

    db.update_entry(primary_id, updates)
    db.delete_entry(secondary_id)

    result = db.get_entry(primary_id)
    return jsonify(result.to_dict())


@app.route('/api/entries/normalize-all', methods=['POST'])
def normalize_all_entries():
    entries = db.get_all_entries()
    existing_keys = set()
    updated_count = 0

    for entry in entries:
        entry = normalize_entry(entry, existing_keys)
        status, messages = validate_entry(entry)
        updates = {k: v for k, v in entry.to_dict().items()
                   if k not in ('id', '_extra_fields', 'created_at', 'updated_at') and v is not None}
        updates['validation_status'] = status
        updates['validation_messages'] = json.dumps(messages)
        updates['raw_bibtex'] = entry_to_bibtex(entry)
        db.update_entry(entry.id, updates)
        updated_count += 1

    return jsonify({'message': f'Normalized {updated_count} entries', 'count': updated_count})


# ── LLM Integration ──────────────────────────────────────────

@app.route('/api/llm/config', methods=['GET'])
def get_llm_config():
    config = llm_load_config()
    return jsonify({
        'base_url': config.get('base_url', ''),
        'api_key': mask_api_key(config.get('api_key', '')),
        'model': config.get('model', ''),
    })


@app.route('/api/llm/config', methods=['PUT'])
def update_llm_config():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    current = llm_load_config()
    new_config = {
        'base_url': data.get('base_url', current.get('base_url', '')),
        'model': data.get('model', current.get('model', '')),
    }
    # Only update api_key if a real (non-masked) value is provided
    new_key = data.get('api_key', '')
    if new_key and '*' not in new_key:
        new_config['api_key'] = new_key
    else:
        new_config['api_key'] = current.get('api_key', '')

    llm_save_config(new_config)
    return jsonify({
        'base_url': new_config['base_url'],
        'api_key': mask_api_key(new_config['api_key']),
        'model': new_config['model'],
    })


@app.route('/api/llm/propose', methods=['POST'])
def llm_propose():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    entry_ids = data.get('entry_ids', [])
    preset = data.get('preset')
    custom_prompt = data.get('custom_prompt')

    if not entry_ids:
        return jsonify({'error': 'No entries selected'}), 400
    if not preset and not custom_prompt:
        return jsonify({'error': 'No preset or custom prompt provided'}), 400

    entries = []
    for eid in entry_ids:
        entry = db.get_entry(eid)
        if entry:
            entries.append(entry.to_dict())

    if not entries:
        return jsonify({'error': 'No valid entries found'}), 404

    try:
        result = call_llm(entries, preset=preset, custom_prompt=custom_prompt)
        return jsonify(result)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"LLM propose failed: {e}")
        return jsonify({'error': f'LLM request failed: {e}'}), 500


@app.route('/api/llm/apply', methods=['POST'])
def llm_apply():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    proposals = data.get('proposals', [])
    if not proposals:
        return jsonify({'error': 'No proposals to apply'}), 400

    applied = []
    errors = []

    for proposal in proposals:
        ckey = proposal.get('citation_key')
        changes = proposal.get('changes', {})
        if not ckey or not changes:
            continue

        entry = db.get_entry_by_key(ckey)
        if not entry:
            errors.append(f"Entry not found: {ckey}")
            continue

        # Apply changes
        updatable = [
            'citation_key', 'entry_type', 'title', 'author', 'year', 'month',
            'journal', 'booktitle', 'volume', 'number', 'pages', 'doi',
            'arxiv_id', 'url', 'abstract', 'publisher', 'editor', 'series',
            'address', 'organization', 'school', 'institution', 'note', 'keywords',
        ]
        updates = {k: v for k, v in changes.items() if k in updatable}
        for k, v in updates.items():
            setattr(entry, k, v)

        # Re-normalize and validate
        existing_keys = {e.citation_key for e in db.get_all_entries()} - {entry.citation_key}
        entry = normalize_entry(entry, existing_keys)
        status, messages = validate_entry(entry)
        updates['validation_status'] = status
        updates['validation_messages'] = json.dumps(messages)
        updates['raw_bibtex'] = entry_to_bibtex(entry)

        db.update_entry(entry.id, updates)
        applied.append(ckey)

    return jsonify({'applied': applied, 'errors': errors})


if __name__ == '__main__':
    import webbrowser, threading
    def _open_browser():
        webbrowser.open(f'http://127.0.0.1:{PORT}')
    threading.Timer(1.5, _open_browser).start()
    app.run(host='0.0.0.0', port=PORT, debug=DEBUG)
