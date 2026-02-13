/* Editor panel for editing individual entries */
const Editor = {
    currentId: null,
    fields: [
        'citation_key', 'entry_type', 'title', 'author', 'year', 'month',
        'journal', 'booktitle', 'volume', 'number', 'pages', 'doi',
        'arxiv_id', 'url', 'publisher', 'abstract',
    ],

    init() {
        document.getElementById('btn-editor-close').addEventListener('click', () => this.close());
        document.getElementById('btn-editor-save').addEventListener('click', () => this.save());
        document.getElementById('btn-editor-delete').addEventListener('click', () => this.delete());

        // Live preview on input change
        this.fields.forEach(f => {
            const el = document.getElementById('edit-' + f);
            if (el) {
                el.addEventListener('input', () => this.updatePreview());
            }
        });
    },

    async open(id) {
        try {
            const entry = await API.getEntry(id);
            this.currentId = id;
            this.populate(entry);
            document.getElementById('editor-panel').classList.remove('hidden');
        } catch (e) {
            App.toast('Failed to load entry: ' + e.message, 'error');
        }
    },

    close() {
        document.getElementById('editor-panel').classList.add('hidden');
        this.currentId = null;
    },

    populate(entry) {
        this.fields.forEach(f => {
            const el = document.getElementById('edit-' + f);
            if (el) {
                el.value = entry[f] || '';
            }
        });
        document.getElementById('edit-id').value = entry.id;

        // Show validation messages
        const valDiv = document.getElementById('editor-validation');
        const messages = entry.validation_messages || [];
        if (messages.length > 0) {
            valDiv.innerHTML = messages.map(m => {
                const cls = m.startsWith('Missing required') ? 'msg-error' : 'msg-warning';
                return `<div class="${cls}">${Table.esc(m)}</div>`;
            }).join('');
        } else {
            valDiv.innerHTML = '<div style="color: var(--success);">All fields valid</div>';
        }

        this.updatePreview();
    },

    updatePreview() {
        const data = {};
        this.fields.forEach(f => {
            const el = document.getElementById('edit-' + f);
            if (el && el.value) {
                data[f] = el.value;
            }
        });

        // Build a simple BibTeX preview
        const type = data.entry_type || 'misc';
        const key = data.citation_key || 'unknown';
        const lines = [`@${type}{${key},`];

        const order = ['author', 'title', 'journal', 'booktitle', 'year', 'month',
                       'volume', 'number', 'pages', 'doi', 'url', 'publisher', 'abstract'];
        const shownFields = [];
        order.forEach(f => { if (data[f]) shownFields.push(f); });
        Object.keys(data).forEach(f => {
            if (!order.includes(f) && f !== 'entry_type' && f !== 'citation_key') {
                shownFields.push(f);
            }
        });

        shownFields.forEach((f, i) => {
            const val = data[f];
            const comma = i < shownFields.length - 1 ? ',' : '';
            if (f === 'arxiv_id') {
                lines.push(`  eprint = {${val}}${comma}`);
            } else {
                lines.push(`  ${f} = {${val}}${comma}`);
            }
        });
        lines.push('}');

        document.getElementById('bibtex-preview-code').textContent = lines.join('\n');
    },

    async save() {
        if (!this.currentId) return;

        const data = {};
        this.fields.forEach(f => {
            const el = document.getElementById('edit-' + f);
            if (el) {
                data[f] = el.value || null;
            }
        });

        try {
            await API.updateEntry(this.currentId, data);
            App.toast('Entry saved', 'success');
            Table.load();
            // Reload to show updated validation
            const updated = await API.getEntry(this.currentId);
            this.populate(updated);
        } catch (e) {
            App.toast('Save failed: ' + e.message, 'error');
        }
    },

    async delete() {
        if (!this.currentId) return;
        if (!confirm('Delete this entry?')) return;

        try {
            await API.deleteEntry(this.currentId);
            App.toast('Entry deleted', 'success');
            this.close();
            Table.load();
        } catch (e) {
            App.toast('Delete failed: ' + e.message, 'error');
        }
    },
};
