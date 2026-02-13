/* Search modal logic */
const Search = {
    init() {
        const modal = document.getElementById('search-modal');

        document.getElementById('btn-search').addEventListener('click', () => {
            this.reset();
            modal.classList.remove('hidden');
            document.getElementById('search-input').focus();
        });

        modal.querySelector('.modal-close').addEventListener('click', () => modal.classList.add('hidden'));
        modal.querySelector('.modal-backdrop').addEventListener('click', () => modal.classList.add('hidden'));

        document.getElementById('btn-search-go').addEventListener('click', () => this.doSearch());
        document.getElementById('search-input').addEventListener('keydown', (e) => {
            if (e.key === 'Enter') this.doSearch();
        });
    },

    reset() {
        document.getElementById('search-input').value = '';
        document.getElementById('search-status').classList.add('hidden');
        document.getElementById('search-results').classList.add('hidden');
    },

    async doSearch() {
        const query = document.getElementById('search-input').value.trim();
        if (!query) return;

        const statusDiv = document.getElementById('search-status');
        const resultsDiv = document.getElementById('search-results');

        statusDiv.className = 'loading';
        statusDiv.innerHTML = 'Searching... <span class="spinner"></span>';
        statusDiv.classList.remove('hidden');
        resultsDiv.classList.add('hidden');

        try {
            const data = await API.search(query);
            statusDiv.classList.add('hidden');

            const results = data.results || [];
            if (results.length === 0) {
                statusDiv.className = 'error';
                statusDiv.textContent = 'No results found.';
                statusDiv.classList.remove('hidden');
                return;
            }

            resultsDiv.classList.remove('hidden');
            resultsDiv.innerHTML = results.map((r, i) => this.renderResult(r, i, query)).join('');

            // Attach add buttons
            resultsDiv.querySelectorAll('.btn-add-result').forEach(btn => {
                btn.addEventListener('click', () => this.addResult(btn));
            });
        } catch (e) {
            statusDiv.className = 'error';
            statusDiv.textContent = 'Search failed: ' + e.message;
            statusDiv.classList.remove('hidden');
        }
    },

    renderResult(result, index, query) {
        const title = result.title || 'Untitled';
        const authors = result.authors || '';
        const year = result.year || '';
        const venue = result.venue || '';
        const published = result.is_published ? '<span style="color:var(--success);">[Published]</span>' : '<span style="color:var(--text-secondary);">[Preprint]</span>';

        return `<div class="search-result-card">
            <h4>${Table.esc(title)}</h4>
            <div class="meta">
                ${Table.esc(authors)}<br>
                ${Table.esc(year)} ${venue ? '&middot; ' + Table.esc(venue) : ''} ${published}
            </div>
            <div class="actions">
                <button class="btn-add-result primary" data-index="${index}" data-query="${Table.esc(query)}" data-bibtex="${btoa(unescape(encodeURIComponent(result.bibtex || '')))}">
                    Add to Library
                </button>
            </div>
        </div>`;
    },

    async addResult(btn) {
        btn.disabled = true;
        btn.textContent = 'Adding...';

        const query = btn.dataset.query;
        const bibtexB64 = btn.dataset.bibtex;
        let bibtex = '';
        try {
            bibtex = decodeURIComponent(escape(atob(bibtexB64)));
        } catch(e) {
            bibtex = '';
        }

        try {
            const data = bibtex ? { bibtex, query } : { query };
            await API.addSearchResult(data);
            App.toast('Added to library', 'success');
            btn.textContent = 'Added';
            btn.classList.remove('primary');
            Table.load();
        } catch (e) {
            App.toast('Failed to add: ' + e.message, 'error');
            btn.disabled = false;
            btn.textContent = 'Add to Library';
        }
    },
};
