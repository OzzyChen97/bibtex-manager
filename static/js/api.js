/* API wrapper functions */
const API = {
    async request(method, path, body = null) {
        const opts = {
            method,
            headers: {},
        };
        if (body && !(body instanceof FormData)) {
            opts.headers['Content-Type'] = 'application/json';
            opts.body = JSON.stringify(body);
        } else if (body instanceof FormData) {
            opts.body = body;
        }
        const resp = await fetch(path, opts);
        if (!resp.ok) {
            const err = await resp.json().catch(() => ({ error: resp.statusText }));
            throw new Error(err.error || resp.statusText);
        }
        // Handle blob responses (export)
        const ct = resp.headers.get('Content-Type') || '';
        if (ct.includes('application/octet-stream') || resp.headers.get('Content-Disposition')) {
            return resp.blob();
        }
        return resp.json();
    },

    getEntries() { return this.request('GET', '/api/entries'); },
    getEntry(id) { return this.request('GET', `/api/entries/${id}`); },
    createEntry(data) { return this.request('POST', '/api/entries', data); },
    updateEntry(id, data) { return this.request('PUT', `/api/entries/${id}`, data); },
    deleteEntry(id) { return this.request('DELETE', `/api/entries/${id}`); },

    importBibtex(formData) {
        return fetch('/api/import/bibtex', { method: 'POST', body: formData })
            .then(r => r.json());
    },
    importBibtexText(bibtex) {
        return this.request('POST', '/api/import/bibtex', { bibtex });
    },

    exportBibtex(abbreviations = true) {
        return fetch(`/api/export/bibtex?abbreviations=${abbreviations}`)
            .then(r => {
                if (!r.ok) throw new Error('Export failed');
                return r.blob();
            });
    },

    search(query) { return this.request('GET', `/api/search?q=${encodeURIComponent(query)}`); },
    addSearchResult(data) { return this.request('POST', '/api/search/add', data); },

    findDuplicates() { return this.request('GET', '/api/library/duplicates'); },
    mergeEntries(primaryId, secondaryId) {
        return this.request('POST', '/api/library/merge', { primary_id: primaryId, secondary_id: secondaryId });
    },
    normalizeAll() { return this.request('POST', '/api/entries/normalize-all'); },

    // Export with mode
    exportBibtexWithMode(mode = 'detailed', abbreviations = true) {
        return fetch(`/api/export/bibtex?abbreviations=${abbreviations}&mode=${mode}`)
            .then(r => {
                if (!r.ok) throw new Error('Export failed');
                return r.blob();
            });
    },

    // LLM
    getLLMConfig() { return this.request('GET', '/api/llm/config'); },
    updateLLMConfig(data) { return this.request('PUT', '/api/llm/config', data); },
    llmPropose(data) { return this.request('POST', '/api/llm/propose', data); },
    llmApply(data) { return this.request('POST', '/api/llm/apply', data); },
};
