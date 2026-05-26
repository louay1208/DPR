/**
 * Concession Manager — CRUD UI for concessions and cell mappings
 */
const ConcManager = (() => {
    let concessions = [];
    let currentConc = null;
    let currentTab = 'dc';
    let currentMappings = [];

    // ── Concessions List ───────────────────────────────────────────
    async function load() {
        try {
            const res = await fetch('/api/concessions');
            concessions = await res.json();
            render();
            updateStats();
        } catch (e) { console.error('Failed to load concessions:', e); }
    }

    function render() {
        const tbody = document.getElementById('tbody-concessions');
        const search = (document.getElementById('conc-search')?.value || '').toLowerCase();

        const filtered = concessions.filter(c =>
            c.name.toLowerCase().includes(search) ||
            (c.dpr_file_alias || '').toLowerCase().includes(search)
        );

        if (!filtered.length) {
            tbody.innerHTML = '<tr><td class="empty-row" colspan="10">No concessions found</td></tr>';
            return;
        }

        tbody.innerHTML = filtered.map(c => `
            <tr style="cursor:pointer" onclick="ConcManager.openDetail('${c.id}')">
                <td style="font-weight:500">${esc(c.name)}</td>
                <td style="color:var(--text-dim)">${esc(c.dpr_file_alias || '—')}</td>
                <td>${badge(c.active_daily)}</td>
                <td>${badge(c.active_monthly)}</td>
                <td>${badge(c.active_well_test)}</td>
                <td><span class="count-chip">${c.dc_count}</span></td>
                <td><span class="count-chip">${c.dw_count}</span></td>
                <td><span class="count-chip">${c.mc_count}</span></td>
                <td><span class="count-chip">${c.wt_count}</span></td>
                <td><button class="btn btn-outline btn-xs" onclick="event.stopPropagation();ConcManager.openDetail('${c.id}')">Edit</button></td>
            </tr>
        `).join('');
    }

    function updateStats() {
        const el = (id, v) => { const e = document.getElementById(id); if (e) e.textContent = v; };
        el('conc-total', concessions.length);
        el('conc-active-d', concessions.filter(c => c.active_daily).length);
        el('conc-active-m', concessions.filter(c => c.active_monthly).length);
        el('conc-total-maps', concessions.reduce((s, c) => s + c.dc_count + c.dw_count + c.mc_count + c.wt_count, 0));
    }

    function badge(val) {
        return val
            ? '<span style="color:var(--accent);font-weight:600">●</span>'
            : '<span style="color:var(--text-dim)">○</span>';
    }

    // ── Create Concession ──────────────────────────────────────────
    async function showCreate() {
        const name = prompt('Concession name:');
        if (!name) return;
        try {
            await fetch('/api/concessions', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name }),
            });
            await load();
            showToast('Concession created', 'success');
        } catch (e) { showToast('Failed to create', 'error'); }
    }

    // ── Detail View ────────────────────────────────────────────────
    async function openDetail(id) {
        try {
            const res = await fetch(`/api/concessions/${id}`);
            currentConc = await res.json();
        } catch (e) {
            showToast('Failed to load concession', 'error');
            return;
        }

        // Show detail section, hide list
        document.getElementById('section-concessions').classList.remove('active');
        document.getElementById('section-conc-detail').classList.add('active');

        // Fill form
        document.getElementById('conc-detail-title').textContent = currentConc.name;
        document.getElementById('cd-name').value = currentConc.name;
        document.getElementById('cd-alias').value = currentConc.dpr_file_alias || '';
        document.getElementById('cd-sheet').value = currentConc.dpr_sheet || '';
        document.getElementById('cd-datefmt').value = currentConc.date_format || 'ddmmyyyy';
        document.getElementById('cd-active-d').checked = currentConc.active_daily;
        document.getElementById('cd-active-m').checked = currentConc.active_monthly;
        document.getElementById('cd-active-wt').checked = currentConc.active_well_test;
        document.getElementById('cd-monthly').value = currentConc.monthly_report || '';

        // Update tab counts
        const m = currentConc.mappings;
        setText('tab-dc-count', m.dc.length);
        setText('tab-dw-count', m.dw.reduce((s, w) => s + w.fields.length, 0));
        setText('tab-mc-count', m.mc.length);
        setText('tab-wt-count', m.wt.reduce((s, w) => s + w.fields.length, 0));

        // Load first tab
        switchTab('dc');
    }

    function backToList() {
        document.getElementById('section-conc-detail').classList.remove('active');
        document.getElementById('section-concessions').classList.add('active');
        currentConc = null;
        load();
    }

    // ── Save Detail ────────────────────────────────────────────────
    async function saveDetail() {
        if (!currentConc) return;
        try {
            // Save basic info
            await fetch(`/api/concessions/${currentConc.id}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    name: document.getElementById('cd-name').value,
                    dpr_file_alias: document.getElementById('cd-alias').value,
                    dpr_sheet: document.getElementById('cd-sheet').value,
                    date_format: document.getElementById('cd-datefmt').value,
                    active_daily: document.getElementById('cd-active-d').checked,
                    active_monthly: document.getElementById('cd-active-m').checked,
                    active_well_test: document.getElementById('cd-active-wt').checked,
                    monthly_report: document.getElementById('cd-monthly').value,
                }),
            });

            // Save current tab's mappings
            await saveMappings();

            showToast('Saved successfully', 'success');
            document.getElementById('conc-detail-title').textContent = document.getElementById('cd-name').value;
        } catch (e) { showToast('Failed to save: ' + e.message, 'error'); }
    }

    // ── Delete ─────────────────────────────────────────────────────
    async function deleteCurrent() {
        if (!currentConc) return;
        if (!confirm(`Delete "${currentConc.name}" and all its mappings?`)) return;
        try {
            await fetch(`/api/concessions/${currentConc.id}`, { method: 'DELETE' });
            showToast('Concession deleted', 'success');
            backToList();
        } catch (e) { showToast('Failed to delete', 'error'); }
    }

    // ── Mapping Tabs ───────────────────────────────────────────────
    function switchTab(tab) {
        currentTab = tab;
        document.querySelectorAll('.mapping-tab').forEach(b => {
            b.classList.toggle('active', b.dataset.tab === tab);
        });
        renderMappings();
    }

    function renderMappings() {
        if (!currentConc) return;
        const m = currentConc.mappings;
        const thead = document.getElementById('thead-mappings');
        const tbody = document.getElementById('tbody-mappings');

        const isWell = currentTab === 'dw' || currentTab === 'wt';

        // Build header
        if (isWell) {
            thead.innerHTML = '<tr><th>Well Name</th><th>UBHI</th><th>Completion</th><th>Code</th><th>Attribute</th><th>Cell Ref</th><th>Unit</th><th style="width:40px"></th></tr>';
        } else {
            thead.innerHTML = '<tr><th>Code</th><th>Attribute</th><th>Cell Ref</th><th>Unit</th><th style="width:40px"></th></tr>';
        }

        // Build rows
        let rows = [];
        if (isWell) {
            const wells = currentTab === 'dw' ? m.dw : m.wt;
            wells.forEach(w => {
                w.fields.forEach((f, fi) => {
                    rows.push(`<tr>
                        ${fi === 0 ? `<td rowspan="${w.fields.length}" style="font-weight:500;vertical-align:top">${esc(w.well_name)}</td>
                        <td rowspan="${w.fields.length}" style="vertical-align:top;color:var(--text-dim)">${esc(w.ubhi)}</td>
                        <td rowspan="${w.fields.length}" style="vertical-align:top;color:var(--text-dim)">${esc(w.completion)}</td>` : ''}
                        <td><input class="form-input map-code" value="${esc(f.attribute_code)}" style="font-size:.78rem;padding:2px 6px" data-id="${f.id||''}"></td>
                        <td><input class="form-input map-attr" value="${esc(f.attribute)}" style="font-size:.78rem;padding:2px 6px"></td>
                        <td><input class="form-input map-ref" value="${esc(f.cell_ref)}" style="font-size:.78rem;padding:2px 6px;width:70px;font-family:monospace"></td>
                        <td><input class="form-input map-unit" value="${esc(f.unit)}" style="font-size:.78rem;padding:2px 6px;width:60px"></td>
                        <td><button class="btn btn-outline btn-xs" onclick="ConcManager.removeRow(this)" style="color:var(--danger);padding:1px 5px">×</button></td>
                    </tr>`);
                });
            });
        } else {
            const items = currentTab === 'dc' ? m.dc : m.mc;
            items.forEach(f => {
                rows.push(`<tr>
                    <td><input class="form-input map-code" value="${esc(f.attribute_code)}" style="font-size:.78rem;padding:2px 6px" data-id="${f.id||''}"></td>
                    <td><input class="form-input map-attr" value="${esc(f.attribute)}" style="font-size:.78rem;padding:2px 6px"></td>
                    <td><input class="form-input map-ref" value="${esc(f.cell_ref)}" style="font-size:.78rem;padding:2px 6px;width:80px;font-family:monospace"></td>
                    <td><input class="form-input map-unit" value="${esc(f.unit)}" style="font-size:.78rem;padding:2px 6px;width:70px"></td>
                    <td><button class="btn btn-outline btn-xs" onclick="ConcManager.removeRow(this)" style="color:var(--danger);padding:1px 5px">×</button></td>
                </tr>`);
            });
        }

        tbody.innerHTML = rows.length
            ? rows.join('')
            : `<tr><td class="empty-row" colspan="8">No ${currentTab.toUpperCase()} mappings. Click "+ Add Row" to create.</td></tr>`;
    }

    function addMappingRow() {
        const tbody = document.getElementById('tbody-mappings');
        const isWell = currentTab === 'dw' || currentTab === 'wt';
        const empty = tbody.querySelector('.empty-row');
        if (empty) empty.closest('tr').remove();

        const tr = document.createElement('tr');
        if (isWell) {
            tr.innerHTML = `
                <td><input class="form-input map-well" value="" style="font-size:.78rem;padding:2px 6px" placeholder="Well name"></td>
                <td><input class="form-input map-ubhi" value="" style="font-size:.78rem;padding:2px 6px" placeholder="UBHI"></td>
                <td><input class="form-input map-comp" value="" style="font-size:.78rem;padding:2px 6px" placeholder="Completion"></td>
                <td><input class="form-input map-code" value="" style="font-size:.78rem;padding:2px 6px" placeholder="${currentTab.toUpperCase()}001"></td>
                <td><input class="form-input map-attr" value="" style="font-size:.78rem;padding:2px 6px" placeholder="Attribute name"></td>
                <td><input class="form-input map-ref" value="" style="font-size:.78rem;padding:2px 6px;width:70px;font-family:monospace" placeholder="B15"></td>
                <td><input class="form-input map-unit" value="" style="font-size:.78rem;padding:2px 6px;width:60px" placeholder="sm3"></td>
                <td><button class="btn btn-outline btn-xs" onclick="ConcManager.removeRow(this)" style="color:var(--danger);padding:1px 5px">×</button></td>
            `;
        } else {
            tr.innerHTML = `
                <td><input class="form-input map-code" value="" style="font-size:.78rem;padding:2px 6px" placeholder="${currentTab.toUpperCase()}001"></td>
                <td><input class="form-input map-attr" value="" style="font-size:.78rem;padding:2px 6px" placeholder="Attribute name"></td>
                <td><input class="form-input map-ref" value="" style="font-size:.78rem;padding:2px 6px;width:80px;font-family:monospace" placeholder="B15"></td>
                <td><input class="form-input map-unit" value="" style="font-size:.78rem;padding:2px 6px;width:70px" placeholder="sm3"></td>
                <td><button class="btn btn-outline btn-xs" onclick="ConcManager.removeRow(this)" style="color:var(--danger);padding:1px 5px">×</button></td>
            `;
        }
        tbody.appendChild(tr);
        tr.querySelector('input').focus();
    }

    function removeRow(btn) {
        btn.closest('tr').remove();
    }

    async function saveMappings() {
        if (!currentConc) return;
        const tbody = document.getElementById('tbody-mappings');
        const rows = tbody.querySelectorAll('tr');
        const isWell = currentTab === 'dw' || currentTab === 'wt';
        const mappings = [];

        rows.forEach(tr => {
            if (tr.querySelector('.empty-row')) return;
            const obj = {
                attribute_code: tr.querySelector('.map-code')?.value || '',
                attribute: tr.querySelector('.map-attr')?.value || '',
                cell_ref: tr.querySelector('.map-ref')?.value || '',
                unit: tr.querySelector('.map-unit')?.value || '',
            };
            if (isWell) {
                obj.well_name = tr.querySelector('.map-well')?.value || '';
                obj.ubhi = tr.querySelector('.map-ubhi')?.value || '';
                obj.completion = tr.querySelector('.map-comp')?.value || '';
            }
            if (obj.attribute_code) mappings.push(obj);
        });

        await fetch(`/api/concessions/${currentConc.id}/mappings/${currentTab}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(mappings),
        });
    }

    // ── Search ─────────────────────────────────────────────────────
    function setupSearch() {
        const el = document.getElementById('conc-search');
        if (el) el.addEventListener('input', () => render());
    }

    // ── Helpers ────────────────────────────────────────────────────
    function esc(s) { return String(s || '').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;'); }
    function setText(id, v) { const e = document.getElementById(id); if (e) e.textContent = v; }
    function showToast(msg, type) { if (window.App && App.showToast) App.showToast(msg, type); else console.log(msg); }

    return { load, showCreate, openDetail, backToList, saveDetail, deleteCurrent, switchTab, addMappingRow, removeRow, setupSearch };
})();


/**
 * UOM Manager — CRUD for unit conversion entries
 */
const UomManager = (() => {
    async function load() {
        try {
            const res = await fetch('/api/uom');
            const data = await res.json();
            render(data);
        } catch (e) { console.error('Failed to load UOM:', e); }
    }

    function render(entries) {
        const tbody = document.getElementById('tbody-uom');
        if (!entries.length) {
            tbody.innerHTML = '<tr><td class="empty-row" colspan="4">No UOM entries</td></tr>';
            return;
        }
        tbody.innerHTML = entries.map(e => `
            <tr>
                <td style="font-weight:500;font-family:monospace">${e.unit}</td>
                <td style="font-family:monospace">${e.factor}</td>
                <td>${e.target_unit}</td>
                <td><button class="btn btn-outline btn-xs" onclick="UomManager.remove('${e.unit}')" style="color:var(--danger);padding:1px 5px">×</button></td>
            </tr>
        `).join('');
    }

    async function showAdd() {
        const unit = prompt('Unit name (e.g. MSCF):');
        if (!unit) return;
        const factor = prompt('Conversion factor:');
        if (!factor) return;
        const target = prompt('Target unit (e.g. ksm3):') || '';

        try {
            await fetch('/api/uom', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ unit, factor: parseFloat(factor), target_unit: target }),
            });
            load();
        } catch (e) { console.error(e); }
    }

    async function remove(unit) {
        if (!confirm(`Delete UOM entry "${unit}"?`)) return;
        await fetch(`/api/uom/${unit}`, { method: 'DELETE' });
        load();
    }

    return { load, showAdd, remove };
})();


/**
 * Import Manager — File upload for moulinette and mapping imports
 */
const ImportManager = (() => {
    async function importMoulinette() {
        const input = document.getElementById('import-moulinette-file');
        if (!input.files.length) return alert('Select a file first');

        const form = new FormData();
        form.append('file', input.files[0]);

        const el = document.getElementById('import-moulinette-result');
        el.innerHTML = '<span style="color:var(--text-dim)">Importing...</span>';

        try {
            const res = await fetch('/api/import/moulinette', { method: 'POST', body: form });
            const data = await res.json();
            el.innerHTML = formatResult(data);
            ConcManager.load();
        } catch (e) {
            el.innerHTML = `<span style="color:var(--danger)">Error: ${e.message}</span>`;
        }
    }

    async function importMapping() {
        const input = document.getElementById('import-mapping-file');
        if (!input.files.length) return alert('Select a file first');

        const form = new FormData();
        form.append('file', input.files[0]);

        const el = document.getElementById('import-mapping-result');
        el.innerHTML = '<span style="color:var(--text-dim)">Importing...</span>';

        try {
            const res = await fetch('/api/import/mapping', { method: 'POST', body: form });
            const data = await res.json();
            el.innerHTML = formatResult(data);
            ConcManager.load();
        } catch (e) {
            el.innerHTML = `<span style="color:var(--danger)">Error: ${e.message}</span>`;
        }
    }

    async function autoDetect() {
        const el = document.getElementById('import-auto-result');
        el.innerHTML = '<span style="color:var(--text-dim)">Scanning...</span>';

        try {
            const res = await fetch('/api/import/auto-detect', { method: 'POST' });
            const data = await res.json();
            let html = `<p style="color:var(--accent);font-weight:500">Found ${data.total_files} files</p>`;
            data.results.forEach(r => {
                html += formatResult(r);
            });
            el.innerHTML = html;
            ConcManager.load();
        } catch (e) {
            el.innerHTML = `<span style="color:var(--danger)">Error: ${e.message}</span>`;
        }
    }

    function formatResult(r) {
        const items = [];
        if (r.concessions_imported) items.push(`${r.concessions_imported} concessions`);
        if (r.mappings_imported) items.push(`${r.mappings_imported} mappings`);
        if (r.uom_imported) items.push(`${r.uom_imported} UOM`);
        if (r.qc_rules_imported) items.push(`${r.qc_rules_imported} QC rules`);
        if (r.naming_rules_imported) items.push(`${r.naming_rules_imported} naming rules`);
        const warn = r.warnings?.length ? `<br><span style="color:var(--warning);font-size:.78rem">${r.warnings.join(', ')}</span>` : '';
        return `<div style="padding:4px 0;font-size:.82rem"><strong>${r.source}:</strong> ${items.join(', ') || 'Nothing imported'}${warn}</div>`;
    }

    // ── Backup / Restore ──────────────────────────────────────────
    async function downloadBackup() {
        const el = document.getElementById('backup-result');
        el.innerHTML = '<span style="color:var(--text-dim)">Generating...</span>';
        try {
            const res = await fetch('/api/config/backup');
            const data = await res.json();
            const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            const ts = new Date().toISOString().slice(0,10).replace(/-/g,'');
            a.href = url;
            a.download = `dpr_config_backup_${ts}.json`;
            a.click();
            URL.revokeObjectURL(url);
            el.innerHTML = `<span style="color:var(--accent);font-size:.82rem">✓ Backup downloaded (${data.concessions.length} conc, ${data.cell_mappings.length} mappings)</span>`;
        } catch (e) {
            el.innerHTML = `<span style="color:var(--danger)">Error: ${e.message}</span>`;
        }
    }

    async function restoreBackup() {
        const input = document.getElementById('restore-file');
        if (!input.files.length) return alert('Select a JSON backup file first');

        if (!confirm('⚠️ This will REPLACE all current configuration. Are you sure?')) return;

        const el = document.getElementById('restore-result');
        el.innerHTML = '<span style="color:var(--text-dim)">Restoring...</span>';

        try {
            const text = await input.files[0].text();
            const data = JSON.parse(text);

            const res = await fetch('/api/config/restore', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data),
            });
            const result = await res.json();
            const c = result.counts;
            el.innerHTML = `<span style="color:var(--accent);font-size:.82rem">✓ Restored: ${c.concessions} concessions, ${c.mappings} mappings, ${c.uom} UOM, ${c.qc_rules} QC rules</span>`;
            ConcManager.load();
        } catch (e) {
            el.innerHTML = `<span style="color:var(--danger)">Error: ${e.message}</span>`;
        }
    }

    // ── Copy Mappings ─────────────────────────────────────────────
    async function populateConcDropdowns() {
        try {
            const res = await fetch('/api/concessions');
            const concs = await res.json();
            const opts = concs.map(c => `<option value="${c.id}">${c.name} (${c.dc_count + c.dw_count + c.mc_count + c.wt_count} maps)</option>`).join('');
            const src = document.getElementById('copy-source');
            const tgt = document.getElementById('copy-target');
            if (src) src.innerHTML = opts;
            if (tgt) tgt.innerHTML = opts;
        } catch (e) { console.error(e); }
    }

    async function copyMappings() {
        const src = document.getElementById('copy-source')?.value;
        const tgt = document.getElementById('copy-target')?.value;
        if (!src || !tgt) return alert('Select both concessions');
        if (src === tgt) return alert('Source and target must be different');
        if (!confirm(`Copy ALL mappings from source → target? Target mappings will be replaced.`)) return;

        const el = document.getElementById('copy-result');
        el.innerHTML = '<span style="color:var(--text-dim)">Copying...</span>';

        try {
            const res = await fetch(`/api/concessions/${src}/copy-mappings/${tgt}`, { method: 'POST' });
            const data = await res.json();
            el.innerHTML = `<span style="color:var(--accent);font-size:.82rem">✓ Copied ${data.mappings_copied} mappings (${data.types.join(', ')})</span>`;
            ConcManager.load();
        } catch (e) {
            el.innerHTML = `<span style="color:var(--danger)">Error: ${e.message}</span>`;
        }
    }

    // ── Bulk Toggle ───────────────────────────────────────────────
    async function bulkToggle(field, value) {
        const label = field.replace('active_', '').replace('_', ' ');
        if (!confirm(`${value ? 'Enable' : 'Disable'} ${label} for ALL concessions?`)) return;

        const el = document.getElementById('bulk-result');
        el.innerHTML = '<span style="color:var(--text-dim)">Updating...</span>';

        try {
            // Get all concession IDs
            const res = await fetch('/api/concessions');
            const concs = await res.json();
            const ids = concs.map(c => c.id);

            const res2 = await fetch(`/api/concessions/bulk/toggle?field=${field}&value=${value}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(ids),
            });
            const data = await res2.json();
            el.innerHTML = `<span style="color:var(--accent);font-size:.82rem">✓ Updated ${data.count} concessions: ${field} = ${value}</span>`;
            ConcManager.load();
        } catch (e) {
            el.innerHTML = `<span style="color:var(--danger)">Error: ${e.message}</span>`;
        }
    }

    return { importMoulinette, importMapping, autoDetect, downloadBackup, restoreBackup, copyMappings, populateConcDropdowns, bulkToggle };
})();
