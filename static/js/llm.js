/* LLM integration frontend */
const LLM = {
    init() {
        this.initSettingsModal();
        this.initPresetButtons();
        this.initCustomModal();
        this.initDiffModal();
    },

    // ── Settings Modal ──────────────────────────────────────
    initSettingsModal() {
        const modal = document.getElementById('llm-settings-modal');
        const btn = document.getElementById('btn-llm-settings');
        const saveBtn = document.getElementById('btn-llm-settings-save');

        btn.addEventListener('click', async () => {
            modal.classList.remove('hidden');
            try {
                const config = await API.getLLMConfig();
                document.getElementById('llm-base-url').value = config.base_url || '';
                document.getElementById('llm-api-key').value = config.api_key || '';
                document.getElementById('llm-model').value = config.model || '';
            } catch (e) {
                App.toast('Failed to load LLM config: ' + e.message, 'error');
            }
        });

        modal.querySelector('.modal-close').addEventListener('click', () => modal.classList.add('hidden'));
        modal.querySelector('.modal-backdrop').addEventListener('click', () => modal.classList.add('hidden'));

        saveBtn.addEventListener('click', async () => {
            const data = {
                base_url: document.getElementById('llm-base-url').value.trim(),
                api_key: document.getElementById('llm-api-key').value.trim(),
                model: document.getElementById('llm-model').value.trim(),
            };
            try {
                const result = await API.updateLLMConfig(data);
                document.getElementById('llm-api-key').value = result.api_key || '';
                App.toast('LLM settings saved', 'success');
                modal.classList.add('hidden');
            } catch (e) {
                App.toast('Failed to save: ' + e.message, 'error');
            }
        });
    },

    // ── Preset Buttons ──────────────────────────────────────
    initPresetButtons() {
        document.querySelectorAll('.llm-preset-btn[data-preset]').forEach(btn => {
            btn.addEventListener('click', () => {
                const ids = Table.getSelectedIds();
                if (ids.length === 0) {
                    App.toast('Select at least one entry first', 'info');
                    return;
                }
                this.propose(ids, btn.dataset.preset, null);
            });
        });
    },

    // ── Custom Prompt Modal ─────────────────────────────────
    initCustomModal() {
        const modal = document.getElementById('llm-custom-modal');
        const btn = document.getElementById('btn-llm-custom');
        const submitBtn = document.getElementById('btn-llm-custom-submit');

        btn.addEventListener('click', () => {
            const ids = Table.getSelectedIds();
            if (ids.length === 0) {
                App.toast('Select at least one entry first', 'info');
                return;
            }
            document.getElementById('llm-custom-prompt').value = '';
            modal.classList.remove('hidden');
        });

        modal.querySelector('.modal-close').addEventListener('click', () => modal.classList.add('hidden'));
        modal.querySelector('.modal-backdrop').addEventListener('click', () => modal.classList.add('hidden'));

        submitBtn.addEventListener('click', () => {
            const prompt = document.getElementById('llm-custom-prompt').value.trim();
            if (!prompt) {
                App.toast('Please enter a prompt', 'info');
                return;
            }
            modal.classList.add('hidden');
            const ids = Table.getSelectedIds();
            this.propose(ids, null, prompt);
        });
    },

    // ── Diff Preview Modal ──────────────────────────────────
    initDiffModal() {
        const modal = document.getElementById('llm-diff-modal');
        modal.querySelector('.modal-close').addEventListener('click', () => modal.classList.add('hidden'));
        modal.querySelector('.modal-backdrop').addEventListener('click', () => modal.classList.add('hidden'));
        document.getElementById('btn-llm-diff-cancel').addEventListener('click', () => modal.classList.add('hidden'));

        document.getElementById('btn-llm-diff-apply').addEventListener('click', async () => {
            await this.applySelected();
        });
    },

    // ── Core: Propose ───────────────────────────────────────
    async propose(entryIds, preset, customPrompt) {
        const overlay = document.getElementById('llm-loading-overlay');
        const loadingText = document.getElementById('llm-loading-text');

        // Show loading overlay with context
        const presetLabels = {
            complete_fields: 'Complete Fields',
            fix_format: 'Fix Format',
            generate_abstract: 'Generate Abstract',
            check_entry_type: 'Check Type',
        };
        const label = preset ? (presetLabels[preset] || preset) : 'Custom Prompt';
        loadingText.textContent = `Running "${label}" on ${entryIds.length} entry${entryIds.length > 1 ? 's' : ''}...`;
        overlay.classList.remove('hidden');

        // Disable all LLM buttons during request
        const btns = document.querySelectorAll('.llm-preset-btn');
        btns.forEach(b => b.disabled = true);

        try {
            const result = await API.llmPropose({
                entry_ids: entryIds,
                preset: preset,
                custom_prompt: customPrompt,
            });

            overlay.classList.add('hidden');
            btns.forEach(b => b.disabled = false);

            if (!result.proposals || result.proposals.length === 0) {
                let msg = 'LLM returned no changes.';
                if (result.filtered && result.filtered.length > 0) {
                    msg += ` (${result.filtered.length} items filtered by security checks)`;
                }
                App.toast(msg, 'info');
                return;
            }

            this.showDiff(result.proposals, result.filtered || []);
        } catch (e) {
            overlay.classList.add('hidden');
            btns.forEach(b => b.disabled = false);
            App.toast('LLM error: ' + e.message, 'error');
        }
    },

    // ── Show Diff ───────────────────────────────────────────
    showDiff(proposals, warnings) {
        const modal = document.getElementById('llm-diff-modal');
        const warningsEl = document.getElementById('llm-diff-warnings');
        const listEl = document.getElementById('llm-diff-list');

        // Show warnings if any
        if (warnings.length > 0) {
            warningsEl.classList.remove('hidden');
            warningsEl.innerHTML = `<div class="llm-warnings-box">
                <strong>Security filter warnings:</strong>
                <ul>${warnings.map(w => `<li>${Table.esc(w)}</li>`).join('')}</ul>
            </div>`;
        } else {
            warningsEl.classList.add('hidden');
            warningsEl.innerHTML = '';
        }

        // Build entry map for showing old values
        const entryMap = {};
        Table.entries.forEach(e => { entryMap[e.citation_key] = e; });

        // Store proposals for apply
        this._currentProposals = proposals;

        listEl.innerHTML = proposals.map((p, pi) => {
            const orig = entryMap[p.citation_key] || {};
            const changesHtml = Object.entries(p.changes).map(([field, newVal]) => {
                const oldVal = orig[field] || '';
                const oldDisplay = oldVal ? Table.esc(String(oldVal)) : '<em class="llm-empty">empty</em>';
                const newDisplay = Table.esc(String(newVal));
                return `<div class="llm-diff-field">
                    <label class="llm-diff-check">
                        <input type="checkbox" checked data-pi="${pi}" data-field="${Table.esc(field)}">
                        <strong>${Table.esc(field)}</strong>
                    </label>
                    <div class="llm-diff-values">
                        <span class="llm-old">${oldDisplay}</span>
                        <span class="llm-arrow">&rarr;</span>
                        <span class="llm-new">${newDisplay}</span>
                    </div>
                </div>`;
            }).join('');

            return `<div class="llm-diff-card">
                <div class="llm-diff-card-header">
                    <strong>${Table.esc(p.citation_key)}</strong>
                    <span class="llm-diff-count">${Object.keys(p.changes).length} field(s)</span>
                </div>
                ${changesHtml}
            </div>`;
        }).join('');

        modal.classList.remove('hidden');
    },

    // ── Apply Selected ──────────────────────────────────────
    async applySelected() {
        const modal = document.getElementById('llm-diff-modal');
        const checkboxes = modal.querySelectorAll('.llm-diff-field input[type="checkbox"]');

        // Build filtered proposals based on checked fields
        const proposalChanges = {};
        checkboxes.forEach(cb => {
            if (!cb.checked) return;
            const pi = parseInt(cb.dataset.pi);
            const field = cb.dataset.field;
            if (!proposalChanges[pi]) proposalChanges[pi] = {};
            proposalChanges[pi][field] = this._currentProposals[pi].changes[field];
        });

        const toApply = [];
        for (const [pi, changes] of Object.entries(proposalChanges)) {
            if (Object.keys(changes).length > 0) {
                toApply.push({
                    citation_key: this._currentProposals[parseInt(pi)].citation_key,
                    changes: changes,
                });
            }
        }

        if (toApply.length === 0) {
            App.toast('No changes selected', 'info');
            return;
        }

        const applyBtn = document.getElementById('btn-llm-diff-apply');
        applyBtn.disabled = true;
        applyBtn.textContent = 'Applying...';

        try {
            const result = await API.llmApply({ proposals: toApply });
            modal.classList.add('hidden');
            App.toast(`Applied changes to ${result.applied.length} entries`, 'success');
            if (result.errors && result.errors.length > 0) {
                App.toast(`Errors: ${result.errors.join(', ')}`, 'error');
            }
            Table.load();
        } catch (e) {
            App.toast('Apply failed: ' + e.message, 'error');
        } finally {
            applyBtn.disabled = false;
            applyBtn.textContent = 'Apply Selected Changes';
        }
    },
};
