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
        const sourceLabel = result.source === 'semantic_scholar' ? '<span style="color:var(--primary);font-size:0.75rem;font-weight:600;">[Semantic Scholar]</span>' : result.source === 'scholar' ? '<span style="color:#ea580c;font-size:0.75rem;font-weight:600;">[Google Scholar]</span>' : '';
        const citations = result.citation_count ? `<span style="color:var(--text-secondary);font-size:0.78rem;">Citations: ${result.citation_count}</span>` : '';

        // For published papers, show published info and prefer published bibtex
        let publishedInfo = '';
        let bibtexToUse = result.published_bibtex || result.bibtex || '';
        let btnLabel = 'Add to Library';
        if (result.is_published && result.venue) {
            publishedInfo = `<div style="background:#f0fdf4;border:1px solid #bbf7d0;border-radius:var(--radius);padding:8px 12px;margin:8px 0;font-size:0.82rem;color:#166534;">
                Published at: <strong>${Table.esc(result.venue)}</strong>${result.doi ? ' &middot; DOI: ' + Table.esc(result.doi) : ''}
            </div>`;
            if (result.published_bibtex) {
                btnLabel = result.arxiv_id ? 'Add Published Version' : 'Add to Library';
            }
        }

        return `<div class="search-result-card">
            <h4>${Table.esc(title)}</h4>
            <div class="meta">
                ${Table.esc(authors)}<br>
                ${Table.esc(year)} ${venue ? '&middot; ' + Table.esc(venue) : ''} ${published} ${sourceLabel} ${citations}
            </div>
            ${publishedInfo}
            <div class="actions">
                <button class="btn-add-result primary" data-index="${index}" data-query="${Table.esc(query)}" data-title="${Table.esc(title)}" data-bibtex="${btoa(unescape(encodeURIComponent(bibtexToUse)))}">
                    ${btnLabel}
                </button>
            </div>
        </div>`;
    },

    async addResult(btn) {
        btn.disabled = true;
        const originalLabel = btn.textContent.trim();
        btn.textContent = 'Adding...';

        const query = btn.dataset.query;
        const title = btn.dataset.title || query;
        const bibtexB64 = btn.dataset.bibtex;
        let bibtex = '';
        try {
            bibtex = decodeURIComponent(escape(atob(bibtexB64)));
        } catch(e) {
            bibtex = '';
        }

        try {
            // When no bibtex (S2 results), use the paper title for precise resolution
            const resolveQuery = bibtex ? query : title;
            const data = bibtex ? { bibtex, query: resolveQuery } : { query: resolveQuery };
            await API.addSearchResult(data);
            App.toast('Added to library', 'success');
            btn.textContent = 'Added';
            btn.classList.remove('primary');
            Table.load();
        } catch (e) {
            App.toast('Failed to add: ' + e.message, 'error');
            btn.disabled = false;
            btn.textContent = originalLabel;
        }
    },
};
