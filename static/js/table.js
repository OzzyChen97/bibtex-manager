/* Entry list table rendering and interaction */
const Table = {
    entries: [],
    filteredEntries: [],
    selectedIds: new Set(),

    async load() {
        try {
            this.entries = await API.getEntries();
            this.applyFilter();
        } catch (e) {
            App.toast('Failed to load entries: ' + e.message, 'error');
        }
    },

    applyFilter() {
        const query = document.getElementById('filter-input').value.toLowerCase().trim();
        const sortBy = document.getElementById('sort-select').value;

        this.filteredEntries = this.entries;
        if (query) {
            this.filteredEntries = this.entries.filter(e => {
                const fields = [e.citation_key, e.title, e.author, e.year, e.journal, e.booktitle, e.doi, e.arxiv_id];
                return fields.some(f => f && f.toLowerCase().includes(query));
            });
        }

        this.filteredEntries.sort((a, b) => {
            switch (sortBy) {
                case 'year': return (b.year || '0').localeCompare(a.year || '0');
                case 'author': return (a.author || '').localeCompare(b.author || '');
                case 'title': return (a.title || '').localeCompare(b.title || '');
                default: return 0; // created_at — already sorted by server
            }
        });

        this.render();
    },

    render() {
        const tbody = document.getElementById('entry-tbody');
        const empty = document.getElementById('empty-state');
        const count = document.getElementById('entry-count');

        count.textContent = `${this.filteredEntries.length} of ${this.entries.length} entries`;

        if (this.filteredEntries.length === 0) {
            tbody.innerHTML = '';
            empty.classList.remove('hidden');
            this.updateSelectAll();
            return;
        }

        empty.classList.add('hidden');
        tbody.innerHTML = this.filteredEntries.map(e => this.renderRow(e)).join('');

        // Attach click handlers
        tbody.querySelectorAll('tr[data-id]').forEach(tr => {
            tr.addEventListener('click', (ev) => {
                if (ev.target.closest('.btn-icon') || ev.target.closest('.row-check')) return;
                Editor.open(parseInt(tr.dataset.id));
            });
        });

        tbody.querySelectorAll('.btn-delete').forEach(btn => {
            btn.addEventListener('click', async (ev) => {
                ev.stopPropagation();
                const id = parseInt(btn.dataset.id);
                if (confirm('Delete this entry?')) {
                    try {
                        await API.deleteEntry(id);
                        App.toast('Entry deleted', 'success');
                        this.selectedIds.delete(id);
                        this.load();
                    } catch (e) {
                        App.toast('Delete failed: ' + e.message, 'error');
                    }
                }
            });
        });

        // Checkbox handlers
        tbody.querySelectorAll('.row-check').forEach(cb => {
            cb.addEventListener('change', (ev) => {
                ev.stopPropagation();
                const id = parseInt(cb.dataset.id);
                if (cb.checked) {
                    this.selectedIds.add(id);
                } else {
                    this.selectedIds.delete(id);
                }
                this.updateSelectAll();
                this.updateSelectionCount();
            });
        });

        this.updateSelectAll();
        this.updateSelectionCount();
    },

    renderRow(entry) {
        const venue = entry.journal || entry.booktitle || '';
        const authorShort = entry.author ? entry.author.split(' and ')[0].split(',')[0] : '';
        const titleClean = (entry.title || '').replace(/[{}]/g, '');
        const checked = this.selectedIds.has(entry.id) ? 'checked' : '';
        return `<tr data-id="${entry.id}">
            <td class="col-check"><input type="checkbox" class="row-check" data-id="${entry.id}" ${checked}></td>
            <td class="col-status"><span class="status-dot ${entry.validation_status}" title="${entry.validation_status}"></span></td>
            <td class="col-key">${this.esc(entry.citation_key)}</td>
            <td class="col-type">${this.esc(entry.entry_type)}</td>
            <td class="col-author truncate" title="${this.esc(entry.author || '')}">${this.esc(authorShort)}${entry.author && entry.author.includes(' and ') ? ' et al.' : ''}</td>
            <td class="col-title truncate" title="${this.esc(titleClean)}">${this.esc(titleClean)}</td>
            <td class="col-venue truncate" title="${this.esc(venue)}">${this.esc(venue)}</td>
            <td class="col-year">${this.esc(entry.year || '')}</td>
            <td class="col-actions"><button class="btn-icon btn-delete" data-id="${entry.id}" title="Delete">&#128465;</button></td>
        </tr>`;
    },

    getSelectedIds() {
        return Array.from(this.selectedIds);
    },

    updateSelectAll() {
        const sa = document.getElementById('select-all');
        if (!sa) return;
        const visible = this.filteredEntries.map(e => e.id);
        if (visible.length === 0) {
            sa.checked = false;
            sa.indeterminate = false;
            return;
        }
        const selectedVisible = visible.filter(id => this.selectedIds.has(id));
        if (selectedVisible.length === 0) {
            sa.checked = false;
            sa.indeterminate = false;
        } else if (selectedVisible.length === visible.length) {
            sa.checked = true;
            sa.indeterminate = false;
        } else {
            sa.checked = false;
            sa.indeterminate = true;
        }
    },

    updateSelectionCount() {
        const el = document.getElementById('llm-selection-count');
        if (!el) return;
        const n = this.selectedIds.size;
        el.textContent = n > 0 ? `${n} selected` : '';
    },

    esc(str) {
        if (!str) return '';
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    },
};
