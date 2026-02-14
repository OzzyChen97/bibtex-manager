/* Import modal logic */
const Import = {
    init() {
        const modal = document.getElementById('import-modal');
        const dropZone = document.getElementById('drop-zone');
        const fileInput = document.getElementById('file-input');
        const textarea = document.getElementById('import-textarea');
        const btnPaste = document.getElementById('btn-import-paste');
        const btnSubmit = document.getElementById('btn-import-submit');
        const preview = document.getElementById('import-preview');

        // Open modal
        document.getElementById('btn-import').addEventListener('click', () => {
            this.reset();
            modal.classList.remove('hidden');
        });

        // Close modal
        modal.querySelector('.modal-close').addEventListener('click', () => modal.classList.add('hidden'));
        modal.querySelector('.modal-backdrop').addEventListener('click', () => modal.classList.add('hidden'));

        // Drag & drop
        dropZone.addEventListener('click', () => fileInput.click());
        dropZone.addEventListener('dragover', (e) => {
            e.preventDefault();
            dropZone.classList.add('dragover');
        });
        dropZone.addEventListener('dragleave', () => dropZone.classList.remove('dragover'));
        dropZone.addEventListener('drop', (e) => {
            e.preventDefault();
            dropZone.classList.remove('dragover');
            const file = e.dataTransfer.files[0];
            if (file) this.handleFile(file);
        });

        fileInput.addEventListener('change', () => {
            if (fileInput.files[0]) this.handleFile(fileInput.files[0]);
        });

        // Paste mode
        btnPaste.addEventListener('click', () => {
            dropZone.classList.add('hidden');
            preview.classList.remove('hidden');
            btnSubmit.disabled = false;
            btnPaste.classList.add('hidden');
        });

        // Submit
        btnSubmit.addEventListener('click', () => this.submit());
    },

    reset() {
        document.getElementById('drop-zone').classList.remove('hidden');
        document.getElementById('import-preview').classList.remove('hidden');
        document.getElementById('import-results').classList.add('hidden');
        document.getElementById('import-textarea').value = '';
        document.getElementById('btn-import-submit').disabled = false;
        document.getElementById('btn-import-paste').classList.remove('hidden');
        document.getElementById('file-input').value = '';
        this._fileData = null;
    },

    handleFile(file) {
        const reader = new FileReader();
        reader.onload = (e) => {
            const text = e.target.result;
            document.getElementById('import-textarea').value = text;
            document.getElementById('import-preview').classList.remove('hidden');
            document.getElementById('btn-import-submit').disabled = false;
            this._fileData = file;
        };
        reader.readAsText(file);
    },

    async submit() {
        const btn = document.getElementById('btn-import-submit');
        btn.disabled = true;
        btn.textContent = 'Importing...';

        const textarea = document.getElementById('import-textarea');
        const bibtex = textarea.value.trim();

        if (!bibtex) {
            App.toast('No BibTeX content to import', 'error');
            btn.disabled = false;
            btn.textContent = 'Import';
            return;
        }

        try {
            const result = await API.importBibtexText(bibtex);
            this.showResults(result);
            Table.load();
        } catch (e) {
            App.toast('Import failed: ' + e.message, 'error');
        } finally {
            btn.disabled = false;
            btn.textContent = 'Import';
        }
    },

    showResults(result) {
        const div = document.getElementById('import-results');
        div.classList.remove('hidden');

        const imported = result.imported || [];
        const duplicates = result.duplicates || [];
        const errors = result.errors || [];

        let html = '';

        if (imported.length > 0 && duplicates.length === 0 && errors.length === 0) {
            html += `<div class="result-summary success">Successfully imported ${imported.length} entries.</div>`;
        } else {
            html += `<div class="result-summary has-issues">
                Imported: ${imported.length} | Duplicates: ${duplicates.length} | Errors: ${errors.length}
            </div>`;
        }

        if (duplicates.length > 0) {
            html += '<h4 style="margin: 12px 0 8px;">Duplicates Found</h4>';
            duplicates.forEach((d, idx) => {
                const newAuthor = d.new_entry.author || '';
                const newYear = d.new_entry.year || '';
                const existAuthor = d.existing_entry.author || '';
                const existYear = d.existing_entry.year || '';
                html += `<div class="dup-card" id="dup-card-${idx}">
                    <span class="confidence">${(d.confidence * 100).toFixed(0)}% match - ${Table.esc(d.reason)}</span>
                    <div class="entries">
                        <div class="entry-brief">
                            <strong>New</strong>
                            ${Table.esc(d.new_entry.title || '')}
                            <div style="font-size:0.78rem;color:var(--text-secondary);margin-top:4px;">
                                ${Table.esc(newAuthor)}${newYear ? ' (' + Table.esc(newYear) + ')' : ''}
                            </div>
                        </div>
                        <div class="entry-brief">
                            <strong>Existing</strong>
                            ${Table.esc(d.existing_entry.title || '')}
                            <div style="font-size:0.78rem;color:var(--text-secondary);margin-top:4px;">
                                ${Table.esc(existAuthor)}${existYear ? ' (' + Table.esc(existYear) + ')' : ''}
                            </div>
                        </div>
                    </div>
                    <div class="dup-actions" style="margin-top:10px;display:flex;gap:8px;">
                        <button class="secondary dup-btn" data-action="skip" data-idx="${idx}">Skip</button>
                        <button class="primary dup-btn" data-action="import_anyway" data-idx="${idx}">Import Anyway</button>
                        <button class="secondary dup-btn" data-action="replace" data-idx="${idx}" style="border-color:var(--warning);color:var(--warning);">Replace Existing</button>
                    </div>
                    <div class="dup-status" style="display:none;margin-top:8px;font-size:0.85rem;font-weight:600;"></div>
                </div>`;
            });
        }

        if (errors.length > 0) {
            html += '<h4 style="margin: 12px 0 8px;">Errors</h4>';
            errors.forEach(e => {
                html += `<div style="color: var(--error); font-size: 0.85rem;">
                    ${Table.esc(e.citation_key)}: ${Table.esc(e.error)}
                </div>`;
            });
        }

        div.innerHTML = html;

        // Attach duplicate action button handlers
        div.querySelectorAll('.dup-btn').forEach(btn => {
            btn.addEventListener('click', () => this.handleDuplicateAction(btn, duplicates));
        });
    },

    async handleDuplicateAction(btn, duplicates) {
        const idx = parseInt(btn.dataset.idx);
        const action = btn.dataset.action;
        const dup = duplicates[idx];
        const card = document.getElementById(`dup-card-${idx}`);
        const actionsDiv = card.querySelector('.dup-actions');
        const statusDiv = card.querySelector('.dup-status');

        // Disable all buttons in this card
        card.querySelectorAll('.dup-btn').forEach(b => b.disabled = true);

        if (action === 'skip') {
            card.style.opacity = '0.5';
            actionsDiv.style.display = 'none';
            statusDiv.style.display = 'block';
            statusDiv.style.color = 'var(--text-secondary)';
            statusDiv.textContent = 'Skipped';
            return;
        }

        try {
            const data = {
                action: action,
                new_entry: dup.new_entry,
                existing_entry_id: dup.existing_entry.id,
            };
            await API.resolveDuplicate(data);

            actionsDiv.style.display = 'none';
            statusDiv.style.display = 'block';

            if (action === 'import_anyway') {
                statusDiv.style.color = 'var(--success)';
                statusDiv.textContent = 'Imported';
            } else if (action === 'replace') {
                statusDiv.style.color = 'var(--primary)';
                statusDiv.textContent = 'Replaced';
            }
            Table.load();
        } catch (e) {
            App.toast('Failed: ' + e.message, 'error');
            card.querySelectorAll('.dup-btn').forEach(b => b.disabled = false);
        }
    },
};
