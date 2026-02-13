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
                Imported: ${imported.length} | Duplicates skipped: ${duplicates.length} | Errors: ${errors.length}
            </div>`;
        }

        if (duplicates.length > 0) {
            html += '<h4 style="margin: 12px 0 8px;">Duplicates Found</h4>';
            duplicates.forEach(d => {
                html += `<div class="dup-card">
                    <span class="confidence">${(d.confidence * 100).toFixed(0)}% match - ${Table.esc(d.reason)}</span>
                    <div class="entries">
                        <div class="entry-brief">
                            <strong>New</strong>
                            ${Table.esc(d.new_entry.title || '')}
                        </div>
                        <div class="entry-brief">
                            <strong>Existing</strong>
                            ${Table.esc(d.existing_entry.title || '')}
                        </div>
                    </div>
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
    },
};
