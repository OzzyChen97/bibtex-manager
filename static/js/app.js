/* Main application initialization and utilities */
const App = {
    init() {
        Editor.init();
        Import.init();
        Search.init();
        LLM.init();
        Table.load();

        // Filter & sort
        document.getElementById('filter-input').addEventListener('input', () => Table.applyFilter());
        document.getElementById('sort-select').addEventListener('change', () => Table.applyFilter());

        // Select all checkbox
        document.getElementById('select-all').addEventListener('change', (ev) => {
            const checked = ev.target.checked;
            Table.filteredEntries.forEach(e => {
                if (checked) {
                    Table.selectedIds.add(e.id);
                } else {
                    Table.selectedIds.delete(e.id);
                }
            });
            Table.render();
        });

        // Normalize all
        document.getElementById('btn-normalize').addEventListener('click', async () => {
            if (!confirm('Normalize all entries? This will regenerate citation keys and standardize fields.')) return;
            try {
                const result = await API.normalizeAll();
                App.toast(result.message, 'success');
                Table.load();
            } catch (e) {
                App.toast('Normalization failed: ' + e.message, 'error');
            }
        });

        // Find duplicates
        document.getElementById('btn-duplicates').addEventListener('click', () => this.showDuplicates());

        // Export dropdown
        const exportBtn = document.getElementById('btn-export');
        const exportDropdown = document.getElementById('export-dropdown');
        exportBtn.addEventListener('click', (ev) => {
            ev.stopPropagation();
            exportDropdown.classList.toggle('hidden');
        });
        document.querySelectorAll('.export-option').forEach(btn => {
            btn.addEventListener('click', (ev) => {
                ev.stopPropagation();
                exportDropdown.classList.add('hidden');
                this.exportBib(btn.dataset.mode);
            });
        });
        document.addEventListener('click', () => {
            exportDropdown.classList.add('hidden');
        });

        // Close duplicates modal
        const dupModal = document.getElementById('duplicates-modal');
        dupModal.querySelector('.modal-close').addEventListener('click', () => dupModal.classList.add('hidden'));
        dupModal.querySelector('.modal-backdrop').addEventListener('click', () => dupModal.classList.add('hidden'));
    },

    async showDuplicates() {
        const modal = document.getElementById('duplicates-modal');
        const list = document.getElementById('duplicates-list');
        list.innerHTML = '<p>Scanning for duplicates...</p>';
        modal.classList.remove('hidden');

        try {
            const data = await API.findDuplicates();
            const dups = data.duplicates || [];

            if (dups.length === 0) {
                list.innerHTML = '<p>No duplicates found.</p>';
                return;
            }

            // We need entry details for display
            const entries = await API.getEntries();
            const entryMap = {};
            entries.forEach(e => { entryMap[e.id] = e; });

            list.innerHTML = dups.map(d => {
                const e1 = entryMap[d.entry1_id] || {};
                const e2 = entryMap[d.entry2_id] || {};
                return `<div class="dup-card">
                    <span class="confidence">${(d.confidence * 100).toFixed(0)}% match - ${Table.esc(d.reason)}</span>
                    <div class="entries">
                        <div class="entry-brief">
                            <strong>${Table.esc(e1.citation_key || '?')}</strong>
                            ${Table.esc(e1.title || '')}
                            <br><small>${Table.esc(e1.year || '')} ${Table.esc(e1.journal || e1.booktitle || '')}</small>
                        </div>
                        <div class="entry-brief">
                            <strong>${Table.esc(e2.citation_key || '?')}</strong>
                            ${Table.esc(e2.title || '')}
                            <br><small>${Table.esc(e2.year || '')} ${Table.esc(e2.journal || e2.booktitle || '')}</small>
                        </div>
                    </div>
                    <div style="margin-top: 8px; display: flex; gap: 8px;">
                        <button class="secondary btn-merge" data-primary="${d.entry1_id}" data-secondary="${d.entry2_id}">Keep Left, Merge Right</button>
                        <button class="secondary btn-merge" data-primary="${d.entry2_id}" data-secondary="${d.entry1_id}">Keep Right, Merge Left</button>
                    </div>
                </div>`;
            }).join('');

            list.querySelectorAll('.btn-merge').forEach(btn => {
                btn.addEventListener('click', async () => {
                    btn.disabled = true;
                    btn.textContent = 'Merging...';
                    try {
                        await API.mergeEntries(parseInt(btn.dataset.primary), parseInt(btn.dataset.secondary));
                        App.toast('Entries merged', 'success');
                        Table.load();
                        // Refresh duplicates view
                        this.showDuplicates();
                    } catch (e) {
                        App.toast('Merge failed: ' + e.message, 'error');
                        btn.disabled = false;
                        btn.textContent = 'Merge';
                    }
                });
            });
        } catch (e) {
            list.innerHTML = `<p style="color:var(--error);">Failed to scan: ${Table.esc(e.message)}</p>`;
        }
    },

    async exportBib(mode = 'detailed') {
        try {
            const blob = await API.exportBibtexWithMode(mode, true);
            const filenames = {
                detailed: 'references_detailed.bib',
                standard: 'references.bib',
                minimal: 'references_minimal.bib',
            };
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = filenames[mode] || 'references.bib';
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
            App.toast(`Exported ${filenames[mode] || 'references.bib'}`, 'success');
        } catch (e) {
            App.toast('Export failed: ' + e.message, 'error');
        }
    },

    toast(message, type = 'info') {
        const container = document.getElementById('toast-container');
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        toast.textContent = message;
        container.appendChild(toast);
        setTimeout(() => {
            toast.style.opacity = '0';
            toast.style.transition = 'opacity 0.3s';
            setTimeout(() => toast.remove(), 300);
        }, 4000);
    },
};

// Boot
document.addEventListener('DOMContentLoaded', () => App.init());
