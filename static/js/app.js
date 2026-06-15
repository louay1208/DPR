/**
 * DPR Manager — Frontend Application
 * Path-based extraction with moulinette config
 */
const App = (() => {
    // ── State ──────────────────────────────────────────────────────
    let ws = null;
    let currentExtractionId = null;
    let config = {};
    let extractionData = { dc: null, dw: null, mc: null, wt: null };
    let concessionList = [];        // all concessions from API
    let selectedConcessions = new Set(); // currently selected IDs
    let uploadedFiles = [];         // { id, name, size, status }
    let attributeMap = {};          // { DC001: "Nom Concession", ... }
    let recordDetailState = null;   // { type, rowIndex }

    // ── Init ───────────────────────────────────────────────────────
    function init() {
        // Toggle elements based on user role
        const userStr = localStorage.getItem('dpr_user');
        if (userStr) {
            try {
                const user = JSON.parse(userStr);
                if (user && user.role === 'admin') {
                    document.querySelectorAll('.admin-only').forEach(el => el.style.display = '');
                } else {
                    document.querySelectorAll('.admin-only').forEach(el => el.style.display = 'none');
                }
            } catch (e) {
                console.error("Error checking user role in init:", e);
            }
        }

        setupNav();
        setupWebSocket();
        setupPathValidation();
        setupFileDropzone();
        loadConfig();
        loadAttributeMap();
        loadDashboardInsights();
        loadConcessionChips();
        setDefaultDate();
        I18n.apply();
        restoreLastExtraction();
    }

    async function loadAttributeMap() {
        try {
            const res = await fetch('/api/attribute-map');
            if (res.ok) attributeMap = await res.json();
        } catch (e) {
            console.log('Could not load attribute map:', e.message);
        }
    }

    async function restoreLastExtraction() {
        try {
            const res = await fetch('/api/extractions');
            if (!res.ok) return;
            const history = await res.json();
            if (!history.length) return;

            // Load the most recent extraction (first in the list, sorted by date desc)
            const latest = history[0];
            const detailRes = await fetch(`/api/extractions/${latest.id}`);
            if (!detailRes.ok) return;
            const data = await detailRes.json();

            currentExtractionId = data.id;
            // Let populateOutputPages handle extractionData via renderOutputTable
            populateOutputPages(data, data.report_type);

            // Enable pipeline buttons
            const btnCorrect = document.getElementById('btn-correct');
            const btnConvert = document.getElementById('btn-convert');
            const btnExport = document.getElementById('btn-export');
            if (btnCorrect) btnCorrect.disabled = false;
            if (btnConvert) btnConvert.disabled = false;
            if (btnExport) btnExport.disabled = false;
        } catch (e) {
            // Silent fail — not critical
            console.log('No extraction to restore:', e.message);
        }
    }

    function setDefaultDate() {
        const d = new Date();
        d.setDate(d.getDate() - 1);
        const iso = d.toISOString().split('T')[0];

        // Native date input
        const el = document.getElementById('date-dpr');
        if (el) el.value = iso;

        // Multi start date
        const multi = document.getElementById('multi-start-date');
        if (multi) multi.value = iso;

        // Populate selection dropdowns
        populateDateSelectors(d);
    }

    function populateDateSelectors(d) {
        const dayEl = document.getElementById('sel-day');
        const monthEl = document.getElementById('sel-month');
        const yearEl = document.getElementById('sel-year');
        if (!dayEl) return;

        dayEl.innerHTML = '';
        for (let i = 1; i <= 31; i++) {
            const opt = document.createElement('option');
            opt.value = i; opt.textContent = i;
            if (i === d.getDate()) opt.selected = true;
            dayEl.appendChild(opt);
        }
        const months = I18n.lang() === 'fr'
            ? ['Jan','Fév','Mar','Avr','Mai','Juin','Juil','Aoû','Sep','Oct','Nov','Déc']
            : ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
        monthEl.innerHTML = '';
        months.forEach((m, i) => {
            const opt = document.createElement('option');
            opt.value = i + 1; opt.textContent = m;
            if (i === d.getMonth()) opt.selected = true;
            monthEl.appendChild(opt);
        });
        const curYear = new Date().getFullYear();
        yearEl.innerHTML = '';
        for (let y = curYear - 5; y <= curYear + 1; y++) {
            const opt = document.createElement('option');
            opt.value = y; opt.textContent = y;
            if (y === d.getFullYear()) opt.selected = true;
            yearEl.appendChild(opt);
        }
    }

    // ── Navigation ─────────────────────────────────────────────────
    function setupNav() {
        document.querySelectorAll('.nav-item[data-page]').forEach(item => {
            item.addEventListener('click', () => goTo(item.dataset.page));
        });
    }

    function goTo(page) {
        // Protect administration page
        if (page === 'users') {
            const userStr = localStorage.getItem('dpr_user');
            let isAdmin = false;
            if (userStr) {
                try {
                    const user = JSON.parse(userStr);
                    isAdmin = user && user.role === 'admin';
                } catch (e) {}
            }
            if (!isAdmin) {
                console.warn("Unauthorized attempt to access User Management page.");
                goTo('dashboard');
                return;
            }
        }

        document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
        document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));

        const nav = document.querySelector(`.nav-item[data-page="${page}"]`);
        const sec = document.getElementById(`section-${page}`);
        if (nav) nav.classList.add('active');
        if (sec) sec.classList.add('active');

        const titleEl = document.getElementById('page-title');
        const titles = {
            'concessions': 'Concessions',
            'conc-detail': 'Concession Detail',
            'uom-config': 'Unit Conversions',
            'import-config': 'Import',
            'output-dc': 'Daily Concession (DC)',
            'output-dw': 'Daily Well (DW)',
            'output-mc': 'Monthly Concession (MC)',
            'well-test': 'Well Test (WT)',
            'history': 'Extraction History',
            'users': 'User Management',
        };
        const key = `page.${page}`;
        titleEl.textContent = titles[page] || I18n.t(key);
        titleEl.setAttribute('data-i18n', key);

        // Load data for config pages
        if (page === 'concessions' && typeof ConcManager !== 'undefined') {
            ConcManager.load();
            ConcManager.setupSearch();
        }
        if (page === 'uom-config' && typeof UomManager !== 'undefined') {
            UomManager.load();
        }
        if (page === 'import-config' && typeof ImportManager !== 'undefined') {
            ImportManager.populateConcDropdowns();
        }
        if (page === 'history') {
            loadHistory();
        }
        if (page === 'users' && typeof UserManager !== 'undefined') {
            UserManager.load();
        }
    }

    // ── Config & Dashboard ─────────────────────────────────────────
    async function loadConfig() {
        try {
            const res = await fetch('/api/config');
            config = await res.json();
            updateDashboard();
            populatePathFields();
        } catch (e) { console.error('Config load error:', e); }
    }

    function populatePathFields() {
        if (config.dpr_folder) document.getElementById('dpr-files-path').value = config.dpr_folder;
        document.getElementById('output-csv-path').value = config.output_folder || '';

        // Auto-validate all populated paths
        const hasAny = config.dpr_folder || config.output_folder;
        if (hasAny) {
            validatePaths({
                dpr_folder: config.dpr_folder || '',
                output_folder: config.output_folder || '',
            });
        }
    }

    function updateDashboard() {
        const dotEl = document.getElementById('status-dot');
        const statusText = document.getElementById('sidebar-status-text');

        // Config is always ready in SQLite-driven mode
        if (dotEl) dotEl.className = 'status-dot live';
        if (statusText) statusText.textContent = I18n.lang() === 'fr' ? 'Système prêt' : 'System Ready';
    }

    async function loadDashboardInsights(extractionId) {
        try {
            let url = '/api/dashboard/insights';
            if (extractionId) url += `?extraction_id=${encodeURIComponent(extractionId)}`;
            const res = await fetch(url);
            const d = await res.json();
            renderInsights(d);
        } catch (e) { console.error('Insights error:', e); }
    }

    // Wire extraction filter dropdown
    document.addEventListener('DOMContentLoaded', () => {
        const extSelect = document.getElementById('dash-extraction-select');
        if (extSelect) {
            extSelect.addEventListener('change', () => {
                loadDashboardInsights(extSelect.value);
            });
        }
    });

    // ── Chart instances (for destroy/re-render) ─────────────
    let chartConcProd = null;
    let chartGasDist = null;
    let chartProdMix = null;
    let dashboardData = null;  // Cache for filter re-rendering

    function renderInsights(d) {
        dashboardData = d;
        const setText = (id, v) => { const el = document.getElementById(id); if (el) el.textContent = v; };
        const esc = (s) => String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
        const isFr = I18n.lang() === 'fr';

        // ── Populate extraction dropdown ──────────────────────
        const extSelect = document.getElementById('dash-extraction-select');
        if (extSelect && d.extraction_list) {
            const opts = d.extraction_list.map(e => {
                const date = new Date(e.created_at).toLocaleDateString(isFr ? 'fr-FR' : 'en-US', { month: 'short', day: 'numeric', year: 'numeric' });
                const label = `${e.report_type} · ${date} · ${e.record_count} records`;
                return `<option value="${e.id}" ${e.id === d.latest_extraction_id ? 'selected' : ''}>${label}</option>`;
            });
            if (opts.length) extSelect.innerHTML = opts.join('');
            else extSelect.innerHTML = `<option value="">${isFr ? 'Aucune extraction' : 'No extractions yet'}</option>`;
        }

        // ── Populate concession dropdown ──────────────────────
        const concSelect = document.getElementById('dash-concession-select');
        if (concSelect && d.concession_production) {
            const names = [...new Set(d.concession_production.map(c => c.name))].sort();
            let html = `<option value="">${isFr ? 'Toutes les concessions' : 'All Concessions'}</option>`;
            html += names.map(n => `<option value="${n}">${n}</option>`).join('');
            concSelect.innerHTML = html;

            // Re-attach filter listener (innerHTML replacement destroys previous listeners)
            concSelect.onchange = () => {
                if (dashboardData) filterWellTableByConcession(concSelect.value);
            };
        }

        // ── KPI Cards ────────────────────────────────────────
        const ps = d.production_summary || {};
        setText('kpi-gas', (ps.gas || 0).toLocaleString(isFr ? 'fr-FR' : 'en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }));
        setText('kpi-oil', (ps.oil || 0).toLocaleString(isFr ? 'fr-FR' : 'en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }));
        setText('kpi-water', (ps.water || 0).toLocaleString(isFr ? 'fr-FR' : 'en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }));
        setText('kpi-condensate', (ps.condensate || 0).toLocaleString(isFr ? 'fr-FR' : 'en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }));
        setText('kpi-records', ps.records || 0);

        // ── Production by Concession bar chart ───────────────
        const cp = d.concession_production || [];
        const sorted = [...cp].sort((a, b) => b.gas - a.gas);
        const concNames = sorted.map(c => c.name);
        const concGas = sorted.map(c => c.gas);

        if (chartConcProd) chartConcProd.destroy();
        const concChartEl = document.getElementById('chart-conc-production');
        if (concChartEl && concNames.length) {
            chartConcProd = new ApexCharts(concChartEl, {
                chart: { type: 'bar', height: Math.max(180, concNames.length * 38), fontFamily: 'Inter, sans-serif',
                    background: 'transparent', toolbar: { show: false },
                    animations: { enabled: true, easing: 'easeinout', speed: 500 } },
                series: [{ name: isFr ? 'Gaz (k Sm3)' : 'Gas (k Sm3)', data: concGas }],
                colors: ['#d4a043'],
                plotOptions: { bar: { horizontal: true, borderRadius: 4, barHeight: '55%' } },
                dataLabels: { enabled: true, textAnchor: 'start', offsetX: 5,
                    style: { fontSize: '10px', fontWeight: 500, colors: ['#fff'] },
                    formatter: (v) => v.toFixed(1) },
                xaxis: { categories: concNames, labels: { show: false },
                    axisBorder: { show: false }, axisTicks: { show: false } },
                yaxis: { labels: { style: { fontSize: '10.5px', fontWeight: 500, colors: '#5a5a5a' } } },
                grid: { show: false, padding: { left: 0, right: 14 } },
                legend: { show: false },
                tooltip: { y: { formatter: (v) => v.toFixed(2) + ' k Sm3' } },
            });
            chartConcProd.render();
        }

        // ── Gas Distribution donut ───────────────────────────
        const gd = d.gas_distribution || {};
        const gdLabels = [
            isFr ? 'Vendu STEG' : 'Sold STEG',
            isFr ? 'Vendu MISKAR' : 'Sold MISKAR',
            isFr ? 'Vendu Gabès' : 'Sold Gabès',
            isFr ? 'Torché' : 'Flared',
            isFr ? 'Fuel Gaz' : 'Fuel Gas',
            isFr ? 'Injecté' : 'Injected',
        ];
        const gdValues = [gd.steg || 0, gd.miskar || 0, gd.gabes || 0, gd.flared || 0, gd.fuel || 0, gd.injected || 0];
        const gdTotal = gdValues.reduce((a, b) => a + b, 0);

        if (chartGasDist) chartGasDist.destroy();
        const gasDistEl = document.getElementById('chart-gas-distribution');
        if (gasDistEl && gdTotal > 0) {
            chartGasDist = new ApexCharts(gasDistEl, {
                chart: { type: 'donut', height: Math.max(260, concNames.length * 38), fontFamily: 'Inter, sans-serif', background: 'transparent' },
                series: gdValues,
                labels: gdLabels,
                colors: ['#d4a043', '#4a8fb8', '#5a9a8a', '#c0392b', '#8a8a8a', '#a8a8a8'],
                plotOptions: {
                    pie: { donut: { size: '55%',
                        labels: { show: true, total: { show: true, label: isFr ? 'Total' : 'Total',
                            fontSize: '10px', color: '#9a9a9a',
                            formatter: () => gdTotal.toFixed(1) } } } },
                },
                dataLabels: { enabled: false },
                legend: { position: 'right', fontSize: '11px', fontWeight: 400,
                    labels: { colors: '#5a5a5a' }, itemMargin: { horizontal: 4, vertical: 4 },
                    markers: { width: 10, height: 10, radius: 3 },
                    formatter: (name, opts) => {
                        const val = opts.w.globals.series[opts.seriesIndex];
                        const pct = gdTotal > 0 ? ((val / gdTotal) * 100).toFixed(0) : 0;
                        return `${name} (${pct}%)`;
                    }
                },
                stroke: { width: 2, colors: ['#f0efec'] },
                tooltip: { y: { formatter: (v) => v.toFixed(2) + ' k Sm3' } },
            });
            chartGasDist.render();
        }

        // ── Liquid Products ──────────────────────────────────
        const lp = d.liquid_products || {};
        for (const product of ['gpl', 'butane', 'propane', 'pentane', 'condensate']) {
            setText(`lp-${product}-prod`, (lp[product]?.prod || 0).toFixed(2));
            setText(`lp-${product}-ship`, (lp[product]?.ship || 0).toFixed(2));
        }

        // ── Production Mix donut ─────────────────────────────
        const mixLabels = [
            isFr ? 'Gaz' : 'Gas',
            isFr ? 'Huile' : 'Oil',
            isFr ? 'Eau' : 'Water',
            isFr ? 'Condensat' : 'Condensate',
        ];
        const mixValues = [ps.gas || 0, ps.oil || 0, ps.water || 0, ps.condensate || 0];
        const mixTotal = mixValues.reduce((a, b) => a + b, 0);

        if (chartProdMix) chartProdMix.destroy();
        const mixEl = document.getElementById('chart-production-mix');
        if (mixEl && mixTotal > 0) {
            chartProdMix = new ApexCharts(mixEl, {
                chart: { type: 'donut', height: 260, fontFamily: 'Inter, sans-serif', background: 'transparent' },
                series: mixValues,
                labels: mixLabels,
                colors: ['#d4a043', '#5a5a5a', '#4a8fb8', '#5a9a8a'],
                plotOptions: {
                    pie: { donut: { size: '55%',
                        labels: { show: true, total: { show: true, label: 'Mix',
                            fontSize: '10px', color: '#9a9a9a',
                            formatter: () => '' } } } },
                },
                dataLabels: { enabled: false },
                legend: { position: 'right', fontSize: '11px', fontWeight: 400,
                    labels: { colors: '#5a5a5a' }, itemMargin: { horizontal: 4, vertical: 4 },
                    markers: { width: 10, height: 10, radius: 3 },
                    formatter: (name, opts) => {
                        const val = opts.w.globals.series[opts.seriesIndex];
                        const pct = mixTotal > 0 ? ((val / mixTotal) * 100).toFixed(0) : 0;
                        return `${name} (${pct}%)`;
                    }
                },
                stroke: { width: 2, colors: ['#f0efec'] },
                tooltip: { y: { formatter: (v) => v.toFixed(2) } },
            });
            chartProdMix.render();
        }

        // ── Well Table ───────────────────────────────────────
        const tbody = document.getElementById('well-table-body');
        if (tbody) {
            const wells = d.well_summary || [];
            if (wells.length === 0) {
                tbody.innerHTML = `<tr><td colspan="6" class="empty-row">${isFr ? 'Aucune donnée de puits' : 'No well data available'}</td></tr>`;
            } else {
                tbody.innerHTML = wells.map(w => {
                    const isWarning = w.water_cut > 60;
                    return `<tr class="${isWarning ? 'well-warning' : ''}">
                        <td>${isWarning ? '<span class="warning-icon">⚠</span>' : ''}${esc(w.well)}</td>
                        <td>${esc(w.concession)}</td>
                        <td style="text-align:right">${w.gas.toFixed(2)}</td>
                        <td style="text-align:right">${w.oil.toFixed(2)}</td>
                        <td style="text-align:right">${w.water.toFixed(2)}</td>
                        <td style="text-align:right;font-weight:${isWarning ? '700' : '400'}">${w.water_cut.toFixed(1)}%</td>
                    </tr>`;
                }).join('');
            }
        }
    }

    function filterWellTableByConcession(concessionName) {
        const isFr = I18n.lang() === 'fr';
        const tbody = document.getElementById('well-table-body');
        if (!tbody || !dashboardData) return;

        let wells = dashboardData.well_summary || [];
        if (concessionName) {
            wells = wells.filter(w => w.concession === concessionName);
        }

        if (wells.length === 0) {
            tbody.innerHTML = `<tr><td colspan="6" class="empty-row">${isFr ? 'Aucune donnée de puits' : 'No well data available'}</td></tr>`;
        } else {
            tbody.innerHTML = wells.map(w => {
                const isWarning = w.water_cut > 60;
                return `<tr class="${isWarning ? 'well-warning' : ''}">
                    <td>${isWarning ? '<span class="warning-icon">⚠</span>' : ''}${esc(w.well)}</td>
                    <td>${esc(w.concession)}</td>
                    <td style="text-align:right">${w.gas.toFixed(2)}</td>
                    <td style="text-align:right">${w.oil.toFixed(2)}</td>
                    <td style="text-align:right">${w.water.toFixed(2)}</td>
                    <td style="text-align:right;font-weight:${isWarning ? '700' : '400'}">${w.water_cut.toFixed(1)}%</td>
                </tr>`;
            }).join('');
        }
    }

    // ── Paths ──────────────────────────────────────────────────────
    async function savePaths() {
        const body = {
            dpr_folder: document.getElementById('dpr-files-path').value.trim(),
            output_folder: document.getElementById('output-csv-path').value.trim(),
        };
        try {
            const res = await fetch('/api/config/paths', {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body),
            });
            const data = await res.json();
            if (res.ok) {
                toast(I18n.t('toast.paths_saved'), 'success');
                validatePaths(body);
                setPipelineStep('config', true);
            } else {
                toast(data.detail || 'Failed to save paths', 'error');
            }
        } catch (e) { toast('Network error', 'error'); }
    }

    // ── Smart Path Validation ──────────────────────────────────────
    let pathDebounceTimers = {};

    function setupPathValidation() {
        const fields = [
            { id: 'dpr-files-path',    hint: 'dpr',     status: 'dpr-path-status' },
            { id: 'output-csv-path',   hint: 'output',  status: 'output-path-status' },
        ];
        fields.forEach(f => {
            const el = document.getElementById(f.id);
            if (!el) return;
            // Validate on blur
            el.addEventListener('blur', () => validateSinglePath(f.id, f.hint, f.status));
            // Debounced validation on input (500ms)
            el.addEventListener('input', () => {
                clearTimeout(pathDebounceTimers[f.id]);
                pathDebounceTimers[f.id] = setTimeout(
                    () => validateSinglePath(f.id, f.hint, f.status), 600
                );
            });
        });
    }

    async function validateSinglePath(inputId, hint, statusId) {
        const val = document.getElementById(inputId).value.trim();
        const statusEl = document.getElementById(statusId);
        const inputEl = document.getElementById(inputId);
        if (!statusEl) return;

        if (!val) {
            statusEl.innerHTML = '';
            inputEl.classList.remove('input-valid', 'input-invalid');
            return;
        }

        // Show loading
        statusEl.innerHTML = '<span class="path-checking"><span class="spinner"></span> Checking...</span>';

        try {
            const res = await fetch('/api/validate-single-path', {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ path: val, hint }),
            });
            const data = await res.json();
            renderSmartStatus(statusId, inputId, data);
        } catch (e) {
            statusEl.innerHTML = '<span class="invalid">❌ Network error</span>';
            inputEl.classList.add('input-invalid');
            inputEl.classList.remove('input-valid');
        }
    }

    async function validatePaths(paths) {
        try {
            const res = await fetch('/api/validate-paths', {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(paths),
            });
            const data = await res.json();
            renderSmartStatus('dpr-path-status', 'dpr-files-path', data.dpr);
            renderSmartStatus('output-path-status', 'output-csv-path', data.output);
        } catch (e) { /* ignore */ }
    }

    function renderSmartStatus(statusId, inputId, info) {
        const el = document.getElementById(statusId);
        const inputEl = document.getElementById(inputId);
        if (!el || !info) return;

        if (!info.exists) {
            el.innerHTML = `<span class="path-invalid">❌ ${I18n.lang() === 'fr' ? 'Chemin introuvable' : 'Path not found'}</span>`;
            inputEl.classList.add('input-invalid');
            inputEl.classList.remove('input-valid');
            return;
        }

        inputEl.classList.add('input-valid');
        inputEl.classList.remove('input-invalid');

        const n = info.file_count || 0;
        const hint = info.hint || '';
        let html = '';

        // Header line
        const filesWord = I18n.lang() === 'fr' ? 'fichiers' : 'files';
        html += `<span class="path-valid">✓ `;
        if (n > 0) {
            html += `${n} ${filesWord}`;
            // Extension breakdown
            if (info.extensions && Object.keys(info.extensions).length > 0) {
                const extParts = Object.entries(info.extensions)
                    .map(([ext, count]) => `${count}${ext}`)
                    .join(', ');
                html += ` <span class="path-ext">(${extParts})</span>`;
            }
        } else if (hint === 'output') {
            html += I18n.lang() === 'fr' ? 'Dossier prêt' : 'Folder ready';
        } else {
            html += I18n.lang() === 'fr' ? 'Dossier vide' : 'Empty folder';
        }
        html += '</span>';

        // Mapping-specific: concession match info
        if (hint === 'mapping' && info.total_expected > 0) {
            const matched = info.matched_concessions || 0;
            const total = info.total_expected;
            const pct = Math.round((matched / total) * 100);
            const color = pct === 100 ? 'var(--success)' : pct >= 50 ? 'var(--warning)' : 'var(--error)';
            const label = I18n.lang() === 'fr' ? 'concessions couvertes' : 'concessions matched';
            html += `<div class="path-match" style="color:${color}">○ ${matched}/${total} ${label} (${pct}%)</div>`;

            // Missing files
            if (info.missing_mappings && info.missing_mappings.length > 0) {
                const missingLabel = I18n.lang() === 'fr' ? 'Manquants' : 'Missing';
                html += `<div class="path-missing">⚠ ${missingLabel}: ${info.missing_mappings.join(', ')}</div>`;
            }
        }

        // Sample files preview
        if (info.sample_files && info.sample_files.length > 0 && hint !== 'output') {
            const more = n > info.sample_files.length ? ` +${n - info.sample_files.length} more` : '';
            html += `<div class="path-samples">${info.sample_files.join(', ')}${more}</div>`;
        }

        el.innerHTML = html;
    }

    // ── Form Handlers ──────────────────────────────────────────────
    function getReportType() {
        return document.querySelector('input[name="report-type"]:checked')?.value || 'daily';
    }

    function onReportChange() {
        const type = getReportType();
        const sub = document.getElementById('daily-sub-checks');
        if (sub) sub.style.display = type === 'daily' ? 'flex' : 'none';
    }

    function onDateModeChange() {
        const mode = document.querySelector('input[name="date-mode"]:checked')?.value || 'dpr';
        document.getElementById('date-fields-dpr').style.display = mode === 'dpr' ? 'block' : 'none';
        document.getElementById('date-fields-selection').style.display = mode === 'selection' ? 'block' : 'none';
    }

    function onMultipleChange() {
        const checked = document.getElementById('opt-multiple')?.checked;
        document.getElementById('multi-fields').style.display = checked ? 'block' : 'none';
    }

    function getSelectedDate() {
        const mode = document.querySelector('input[name="date-mode"]:checked')?.value || 'dpr';
        if (mode === 'dpr') {
            return document.getElementById('date-dpr').value || null;
        }
        const d = document.getElementById('sel-day').value;
        const m = document.getElementById('sel-month').value;
        const y = document.getElementById('sel-year').value;
        return `${y}-${String(m).padStart(2,'0')}-${String(d).padStart(2,'0')}`;
    }

    // ── Extraction ─────────────────────────────────────────────────
    async function extract() {
        const reportType = getReportType();
        const isMultiple = document.getElementById('opt-multiple')?.checked;
        const nameMode = document.querySelector('input[name="name-mode"]:checked')?.value || 'auto';
        const dprSource = getDPRSource();

        // Validate inputs before sending
        if (dprSource === 'upload') {
            const successFiles = uploadedFiles.filter(f => f.status === 'success');
            if (successFiles.length === 0) {
                toast('Please upload DPR file(s) first', 'warning');
                return;
            }
        } else {
            const folderPath = document.getElementById('dpr-files-path').value.trim();
            if (!folderPath) {
                toast('Please enter a DPR folder path', 'warning');
                return;
            }
        }

        const body = {
            report_type: reportType,
            date_dpr: getSelectedDate(),
            dpr_source: dprSource,
            dpr_folder: document.getElementById('dpr-files-path').value.trim(),
            output_folder: document.getElementById('output-csv-path').value.trim(),
            auto_detect_name: nameMode === 'auto',
            concatenate: document.getElementById('opt-concatenate').checked,
            num_days: isMultiple ? (parseInt(document.getElementById('num-days').value) || 1) : 1,
            concession_ids: getSelectedConcessionIds(),
            uploaded_file_ids: uploadedFiles.filter(f => f.status === 'success').map(f => f.id),
        };

        // For daily, pass which sub-types are selected
        if (reportType === 'daily') {
            body.extract_dc = document.getElementById('opt-dc')?.checked ?? true;
            body.extract_dw = document.getElementById('opt-dw')?.checked ?? true;
        }

        setLoading(true);
        setPipelineStep('extract');

        try {
            const res = await fetch('/api/extract', {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body),
            });
            const data = await res.json();

            if (res.ok) {
                currentExtractionId = data.id;
                renderPreview(data.columns, data.data);
                enablePostExtract();
                const statEl = document.getElementById('stat-records');
                if (statEl) statEl.textContent = data.record_count;
                setPipelineStep('extract', true);
                toast(`Extracted ${data.record_count} records`, 'success');

                // Populate output pages
                populateOutputPages(data, body.report_type);
            } else {
                toast(data.detail || 'Extraction failed', 'error');
            }
        } catch (e) {
            toast('Extraction error: ' + e.message, 'error');
        }
        setLoading(false);
    }

    function enablePostExtract() {
        const el1 = document.getElementById('btn-correct');
        const el2 = document.getElementById('btn-convert');
        const el3 = document.getElementById('btn-export');
        if (el1) el1.disabled = false;
        if (el2) el2.disabled = false;
        if (el3) el3.disabled = false;
    }

    function populateOutputPages(data, reportType) {
        // For daily extraction, populate both DC and DW if available
        if (reportType === 'daily') {
            if (data.dc_data && data.dc_data.length > 0)
                renderOutputTable('dc', data.dc_data, data.dc_columns);
            if (data.dw_data && data.dw_data.length > 0)
                renderOutputTable('dw', data.dw_data, data.dw_columns);
        } else if (reportType === 'monthly') {
            if (data.mc_data && data.mc_data.length > 0)
                renderOutputTable('mc', data.mc_data, data.mc_columns);
            else if (data.data && data.data.length > 0)
                renderOutputTable('mc', data.data, data.columns);
        } else if (reportType === 'well_test') {
            if (data.wt_data && data.wt_data.length > 0)
                renderOutputTable('wt', data.wt_data, data.wt_columns);
            else if (data.data && data.data.length > 0)
                renderOutputTable('wt', data.data, data.columns);
        }
        // Also populate preview with all data
        if (data.data && data.data.length > 0)
            renderOutputTable('preview', data.data, data.columns);
    }

    function renderOutputTable(type, data, explicitCols) {
        if (!data || data.length === 0) return;

        const cols = explicitCols || Object.keys(data[0]);
        const isOutputPage = ['dc','dw','mc','wt'].includes(type);
        const theadId = type === 'preview' ? 'preview-thead' : `thead-${type}`;
        const tbodyId = type === 'preview' ? 'preview-tbody' : `tbody-${type}`;
        const infoId = `${type}-info`;
        const badgeId = `badge-${type}`;

        const thead = document.getElementById(theadId);
        const tbody = document.getElementById(tbodyId);

        // ── Build header with attribute names ──
        if (thead) {
            if (isOutputPage) {
                thead.innerHTML = '<tr>' +
                    `<th class="cell-check"><input type="checkbox" onchange="App.toggleSelectAll('${type}',this.checked)" title="Select all"></th>` +
                    '<th class="row-num">#</th>' +
                    cols.map((c, i) => {
                        const attrName = attributeMap[c] || '';
                        if (attrName) {
                            return `<th title="${c}: ${attrName}"><span class="col-attr-name">${attrName}</span><span class="col-code">${c}</span></th>`;
                        }
                        return `<th><span class="col-index">${i + 1}</span>${c}</th>`;
                    }).join('') +
                    '</tr>';
            } else {
                thead.innerHTML = '<tr>' + cols.map(c => {
                    const attrName = attributeMap[c];
                    if (attrName) return `<th title="${c}">${attrName}</th>`;
                    return `<th>${c}</th>`;
                }).join('') + '</tr>';
            }
        }

        // ── Build body with smart cell formatting ──
        if (tbody) {
            const maxRows = Math.min(data.length, 500);
            if (isOutputPage) {
                // Clear selection state
                if (selectedRows[type]) selectedRows[type].clear();

                tbody.innerHTML = data.slice(0, maxRows).map((row, ri) =>
                    `<tr>${buildRowHTML(type, row, ri, cols)}</tr>`
                ).join('');

                // Attach double-click events for inline editing
                const trs = tbody.querySelectorAll('tr');
                trs.forEach((tr, ri) => attachRowEvents(type, tr, ri, cols));
            } else {
                tbody.innerHTML = data.slice(0, maxRows).map((row, ri) => {
                    const cells = cols.map(c => {
                        let v = row[c];
                        const cls = getCellClass(v);
                        const display = formatCellValue(v);
                        return `<td class="${cls}">${display}</td>`;
                    }).join('');
                    return `<tr>${cells}</tr>`;
                }).join('');
            }
        }

        // ── Update info subtitle ──
        const info = document.getElementById(infoId);
        if (info) info.textContent = `${cols.length} columns · ${data.length} rows`;

        // ── Update nav badge ──
        const badge = document.getElementById(badgeId);
        if (badge) { badge.textContent = data.length; badge.style.display = ''; }

        // ── Update KPIs ──
        if (isOutputPage) {
            const kpiRows = document.getElementById(`kpi-${type}-rows`);
            const kpiCols = document.getElementById(`kpi-${type}-cols`);
            const kpiFilled = document.getElementById(`kpi-${type}-filled`);
            if (kpiRows) kpiRows.textContent = data.length;
            if (kpiCols) kpiCols.textContent = cols.length;
            if (kpiFilled) {
                let total = 0, filled = 0;
                data.forEach(row => {
                    cols.forEach(c => {
                        total++;
                        const v = row[c];
                        if (v !== null && v !== undefined && v !== '') filled++;
                    });
                });
                kpiFilled.textContent = total > 0 ? Math.round((filled / total) * 100) + '%' : '--';
            }
        }

        // Store raw data for search
        if (isOutputPage) {
            extractionData[type] = { rows: data, cols: cols };
        }
    }

    function filterOutputTable(type) {
        const input = document.getElementById(`search-${type}`);
        if (!input) return;
        const query = input.value.toLowerCase().trim();
        const stored = extractionData[type];
        if (!stored || !stored.rows) return;

        const tbody = document.getElementById(`tbody-${type}`);
        if (!tbody) return;

        const rows = tbody.querySelectorAll('tr');
        let visible = 0;

        if (!query) {
            rows.forEach(r => { r.style.display = ''; r.classList.remove('highlight'); });
            // Remove highlights
            tbody.querySelectorAll('mark').forEach(m => {
                m.replaceWith(document.createTextNode(m.textContent));
            });
            const info = document.getElementById(`${type}-info`);
            if (info) info.textContent = `${stored.cols.length} columns · ${stored.rows.length} rows`;
            return;
        }

        rows.forEach((tr, i) => {
            const cells = tr.querySelectorAll('td:not(.row-num)');
            let match = false;
            cells.forEach(td => {
                const text = td.textContent.toLowerCase();
                if (text.includes(query)) match = true;
            });
            tr.style.display = match ? '' : 'none';
            tr.classList.toggle('highlight', match && query.length > 1);
            if (match) visible++;
        });

        const info = document.getElementById(`${type}-info`);
        if (info) info.textContent = `${stored.cols.length} columns · ${visible}/${stored.rows.length} rows`;
    }

    function toggleOutputCompact(type) {
        const container = document.getElementById(`output-container-${type}`);
        if (container) container.classList.toggle('compact');
    }

    // ══════════════════════════════════════════════════════════════════
    // CRUD — inline edit, add row, delete row, undo/redo
    // ══════════════════════════════════════════════════════════════════

    // Undo/redo stacks per type
    const undoStacks = { dc: [], dw: [], mc: [], wt: [] };
    const redoStacks = { dc: [], dw: [], mc: [], wt: [] };
    // Selected rows per type
    const selectedRows = { dc: new Set(), dw: new Set(), mc: new Set(), wt: new Set() };

    function pushUndo(type, action) {
        undoStacks[type].push(action);
        redoStacks[type] = []; // clear redo on new action
        updateUndoRedoButtons(type);
    }

    function updateUndoRedoButtons(type) {
        const undo = document.getElementById(`undo-${type}`);
        const redo = document.getElementById(`redo-${type}`);
        if (undo) undo.disabled = undoStacks[type].length === 0;
        if (redo) redo.disabled = redoStacks[type].length === 0;
    }

    // ── Inline Cell Editing ──────────────────────────────────────────

    function startCellEdit(type, rowIndex, colName, td) {
        if (td.classList.contains('cell-editing')) return;
        const stored = extractionData[type];
        if (!stored) return;

        const currentValue = stored.rows[rowIndex]?.[colName] ?? '';
        const originalHTML = td.innerHTML;
        const originalClasses = td.className;

        td.className = 'cell-editing';
        const input = document.createElement('input');
        input.type = 'text';
        input.value = currentValue === null || currentValue === undefined ? '' : String(currentValue);
        td.innerHTML = '';
        td.appendChild(input);
        input.focus();
        input.select();

        const finish = (save) => {
            if (save) {
                const newVal = input.value;
                // Try to parse as number
                let parsedVal = newVal;
                if (newVal !== '' && !isNaN(newVal) && newVal.trim() !== '') {
                    parsedVal = Number(newVal);
                }
                saveCellEdit(type, rowIndex, colName, parsedVal, currentValue, td);
            } else {
                td.className = originalClasses;
                td.innerHTML = originalHTML;
            }
        };

        input.addEventListener('keydown', e => {
            if (e.key === 'Enter') { e.preventDefault(); finish(true); }
            if (e.key === 'Escape') { e.preventDefault(); finish(false); }
            if (e.key === 'Tab') { e.preventDefault(); finish(true); }
        });
        input.addEventListener('blur', () => {
            // Short delay to allow click events to fire
            setTimeout(() => { if (td.classList.contains('cell-editing')) finish(true); }, 100);
        });
    }

    async function saveCellEdit(type, rowIndex, colName, newValue, oldValue, td) {
        if (!currentExtractionId) return;
        try {
            const res = await fetch(
                `/api/records/${currentExtractionId}/${type}/${rowIndex}`,
                {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ field: colName, value: newValue }),
                }
            );
            if (!res.ok) throw new Error(await res.text());

            // Update local data
            const stored = extractionData[type];
            if (stored) stored.rows[rowIndex][colName] = newValue;

            // Re-render cell with smart formatting
            td.className = getCellClass(newValue);
            td.innerHTML = formatCellValue(newValue);
            td.classList.add('cell-saved');
            setTimeout(() => td.classList.remove('cell-saved'), 800);

            // Push undo
            pushUndo(type, {
                action: 'update',
                rowIndex, colName, oldValue, newValue,
            });

            refreshKPIs(type);
        } catch (err) {
            toast(`Save failed: ${err.message}`, 'error');
            // Revert
            td.className = getCellClass(oldValue);
            td.innerHTML = formatCellValue(oldValue);
        }
    }

    function isDateValue(value) {
        if (value === null || value === undefined || value === '' || typeof value === 'number') return false;
        const sv = String(value);
        // ISO format: 2024-11-04 or 2024-11-04T00:00:00
        if (/^\d{4}-\d{2}-\d{2}/.test(sv)) return true;
        // dd/mm/yyyy format
        if (/^\d{2}\/\d{2}\/\d{4}/.test(sv)) return true;
        return false;
    }

    function getCellClass(value) {
        if (value === null || value === undefined || value === '') return 'cell-empty';
        if (typeof value === 'number') return 'cell-num';
        const sv = String(value);
        if (isDateValue(sv)) return 'cell-date';
        if (sv.length > 40) return 'cell-text cell-long';
        return 'cell-text';
    }

    function formatCellValue(value) {
        if (value === null || value === undefined || value === '') return '—';
        if (typeof value === 'number') {
            if (Number.isInteger(value)) return value.toLocaleString();
            // Use 2 decimals for production-scale values, 4 for small ones
            const decimals = Math.abs(value) >= 1 ? 2 : 4;
            return value.toLocaleString(undefined, { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
        }
        const sv = String(value);
        // Format dates as dd/mm/yyyy (matching VBA output format)
        const dateMatch = sv.match(/^(\d{4})-(\d{2})-(\d{2})(?:[T ](.*))?\s*$/);
        if (dateMatch) {
            const [, y, m, d, time] = dateMatch;
            const formatted = `${d}/${m}/${y}`;
            if (time && time !== '00:00:00' && time !== '00:00') {
                return `${formatted} ${time.replace(/:\d{2}$/, '')}`;
            }
            return formatted;
        }
        // Already dd/mm/yyyy — return as is
        if (/^\d{2}\/\d{2}\/\d{4}$/.test(sv)) return sv;
        // dd/mm/yyyy with time
        const ddMatch = sv.match(/^(\d{2}\/\d{2}\/\d{4})\s+(.+)$/);
        if (ddMatch) return ddMatch[1];
        const escaped = sv.replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/\n/g, ' → ');
        if (sv.length > 60) return `<span title="${escaped}">${escaped.substring(0, 55)}…</span>`;
        return escaped;
    }

    // ── Add Row ──────────────────────────────────────────────────────

    async function addRecord(type) {
        if (!currentExtractionId) {
            toast('No extraction active. Run an extraction first.', 'warning');
            return;
        }
        try {
            const res = await fetch(
                `/api/records/${currentExtractionId}/${type}`,
                { method: 'POST' }
            );
            if (!res.ok) throw new Error(await res.text());
            const data = await res.json();

            // Update local data
            const stored = extractionData[type];
            if (stored) {
                stored.rows.push(data.row);
                if (!stored.cols.length && data.columns) stored.cols = data.columns;
            }

            // Append row to table
            const tbody = document.getElementById(`tbody-${type}`);
            if (tbody && stored) {
                const ri = stored.rows.length - 1;
                const tr = document.createElement('tr');
                tr.className = 'row-new';
                tr.innerHTML = buildRowHTML(type, data.row, ri, stored.cols);
                tbody.appendChild(tr);
                attachRowEvents(type, tr, ri, stored.cols);
                // Scroll to new row
                tr.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
            }

            pushUndo(type, { action: 'create', rowIndex: data.row_index });
            refreshKPIs(type);
            toast('Row added', 'success');
        } catch (err) {
            toast(`Add row failed: ${err.message}`, 'error');
        }
    }

    // ── Delete Row ───────────────────────────────────────────────────

    async function deleteRecord(type, rowIndex) {
        if (!currentExtractionId) {
            toast('No extraction active', 'warning');
            return;
        }
        const stored = extractionData[type];
        if (!stored || !stored.rows || rowIndex >= stored.rows.length) {
            toast('No data available for this table', 'warning');
            return;
        }

        const deletedRow = { ...stored.rows[rowIndex] };
        const tbody = document.getElementById(`tbody-${type}`);
        const tr = tbody?.querySelectorAll('tr')[rowIndex];

        // Animate out
        if (tr) {
            tr.classList.add('row-deleting');
            await new Promise(r => setTimeout(r, 250));
        }

        try {
            const res = await fetch(
                `/api/records/${currentExtractionId}/${type}/${rowIndex}`,
                { method: 'DELETE' }
            );
            if (!res.ok) throw new Error(await res.text());

            stored.rows.splice(rowIndex, 1);
            selectedRows[type].delete(rowIndex);
            // Re-render table to fix row numbers
            reRenderOutputTable(type);

            pushUndo(type, { action: 'delete', rowIndex, deletedRow });
            refreshKPIs(type);
            updateBulkDeleteBtn(type);
        } catch (err) {
            toast(`Delete failed: ${err.message}`, 'error');
            if (tr) tr.classList.remove('row-deleting');
        }
    }

    // ── Bulk Delete ──────────────────────────────────────────────────

    async function bulkDeleteRecords(type) {
        if (!currentExtractionId) {
            toast('No extraction active', 'warning');
            return;
        }
        const indices = Array.from(selectedRows[type]).sort((a, b) => b - a);
        if (indices.length === 0) {
            toast('No rows selected', 'warning');
            return;
        }

        if (!confirm(`Delete ${indices.length} selected row(s)?`)) return;

        try {
            const res = await fetch(
                `/api/records/${currentExtractionId}/${type}/bulk-delete`,
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ row_indices: indices }),
                }
            );
            if (!res.ok) throw new Error(await res.text());

            const stored = extractionData[type];
            const deletedRows = indices.map(i => ({ index: i, row: { ...stored.rows[i] } }));

            // Remove from local data (already sorted descending)
            indices.forEach(i => stored.rows.splice(i, 1));
            selectedRows[type].clear();

            reRenderOutputTable(type);

            pushUndo(type, { action: 'bulk_delete', deletedRows });
            refreshKPIs(type);
            updateBulkDeleteBtn(type);
            toast(`Deleted ${indices.length} row(s)`, 'success');
        } catch (err) {
            toast(`Bulk delete failed: ${err.message}`, 'error');
        }
    }

    // ── Clean Empty Rows ─────────────────────────────────────────────

    async function cleanEmptyRows(type) {
        if (!currentExtractionId) {
            toast('No extraction active', 'warning');
            return;
        }
        const stored = extractionData[type];
        if (!stored || !stored.rows || stored.rows.length === 0) {
            toast('No data to clean', 'warning');
            return;
        }

        // Find rows where ALL values are empty, null, undefined, or blank string
        const emptyIndices = [];
        stored.rows.forEach((row, i) => {
            const allEmpty = stored.cols.every(col => {
                const v = row[col];
                return v === null || v === undefined || v === '' || v === '—';
            });
            if (allEmpty) emptyIndices.push(i);
        });

        if (emptyIndices.length === 0) {
            toast('No empty rows found', 'info');
            return;
        }

        if (!confirm(`Found ${emptyIndices.length} empty row(s). Delete them?`)) return;

        try {
            const indices = emptyIndices.sort((a, b) => b - a);
            const res = await fetch(
                `/api/records/${currentExtractionId}/${type}/bulk-delete`,
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ row_indices: indices }),
                }
            );
            if (!res.ok) throw new Error(await res.text());

            const deletedRows = indices.map(i => ({ index: i, row: { ...stored.rows[i] } }));
            indices.forEach(i => stored.rows.splice(i, 1));
            selectedRows[type].clear();

            reRenderOutputTable(type);
            pushUndo(type, { action: 'bulk_delete', deletedRows });
            refreshKPIs(type);
            updateBulkDeleteBtn(type);
            toast(`Cleaned ${emptyIndices.length} empty row(s)`, 'success');
        } catch (err) {
            toast(`Clean failed: ${err.message}`, 'error');
        }
    }

    // ── Undo / Redo ──────────────────────────────────────────────────

    async function undoRecord(type) {
        const stack = undoStacks[type];
        if (stack.length === 0) return;
        const action = stack.pop();

        if (action.action === 'update') {
            // Revert cell to old value
            await applyRemoteCellUpdate(type, action.rowIndex, action.colName, action.oldValue);
            redoStacks[type].push({
                action: 'update',
                rowIndex: action.rowIndex,
                colName: action.colName,
                oldValue: action.newValue,
                newValue: action.oldValue,
            });
        } else if (action.action === 'create') {
            // Delete the created row
            await fetch(`/api/records/${currentExtractionId}/${type}/${action.rowIndex}`, { method: 'DELETE' });
            const stored = extractionData[type];
            if (stored) stored.rows.splice(action.rowIndex, 1);
            reRenderOutputTable(type);
            redoStacks[type].push(action);
        } else if (action.action === 'delete') {
            // Re-insert the deleted row
            await reInsertRow(type, action.rowIndex, action.deletedRow);
            redoStacks[type].push(action);
        } else if (action.action === 'bulk_delete') {
            // Re-insert all deleted rows (ascending order)
            const sorted = [...action.deletedRows].sort((a, b) => a.index - b.index);
            for (const dr of sorted) {
                await reInsertRow(type, dr.index, dr.row);
            }
            redoStacks[type].push(action);
        }

        refreshKPIs(type);
        updateUndoRedoButtons(type);
    }

    async function redoRecord(type) {
        const stack = redoStacks[type];
        if (stack.length === 0) return;
        const action = stack.pop();

        if (action.action === 'update') {
            await applyRemoteCellUpdate(type, action.rowIndex, action.colName, action.oldValue);
            undoStacks[type].push({
                action: 'update',
                rowIndex: action.rowIndex,
                colName: action.colName,
                oldValue: action.newValue,
                newValue: action.oldValue,
            });
        } else if (action.action === 'create') {
            // Re-add the row
            const res = await fetch(`/api/records/${currentExtractionId}/${type}`, { method: 'POST' });
            const data = await res.json();
            const stored = extractionData[type];
            if (stored) stored.rows.push(data.row);
            reRenderOutputTable(type);
            undoStacks[type].push(action);
        } else if (action.action === 'delete') {
            // Delete again
            await fetch(`/api/records/${currentExtractionId}/${type}/${action.rowIndex}`, { method: 'DELETE' });
            const stored = extractionData[type];
            if (stored) stored.rows.splice(action.rowIndex, 1);
            reRenderOutputTable(type);
            undoStacks[type].push(action);
        } else if (action.action === 'bulk_delete') {
            const indices = action.deletedRows.map(d => d.index).sort((a, b) => b - a);
            await fetch(`/api/records/${currentExtractionId}/${type}/bulk-delete`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ row_indices: indices }),
            });
            const stored = extractionData[type];
            if (stored) indices.forEach(i => stored.rows.splice(i, 1));
            reRenderOutputTable(type);
            undoStacks[type].push(action);
        }

        refreshKPIs(type);
        updateUndoRedoButtons(type);
    }

    async function applyRemoteCellUpdate(type, rowIndex, colName, value) {
        await fetch(`/api/records/${currentExtractionId}/${type}/${rowIndex}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ field: colName, value }),
        });
        const stored = extractionData[type];
        if (stored) stored.rows[rowIndex][colName] = value;
        reRenderOutputTable(type);
    }

    async function reInsertRow(type, index, row) {
        // POST creates at end, but we need to insert at specific index
        // For simplicity, POST then swap in local data
        const res = await fetch(`/api/records/${currentExtractionId}/${type}`, { method: 'POST' });
        const data = await res.json();

        const stored = extractionData[type];
        if (stored) {
            // Remove from end (where POST put it)
            stored.rows.pop();
            // Insert at original index
            stored.rows.splice(index, 0, row);
        }

        // Now update each cell on the server so it has the right values
        for (const [col, val] of Object.entries(row)) {
            if (val !== '' && val !== null) {
                await fetch(`/api/records/${currentExtractionId}/${type}/${index}`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ field: col, value: val }),
                });
            }
        }
        reRenderOutputTable(type);
    }

    // ── Checkbox selection ───────────────────────────────────────────

    function toggleRowSelect(type, rowIndex, checked) {
        if (checked) {
            selectedRows[type].add(rowIndex);
        } else {
            selectedRows[type].delete(rowIndex);
        }
        const tbody = document.getElementById(`tbody-${type}`);
        if (tbody) {
            const tr = tbody.querySelectorAll('tr')[rowIndex];
            if (tr) tr.classList.toggle('row-selected', checked);
        }
        updateBulkDeleteBtn(type);
    }

    function toggleSelectAll(type, checked) {
        const stored = extractionData[type];
        if (!stored) return;
        const tbody = document.getElementById(`tbody-${type}`);
        if (!tbody) return;

        const rows = tbody.querySelectorAll('tr');
        rows.forEach((tr, i) => {
            const cb = tr.querySelector('.cell-check input[type="checkbox"]');
            if (cb) cb.checked = checked;
            tr.classList.toggle('row-selected', checked);
            if (checked) selectedRows[type].add(i);
            else selectedRows[type].delete(i);
        });
        updateBulkDeleteBtn(type);
    }

    function updateBulkDeleteBtn(type) {
        const btn = document.getElementById(`bulk-del-${type}`);
        if (btn) {
            const count = selectedRows[type].size;
            btn.style.display = count > 0 ? '' : 'none';
            if (count > 0) btn.textContent = `🗑 Delete ${count} selected`;
        }
    }

    // ── Helpers ───────────────────────────────────────────────────────

    function buildRowHTML(type, row, ri, cols) {
        const checkCell = `<td class="cell-check"><input type="checkbox" onchange="App.toggleRowSelect('${type}',${ri},this.checked)"></td>`;
        const numCell = `<td class="row-num">${ri + 1}<button class="row-del" onclick="App.deleteRecord('${type}',${ri})" title="Delete row">✕</button></td>`;
        const dataCells = cols.map(c => {
            const v = row[c];
            const cls = getCellClass(v);
            const display = formatCellValue(v);
            return `<td class="${cls}">${display}</td>`;
        }).join('');
        return checkCell + numCell + dataCells;
    }

    function attachRowEvents(type, tr, ri, cols) {
        const dataCells = tr.querySelectorAll('td:not(.cell-check):not(.row-num)');
        dataCells.forEach((td, ci) => {
            td.addEventListener('dblclick', (e) => {
                e.stopPropagation();
                startCellEdit(type, ri, cols[ci], td);
            });
        });
        // Single-click opens record detail
        tr.addEventListener('click', (e) => {
            // Don't open if clicking checkbox, delete button, or editing
            if (e.target.closest('.cell-check') || e.target.closest('.row-del') ||
                e.target.closest('.cell-editing') || e.target.tagName === 'INPUT') return;
            openRecordDetail(type, ri);
        });
    }

    function reRenderOutputTable(type) {
        const stored = extractionData[type];
        if (!stored) return;
        renderOutputTable(type, stored.rows, stored.cols);
    }

    function refreshKPIs(type) {
        const stored = extractionData[type];
        if (!stored) return;
        const data = stored.rows;
        const cols = stored.cols;

        const kpiRows = document.getElementById(`kpi-${type}-rows`);
        const kpiCols = document.getElementById(`kpi-${type}-cols`);
        const kpiFilled = document.getElementById(`kpi-${type}-filled`);
        const info = document.getElementById(`${type}-info`);
        const badge = document.getElementById(`badge-${type}`);

        if (kpiRows) kpiRows.textContent = data.length;
        if (kpiCols) kpiCols.textContent = cols.length;
        if (info) info.textContent = `${cols.length} columns · ${data.length} rows`;
        if (badge) { badge.textContent = data.length; badge.style.display = data.length > 0 ? '' : 'none'; }

        if (kpiFilled) {
            let total = 0, filled = 0;
            data.forEach(row => {
                cols.forEach(c => {
                    total++;
                    const v = row[c];
                    if (v !== null && v !== undefined && v !== '') filled++;
                });
            });
            kpiFilled.textContent = total > 0 ? Math.round((filled / total) * 100) + '%' : '--';
        }
    }

    // Keyboard shortcuts: Ctrl+Z = undo, Ctrl+Y = redo
    document.addEventListener('keydown', (e) => {
        if (!e.ctrlKey && !e.metaKey) return;
        // Detect which output page is active
        const activeSection = document.querySelector('.section.active[id^="section-output-"], .section.active#section-well-test');
        if (!activeSection) return;
        const type = activeSection.id === 'section-well-test' ? 'wt'
            : activeSection.id.replace('section-output-', '');
        if (!['dc', 'dw', 'mc', 'wt'].includes(type)) return;

        if (e.key === 'z' || e.key === 'Z') {
            e.preventDefault();
            undoRecord(type);
        } else if (e.key === 'y' || e.key === 'Y') {
            e.preventDefault();
            redoRecord(type);
        }
    });


    async function autoCorrect() {
        if (!currentExtractionId) return;
        setLoading(true);
        setPipelineStep('correct');

        try {
            const res = await fetch(`/api/auto-correct/${currentExtractionId}`, { method: 'POST' });
            const data = await res.json();
            if (res.ok) {
                toast(`Cleaned: ${data.corrections_count} fixes applied`, 'success');
                setPipelineStep('correct', true);
                refreshExtraction();
            } else {
                toast(data.detail || 'Cleaning failed', 'error');
            }
        } catch (e) { toast('Error', 'error'); }
        setLoading(false);
    }

    async function convertUnits() {
        if (!currentExtractionId) return;
        try {
            const res = await fetch(`/api/convert-units/${currentExtractionId}?direction=sm3_to_nm3`, { method: 'POST' });
            const data = await res.json();
            if (res.ok) {
                toast(`Converted ${data.conversions} values (SM3→NM3)`, 'success');
                refreshExtraction();
            } else { toast(data.detail || 'Conversion failed', 'error'); }
        } catch (e) { toast('Error', 'error'); }
    }

    async function exportCSV() {
        if (!currentExtractionId) return;
        setLoading(true);
        setPipelineStep('export');

        const reportType = getReportType();
        try {
            const res = await fetch(`/api/export-csv/${currentExtractionId}?report_type=${reportType}`, { method: 'POST' });
            const data = await res.json();
            if (res.ok) {
                toast(`Exported: ${data.filename}`, 'success');
                setPipelineStep('export', true);
                incrStat('stat-exports');
            } else { toast(data.detail || 'Export failed', 'error'); }
        } catch (e) { toast('Error', 'error'); }
        setLoading(false);
    }

    async function exportType(type) {
        if (!currentExtractionId) { toast(I18n.t('toast.extract_first'), 'warning'); return; }
        try {
            const res = await fetch(`/api/export-csv/${currentExtractionId}?report_type=${type}`, { method: 'POST' });
            const data = await res.json();
            if (res.ok) {
                toast(`Exported: ${data.filename}`, 'success');
                incrStat('stat-exports');
            } else { toast(data.detail || 'Export failed', 'error'); }
        } catch (e) { toast('Error', 'error'); }
    }

    async function exportPDF(type) {
        if (!currentExtractionId) { toast(I18n.t('toast.extract_first') || 'Run extraction first', 'warning'); return; }
        try {
            // Map API report_type to internal selectedRows key
            const internalKeyMap = { monthly: 'mc', well_test: 'wt' };
            const internalKey = internalKeyMap[type] || type;
            // Collect selected row indices for this type
            const selected = Array.from(selectedRows[internalKey] || []);
            if (selected.length === 0) {
                toast('Select at least one record to export', 'warning');
                return;
            }
            toast(`Generating PDF report for ${selected.length} record(s)...`, 'info');
            const res = await fetch(`/api/export-pdf/${currentExtractionId}?report_type=${type || 'daily'}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    row_indices: selected,
                    attribute_map: attributeMap,
                }),
            });
            const data = await res.json();
            if (res.ok) {
                toast(`PDF exported: ${data.filename}`, 'success');
                // Auto-open the PDF in a new tab
                if (data.download_url) {
                    window.open(data.download_url, '_blank');
                }
                incrStat('stat-exports');
            } else {
                toast(data.detail || 'PDF export failed', 'error');
            }
        } catch (e) {
            console.error('PDF export error:', e);
            toast('PDF export error', 'error');
        }
    }

    async function refreshExtraction() {
        if (!currentExtractionId) return;
        try {
            const res = await fetch(`/api/extractions/${currentExtractionId}`);
            const data = await res.json();
            renderPreview(data.columns, data.data);
            // Re-populate all output grids with fresh data from backend
            populateOutputPages(data, data.report_type);
            // Update record count badge
            const statEl = document.getElementById('stat-records');
            if (statEl) statEl.textContent = data.record_count;
        } catch (e) { console.warn('refreshExtraction failed:', e); }
    }

    // ── Rendering ─────────────────────────────────────────────────
    function renderPreview(columns, data) {
        const thead = document.getElementById('preview-thead');
        const tbody = document.getElementById('preview-tbody');
        const count = document.getElementById('preview-count');

        if (!columns || !data || !data.length) {
            if (tbody) tbody.innerHTML = '<tr><td class="empty-row" colspan="99">No data</td></tr>';
            if (thead) thead.innerHTML = '';
            if (count) count.textContent = '';
            return;
        }
        if (count) count.textContent = `(${data.length} rows × ${columns.length} cols)`;
        if (thead) thead.innerHTML = '<tr>' + columns.map(c => `<th>${c}</th>`).join('') + '</tr>';

        const max = Math.min(data.length, 100);
        if (tbody) tbody.innerHTML = data.slice(0, max).map(row =>
            '<tr>' + columns.map(c => {
                let v = row[c]; if (v == null) v = '';
                if (typeof v === 'number') v = Number.isInteger(v) ? v : v.toFixed(4);
                return `<td>${v}</td>`;
            }).join('') + '</tr>'
        ).join('');
    }

    // ── Pipeline ──────────────────────────────────────────────────
    function setPipelineStep(step, done = false) {
        const steps = ['config', 'extract', 'correct', 'export'];
        const idx = steps.indexOf(step);
        steps.forEach((s, i) => {
            const el = document.getElementById(`step-${s}`);
            if (!el) return;
            el.classList.remove('active', 'completed');
            if (i < idx) el.classList.add('completed');
            else if (i === idx) el.classList.add(done ? 'completed' : 'active');
        });
    }

    function setLoading(on) {
        const el = document.getElementById('btn-extract');
        if (el) el.disabled = on;
    }

    // ── WebSocket ─────────────────────────────────────────────────
    function setupWebSocket() {
        const proto = location.protocol === 'https:' ? 'wss' : 'ws';
        ws = new WebSocket(`${proto}://${location.host}/ws/logs`);
        ws.onopen = () => {
            const dot = document.getElementById('status-dot');
            const txt = document.getElementById('sidebar-status-text');
            if (dot) dot.className = 'status-dot live';
            if (txt) txt.textContent = I18n.lang() === 'fr' ? 'Système prêt' : 'System Ready';
        };
        ws.onmessage = e => {
            try { appendLog(JSON.parse(e.data)); } catch { /* ignore */ }
        };
        ws.onclose = () => {
            const dot = document.getElementById('status-dot');
            const txt = document.getElementById('sidebar-status-text');
            if (dot) dot.className = 'status-dot offline';
            if (txt) txt.textContent = I18n.t('sidebar.status.reconnecting');
            setTimeout(setupWebSocket, 3000);
        };
    }

    function appendLog(msg) {
        const targets = ['extract-logs', 'dashboard-logs', 'full-logs'];
        const colors = {
            error: '#ef5350', warning: '#ffa726', success: '#66bb6a', info: '#90a4ae'
        };
        const time = new Date().toLocaleTimeString();
        const html = `<div class="log-entry" style="color:${colors[msg.level] || colors.info}">
            <span class="log-time">${time}</span>
            <span class="log-src">[${msg.source || ''}]</span>
            ${msg.message}
        </div>`;

        targets.forEach(id => {
            const el = document.getElementById(id);
            if (!el) return;
            const empty = el.querySelector('.empty-state');
            if (empty) empty.remove();
            el.insertAdjacentHTML('beforeend', html);
            el.scrollTop = el.scrollHeight;
        });
    }

    function clearLogs() {
        ['extract-logs', 'dashboard-logs', 'full-logs'].forEach(id => {
            const el = document.getElementById(id);
            if (el) el.innerHTML = '';
        });
    }

    // ── Helpers ────────────────────────────────────────────────────
    function formatSize(b) {
        if (b < 1024) return b + ' B';
        if (b < 1048576) return (b / 1024).toFixed(1) + ' KB';
        return (b / 1048576).toFixed(1) + ' MB';
    }

    function incrStat(id) {
        const el = document.getElementById(id);
        if (el) el.textContent = (parseInt(el.textContent) || 0) + 1;
    }

    function toast(message, type = 'info') {
        const c = document.getElementById('toast-container');
        const el = document.createElement('div');
        el.className = `toast toast-${type}`;
        el.textContent = message;
        c.appendChild(el);
        setTimeout(() => { el.style.opacity = '0'; setTimeout(() => el.remove(), 200); }, 3500);
    }

    function refreshDashboard() { loadConfig(); loadDashboardInsights(); I18n.apply(); }

    function prepareFiles() {
        toast(I18n.t('toast.prepare_files'), 'info');
        // Will integrate with backend /api/prepare-files once available
    }

    function clearExtraction() {
        currentExtractionId = null;
        extractionData = { dc: null, dw: null, mc: null, wt: null };
        const btnCorrect = document.getElementById('btn-correct');
        const btnConvert = document.getElementById('btn-convert');
        const btnExport = document.getElementById('btn-export');
        if (btnCorrect) btnCorrect.disabled = true;
        if (btnConvert) btnConvert.disabled = true;
        if (btnExport) btnExport.disabled = true;

        // Clear preview
        const thead = document.getElementById('preview-thead');
        const tbody = document.getElementById('preview-tbody');
        if (thead) thead.innerHTML = '';
        if (tbody) tbody.innerHTML = `<tr><td class="empty-row" colspan="99">${I18n.t('extract.no_data')}</td></tr>`;
        const previewCount = document.getElementById('preview-count');
        if (previewCount) previewCount.textContent = '';
        const statRecords = document.getElementById('stat-records');
        if (statRecords) statRecords.textContent = '0';

        // Reset pipeline
        ['config','extract','correct','export'].forEach(s => {
            const el = document.getElementById(`step-${s}`);
            if (el) el.classList.remove('active','completed');
        });

        toast(I18n.t('toast.cleared'), 'info');
    }

    // ── Concession Chips ───────────────────────────────────────────
    async function loadConcessionChips() {
        try {
            const res = await fetch('/api/concessions');
            concessionList = await res.json();
            renderConcessionChips();
        } catch (e) { console.error('Failed to load concessions for chips:', e); }
    }

    function renderConcessionChips() {
        const container = document.getElementById('conc-chips');
        if (!container) return;

        if (!concessionList.length) {
            container.innerHTML = '<div class="conc-chips-loading">No concessions found</div>';
            updateConcCounter();
            return;
        }

        const selectAll = document.getElementById('conc-select-all');
        const allSelected = selectAll && selectAll.checked;

        container.innerHTML = concessionList.map(c => {
            const counts = (c.dc_count || 0) + (c.dw_count || 0) + (c.mc_count || 0) + (c.wt_count || 0);
            const isSelected = allSelected || selectedConcessions.has(c.id);
            if (allSelected) selectedConcessions.add(c.id);
            return `<div class="conc-chip ${isSelected ? 'selected' : ''}" data-id="${c.id}" onclick="App.toggleChip('${c.id}')">
                ${c.name}
                <span class="chip-counts">${counts}</span>
            </div>`;
        }).join('');
        updateConcCounter();
        setupChipFilter();
    }

    function toggleChip(id) {
        if (selectedConcessions.has(id)) {
            selectedConcessions.delete(id);
        } else {
            selectedConcessions.add(id);
        }
        const chip = document.querySelector(`.conc-chip[data-id="${id}"]`);
        if (chip) chip.classList.toggle('selected');

        // Update "All" checkbox
        const selectAll = document.getElementById('conc-select-all');
        if (selectAll) selectAll.checked = selectedConcessions.size === concessionList.length;
        updateConcCounter();
    }

    function toggleAllConcessions() {
        const selectAll = document.getElementById('conc-select-all');
        const checked = selectAll && selectAll.checked;
        concessionList.forEach(c => {
            if (checked) selectedConcessions.add(c.id);
            else selectedConcessions.delete(c.id);
        });
        document.querySelectorAll('.conc-chip').forEach(chip => {
            chip.classList.toggle('selected', checked);
        });
        updateConcCounter();
    }

    function getSelectedConcessionIds() {
        // If all are selected, send empty array (= "all")
        if (selectedConcessions.size === concessionList.length) return [];
        return Array.from(selectedConcessions);
    }

    function updateConcCounter() {
        const el = document.getElementById('conc-selected-count');
        if (el) {
            const n = selectedConcessions.size;
            const total = concessionList.length;
            el.textContent = n === total ? `All ${total} selected` : `${n} / ${total} selected`;
        }
    }

    function setupChipFilter() {
        const input = document.getElementById('conc-filter');
        if (!input) return;
        input.addEventListener('input', () => {
            const q = input.value.trim().toLowerCase();
            document.querySelectorAll('.conc-chip').forEach(chip => {
                const name = chip.textContent.toLowerCase();
                chip.classList.toggle('filtered-out', q && !name.includes(q));
            });
        });
    }

    // ── DPR Source Toggle ──────────────────────────────────────────
    function getDPRSource() {
        const activeTab = document.querySelector('.tab-btn.active');
        return activeTab ? activeTab.dataset.tab : 'folder';
    }

    function switchDPRSource(tab) {
        document.querySelectorAll('.tab-btn').forEach(b => b.classList.toggle('active', b.dataset.tab === tab));
        document.getElementById('dpr-tab-folder').style.display = tab === 'folder' ? 'block' : 'none';
        document.getElementById('dpr-tab-upload').style.display = tab === 'upload' ? 'block' : 'none';
    }

    // ── File Upload ────────────────────────────────────────────────
    function setupFileDropzone() {
        const dz = document.getElementById('file-dropzone');
        if (!dz) return;

        dz.addEventListener('dragover', e => { e.preventDefault(); dz.classList.add('drag-over'); });
        dz.addEventListener('dragleave', () => dz.classList.remove('drag-over'));
        dz.addEventListener('drop', e => {
            e.preventDefault();
            dz.classList.remove('drag-over');
            if (e.dataTransfer.files.length) handleFileUpload(e.dataTransfer.files);
        });
    }

    async function handleFileUpload(files) {
        const list = document.getElementById('upload-list');
        for (const file of files) {
            const item = { id: null, name: file.name, size: file.size, status: 'uploading' };
            uploadedFiles.push(item);
            renderUploadList();

            const formData = new FormData();
            formData.append('file', file);

            try {
                const res = await fetch('/api/files/single', { method: 'POST', body: formData });
                const data = await res.json();
                if (res.ok) {
                    item.id = data.id || data.filename;
                    item.status = 'success';
                    toast(`Uploaded: ${file.name}`, 'success');
                } else {
                    item.status = 'error';
                    toast(`Upload failed: ${file.name}`, 'error');
                }
            } catch (e) {
                item.status = 'error';
                toast(`Upload error: ${file.name}`, 'error');
            }
            renderUploadList();
        }
    }

    function renderUploadList() {
        const list = document.getElementById('upload-list');
        if (!list) return;
        list.innerHTML = uploadedFiles.map((f, i) => `
            <div class="upload-item">
                <span class="file-name">${f.name}</span>
                <span class="file-size">${formatSize(f.size)}</span>
                <span class="upload-status ${f.status}">${f.status === 'success' ? '✓' : f.status === 'uploading' ? '⏳' : '✗'}</span>
                <button class="btn-remove" onclick="App.removeUpload(${i})" title="Remove">✕</button>
            </div>
        `).join('');
    }

    function removeUpload(index) {
        uploadedFiles.splice(index, 1);
        renderUploadList();
    }

    // ── History ────────────────────────────────────────────────────
    let historyData = [];

    async function loadHistory() {
        try {
            const res = await fetch('/api/extractions');
            historyData = await res.json();
            renderHistory();

            // Update badge
            const badge = document.getElementById('badge-history');
            if (badge) {
                badge.textContent = historyData.length;
                badge.style.display = historyData.length ? '' : 'none';
            }
        } catch (e) {
            toast('Failed to load history', 'error');
        }
    }

    function renderHistory() {
        const tbody = document.getElementById('history-tbody');
        if (!tbody) return;

        if (!historyData.length) {
            tbody.innerHTML = '<tr><td colspan="8" class="empty-row">No saved extractions</td></tr>';
            return;
        }

        tbody.innerHTML = historyData.map((h, i) => {
            const d = new Date(h.created_at);
            const dateStr = d.toLocaleDateString() + ' ' + d.toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'});
            const typeLabel = (h.report_type || '').replace('_', ' ');
            return `<tr data-id="${h.id}">
                <td><input type="checkbox" class="history-check" data-id="${h.id}" onchange="App.onHistoryCheck()"></td>
                <td class="history-label" title="Double-click to rename" ondblclick="App.renameHistory('${h.id}')">${h.label || h.id}</td>
                <td><span class="chip chip-active">${typeLabel}</span></td>
                <td>${h.dc_count || 0}</td>
                <td>${h.dw_count || 0}</td>
                <td><strong>${h.record_count}</strong></td>
                <td style="font-size:0.85em;opacity:0.8">${dateStr}</td>
                <td>
                    <button class="btn btn-sm btn-primary" onclick="App.loadSavedExtraction('${h.id}')" title="Load">📂</button>
                    <button class="btn btn-sm btn-outline" onclick="App.renameHistory('${h.id}')" title="Rename">✏️</button>
                    <button class="btn btn-sm btn-danger" onclick="App.deleteHistory('${h.id}')" title="Delete">🗑️</button>
                </td>
            </tr>`;
        }).join('');
    }

    async function loadSavedExtraction(id) {
        setLoading(true);
        try {
            const res = await fetch(`/api/extractions/${id}`);
            if (!res.ok) throw new Error('Not found');
            const data = await res.json();

            currentExtractionId = data.id;

            // Let populateOutputPages handle extractionData via renderOutputTable
            // (do NOT set extractionData directly — it must be {rows, cols} objects)
            populateOutputPages(data, data.report_type);
            toast(`Loaded extraction: ${data.record_count} records`, 'success');

            // Enable pipeline buttons
            const btnCorrect = document.getElementById('btn-correct');
            const btnConvert = document.getElementById('btn-convert');
            const btnExport = document.getElementById('btn-export');
            if (btnCorrect) btnCorrect.disabled = false;
            if (btnConvert) btnConvert.disabled = false;
            if (btnExport) btnExport.disabled = false;

            // Navigate to DC page
            goTo('output-dc');
        } catch (e) {
            toast('Failed to load extraction: ' + e.message, 'error');
        } finally {
            setLoading(false);
        }
    }

    async function deleteHistory(id) {
        if (!confirm('Delete this extraction permanently?')) return;
        try {
            const res = await fetch(`/api/extractions/${id}`, { method: 'DELETE' });
            if (!res.ok) throw new Error('Delete failed');
            toast('Extraction deleted', 'success');

            // If it was the active extraction, clear it
            if (currentExtractionId === id) {
                clearExtraction();
            }
            loadHistory();
        } catch (e) {
            toast('Delete failed: ' + e.message, 'error');
        }
    }

    async function renameHistory(id) {
        const current = historyData.find(h => h.id === id);
        const newLabel = prompt('Enter a new label:', current?.label || id);
        if (!newLabel || newLabel === current?.label) return;
        try {
            const res = await fetch(`/api/extractions/${id}?label=${encodeURIComponent(newLabel)}`, { method: 'PATCH' });
            if (!res.ok) throw new Error('Rename failed');
            toast('Renamed', 'success');
            loadHistory();
        } catch (e) {
            toast('Rename failed: ' + e.message, 'error');
        }
    }

    function onHistoryCheck() {
        const checked = document.querySelectorAll('.history-check:checked');
        const btn = document.getElementById('btn-compare-selected');
        if (btn) btn.disabled = checked.length !== 2;
    }

    function toggleAllHistory(checked) {
        document.querySelectorAll('.history-check').forEach(cb => cb.checked = checked);
        onHistoryCheck();
    }

    async function compareSelected() {
        const checked = document.querySelectorAll('.history-check:checked');
        if (checked.length !== 2) {
            toast('Select exactly 2 extractions to compare', 'warning');
            return;
        }
        const id1 = checked[0].dataset.id;
        const id2 = checked[1].dataset.id;

        try {
            const res = await fetch(`/api/extractions/${id1}/compare/${id2}`);
            if (!res.ok) throw new Error('Compare failed');
            const data = await res.json();
            renderCompare(data);
        } catch (e) {
            toast('Compare failed: ' + e.message, 'error');
        }
    }

    function renderCompare(data) {
        const panel = document.getElementById('compare-panel');
        const body = document.getElementById('compare-body');
        const title = document.getElementById('compare-title');
        if (!panel || !body) return;

        title.textContent = `⚖️ ${data.extraction_1.label || data.extraction_1.id} vs ${data.extraction_2.label || data.extraction_2.id}`;

        const types = ['dc', 'dw', 'mc', 'wt'];
        let html = '<div style="padding:16px">';

        // Summary cards
        html += '<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:16px">';
        for (const t of types) {
            const d = data[t];
            if (!d) continue;
            const hasChanges = d.added || d.removed || d.changed;
            html += `<div class="stat-card" style="text-align:center">
                <div style="font-weight:600;text-transform:uppercase;margin-bottom:8px">${t}</div>
                <div>${d.count_1} → ${d.count_2} rows</div>
                ${hasChanges ? `<div style="margin-top:4px;font-size:0.85em">
                    ${d.added ? `<span style="color:var(--success)">+${d.added}</span> ` : ''}
                    ${d.removed ? `<span style="color:var(--danger)">-${d.removed}</span> ` : ''}
                    ${d.changed ? `<span style="color:var(--warning)">~${d.changed}</span>` : ''}
                </div>` : '<div style="margin-top:4px;color:var(--success);font-size:0.85em">No changes</div>'}
            </div>`;
        }
        html += '</div>';

        // Diff details
        for (const t of types) {
            const d = data[t];
            if (!d || !d.diffs || !d.diffs.length) continue;
            html += `<h4 style="margin:12px 0 8px">${t.toUpperCase()} — Changed Rows</h4>`;
            html += '<table class="data-table" style="font-size:0.85em"><thead><tr><th>Row</th><th>Field</th><th>Old</th><th>New</th></tr></thead><tbody>';
            for (const diff of d.diffs) {
                for (const [field, vals] of Object.entries(diff.fields)) {
                    html += `<tr>
                        <td>${diff.row}</td>
                        <td><code>${field}</code></td>
                        <td style="color:var(--danger)">${vals.old ?? ''}</td>
                        <td style="color:var(--success)">${vals.new ?? ''}</td>
                    </tr>`;
                }
            }
            html += '</tbody></table>';
        }

        html += '</div>';
        body.innerHTML = html;
        panel.style.display = '';
    }

    // ══════════════════════════════════════════════════════════════════
    // RECORD DETAIL OVERLAY — fullscreen detail view for a single row
    // ══════════════════════════════════════════════════════════════════

    // Category definitions for grouping fields
    const FIELD_CATEGORIES = {
        dc: [
            { key: 'identity', label: 'Identification', codes: ['DC001','DC002','DC003','DC004'] },
            { key: 'gas_prod', label: 'Gas Production', codes: ['DC005','DC006'] },
            { key: 'gas_exp', label: 'Gas Expédié / Vendu', codes: ['DC007','DC008','DC009','DC010','DC011','DC012','DC013','DC014','DC015','DC016','DC017','DC018','DC019','DC020'] },
            { key: 'gas_other', label: 'Gas Torché, Fuel & Injection', codes: ['DC021','DC022','DC023','DC052','DC053'] },
            { key: 'pcs', label: 'PCS & Wobbe', codes: ['DC024','DC025','DC026','DC027'] },
            { key: 'oil', label: 'Oil / Huile', codes: ['DC028','DC029','DC030'] },
            { key: 'gpl', label: 'GPL', codes: ['DC031','DC032','DC033'] },
            { key: 'butane', label: 'Butane', codes: ['DC034','DC035','DC036'] },
            { key: 'propane', label: 'Propane', codes: ['DC037','DC038','DC039'] },
            { key: 'pentane', label: 'Pentane', codes: ['DC040','DC041','DC042'] },
            { key: 'water', label: 'Water / Eau', codes: ['DC043','DC044','DC045','DC046'] },
            { key: 'condensat', label: 'Condensat', codes: ['DC047','DC048','DC049','DC050'] },
            { key: 'co2', label: 'CO2', codes: ['DC051'] },
        ],
        dw: [
            { key: 'identity', label: 'Identification', codes: ['DW001','DW002','DW003','DW004','DW005','DW006'] },
            { key: 'production', label: 'Production', codes: ['DW007','DW008','DW009','DW010','DW011','DW012','DW013'] },
            { key: 'pressure', label: 'Pressure & Temperature', codes: ['DW014','DW015','DW016','DW017','DW018','DW019','DW020','DW021'] },
            { key: 'activation', label: 'Activation', codes: ['DW022','DW023','DW024','DW025','DW026','DW027','DW028'] },
            { key: 'remarks', label: 'Remarks', codes: ['DW029','DW030'] },
        ],
        mc: [
            { key: 'identity', label: 'Identification', codes: ['MC001','MC002','MC003','MC004'] },
            { key: 'gas_prod', label: 'Gas Production', codes: ['MC005','MC006'] },
            { key: 'gas_sold', label: 'Gas Vendu', codes: ['MC007','MC008','MC009','MC010','MC011','MC012','MC013','MC014','MC015','MC016','MC017','MC018','MC019','MC020'] },
            { key: 'gas_other', label: 'Gas Torché, Fuel & Injection', codes: ['MC021','MC022','MC023','MC054'] },
            { key: 'pcs', label: 'PCS & Wobbe', codes: ['MC024','MC025','MC026','MC027','MC052','MC053'] },
            { key: 'oil', label: 'Oil / Huile', codes: ['MC028','MC029','MC030'] },
            { key: 'gpl', label: 'GPL', codes: ['MC031','MC032','MC033'] },
            { key: 'butane', label: 'Butane', codes: ['MC034','MC035','MC036'] },
            { key: 'propane', label: 'Propane', codes: ['MC037','MC038','MC039'] },
            { key: 'pentane', label: 'Pentane', codes: ['MC040','MC041','MC042'] },
            { key: 'water', label: 'Water / Eau', codes: ['MC043','MC044','MC045','MC046'] },
            { key: 'condensat', label: 'Condensat', codes: ['MC047','MC048','MC049','MC050'] },
            { key: 'co2', label: 'CO2', codes: ['MC051'] },
        ],
        wt: [
            { key: 'identity', label: 'Identification', codes: ['WT001','WT002','WT003','WT004','WT005','WT006','WT007','WT008','WT009','WT010'] },
            { key: 'production', label: 'Production & Injection', codes: ['WT011','WT012','WT013','WT014','WT015','WT016'] },
            { key: 'rates', label: 'Rates', codes: ['WT017','WT018','WT019','WT020','WT021'] },
            { key: 'gas_lift', label: 'Gas Lift', codes: ['WT022','WT023'] },
            { key: 'pressure', label: 'Pressure & Temperature', codes: ['WT024','WT025','WT026','WT027','WT028','WT029','WT030','WT031','WT032','WT033'] },
            { key: 'reservoir', label: 'Reservoir & Fluid', codes: ['WT034','WT035','WT036','WT037','WT038','WT039','WT040','WT041','WT042','WT043','WT044'] },
            { key: 'perf', label: 'Performance', codes: ['WT045','WT046','WT047','WT048'] },
        ],
    };

    const TYPE_LABELS = { dc: 'Daily Concession', dw: 'Daily Well', mc: 'Monthly Concession', wt: 'Well Test' };

    function openRecordDetail(type, rowIndex) {
        const stored = extractionData[type];
        if (!stored || !stored.rows || rowIndex >= stored.rows.length) return;

        recordDetailState = { type, rowIndex };
        renderRecordDetail();

        const overlay = document.getElementById('record-overlay');
        overlay.style.display = '';

        // Close on Escape
        const escHandler = (e) => {
            if (e.key === 'Escape') {
                closeRecordDetail();
                document.removeEventListener('keydown', escHandler);
            }
        };
        document.addEventListener('keydown', escHandler);
    }

    function closeRecordDetail() {
        const overlay = document.getElementById('record-overlay');
        overlay.style.display = 'none';
        recordDetailState = null;
    }

    function navRecordDetail(delta) {
        if (!recordDetailState) return;
        const stored = extractionData[recordDetailState.type];
        if (!stored) return;
        const newIdx = recordDetailState.rowIndex + delta;
        if (newIdx < 0 || newIdx >= stored.rows.length) return;
        recordDetailState.rowIndex = newIdx;
        renderRecordDetail();
    }

    function renderRecordDetail() {
        if (!recordDetailState) return;
        const { type, rowIndex } = recordDetailState;
        const stored = extractionData[type];
        if (!stored) return;
        const row = stored.rows[rowIndex];
        const cols = stored.cols;

        // Title & badge
        const titleEl = document.getElementById('record-overlay-title');
        const badgeEl = document.getElementById('record-overlay-badge');
        const posEl = document.getElementById('record-overlay-pos');

        // Build a title from the identity fields
        const nameCol = cols.find(c => c.match(/^(DC001|DW001|MC001|WT001)$/));
        const nameVal = nameCol ? row[nameCol] : '';

        // Smart date column detection: first try known codes, then scan for actual date values
        let dateVal = '';
        const knownDateCols = ['DC002', 'MC002', 'WT005'];
        let dateCol = cols.find(c => knownDateCols.includes(c) && isDateValue(row[c]));
        if (!dateCol) {
            // Fallback: find any column with an actual date value
            dateCol = cols.find(c => isDateValue(row[c]));
        }
        if (dateCol) dateVal = formatCellValue(row[dateCol]);

        titleEl.textContent = nameVal ? `${nameVal}` : `Record #${rowIndex + 1}`;
        badgeEl.textContent = TYPE_LABELS[type] || type.toUpperCase();
        posEl.textContent = `${rowIndex + 1} / ${stored.rows.length}`;

        // Navigation buttons
        document.getElementById('record-nav-prev').disabled = rowIndex === 0;
        document.getElementById('record-nav-next').disabled = rowIndex === stored.rows.length - 1;

        // Build body
        const body = document.getElementById('record-overlay-body');
        let html = '';

        // Summary KPI strip
        const filledCount = cols.filter(c => {
            const v = row[c]; return v !== null && v !== undefined && v !== '';
        }).length;
        html += `<div class="record-summary-kpi">`;
        if (dateVal) html += `<div class="output-kpi"><div class="output-kpi-value" style="color:#6b5b95">${dateVal}</div><div class="output-kpi-label">Date</div></div>`;
        html += `<div class="output-kpi"><div class="output-kpi-value">${filledCount}</div><div class="output-kpi-label">Fields with Data</div></div>`;
        html += `<div class="output-kpi"><div class="output-kpi-value">${cols.length}</div><div class="output-kpi-label">Total Columns</div></div>`;
        html += `<div class="output-kpi"><div class="output-kpi-value">${cols.length > 0 ? Math.round((filledCount / cols.length) * 100) : 0}%</div><div class="output-kpi-label">Fill Rate</div></div>`;
        html += `</div>`;

        // Toggle for empty fields
        html += `<label class="record-toggle-empty" style="margin-bottom:12px"><input type="checkbox" id="record-show-empty" onchange="App.toggleRecordEmpty(this.checked)"> Show empty fields</label>`;

        // Group by categories
        const categories = FIELD_CATEGORIES[type];
        if (categories) {
            const usedCodes = new Set();
            for (const cat of categories) {
                const fields = cat.codes.filter(c => cols.includes(c));
                if (fields.length === 0) continue;

                const filledFields = fields.filter(c => {
                    const v = row[c]; return v !== null && v !== undefined && v !== '';
                });

                // Skip categories with no data (unless showing empty)
                html += `<div class="record-section" data-has-data="${filledFields.length > 0}">`;
                html += `<div class="record-section-title">${cat.label} <span style="font-weight:400;color:var(--text-muted)">(${filledFields.length}/${fields.length})</span></div>`;
                html += `<div class="record-fields">`;

                for (const code of fields) {
                    usedCodes.add(code);
                    const v = row[code];
                    const attrName = attributeMap[code] || code;
                    const isEmpty = v === null || v === undefined || v === '';
                    const valClass = isEmpty ? 'val-empty'
                        : typeof v === 'number' ? 'val-num'
                        : isDateValue(v) ? 'val-date'
                        : String(v).length > 60 ? 'val-text val-long'
                        : 'val-text';
                    const displayVal = isEmpty ? '—' : formatCellValue(v);

                    html += `<div class="record-field${isEmpty ? ' record-field-empty' : ''}">`;
                    html += `<div class="record-field-label">${attrName} <span class="record-field-code">${code}</span></div>`;
                    html += `<div class="record-field-value ${valClass}">${displayVal}</div>`;
                    html += `</div>`;
                }
                html += `</div></div>`;
            }

            // Any uncategorized columns
            const uncategorized = cols.filter(c => !usedCodes.has(c));
            if (uncategorized.length > 0) {
                const filledUncat = uncategorized.filter(c => {
                    const v = row[c]; return v !== null && v !== undefined && v !== '';
                });
                html += `<div class="record-section" data-has-data="${filledUncat.length > 0}">`;
                html += `<div class="record-section-title">Other Fields <span style="font-weight:400;color:var(--text-muted)">(${filledUncat.length}/${uncategorized.length})</span></div>`;
                html += `<div class="record-fields">`;
                for (const code of uncategorized) {
                    const v = row[code];
                    const attrName = attributeMap[code] || code;
                    const isEmpty = v === null || v === undefined || v === '';
                    const valClass = isEmpty ? 'val-empty' : typeof v === 'number' ? 'val-num' : isDateValue(v) ? 'val-date' : 'val-text';
                    const displayVal = isEmpty ? '—' : formatCellValue(v);
                    html += `<div class="record-field${isEmpty ? ' record-field-empty' : ''}">`;
                    html += `<div class="record-field-label">${attrName} <span class="record-field-code">${code}</span></div>`;
                    html += `<div class="record-field-value ${valClass}">${displayVal}</div>`;
                    html += `</div>`;
                }
                html += `</div></div>`;
            }
        } else {
            // No categories defined — show all fields in a single grid
            html += `<div class="record-section"><div class="record-fields">`;
            for (const code of cols) {
                const v = row[code];
                const attrName = attributeMap[code] || code;
                const isEmpty = v === null || v === undefined || v === '';
                const valClass = isEmpty ? 'val-empty' : typeof v === 'number' ? 'val-num' : 'val-text';
                const displayVal = isEmpty ? '—' : formatCellValue(v);
                html += `<div class="record-field${isEmpty ? ' record-field-empty' : ''}">`;
                html += `<div class="record-field-label">${attrName} <span class="record-field-code">${code}</span></div>`;
                html += `<div class="record-field-value ${valClass}">${displayVal}</div>`;
                html += `</div>`;
            }
            html += `</div></div>`;
        }

        body.innerHTML = html;

        // Default: hide empty fields
        toggleRecordEmpty(false);
    }

    function toggleRecordEmpty(show) {
        const overlay = document.getElementById('record-overlay-body');
        if (!overlay) return;
        const emptyFields = overlay.querySelectorAll('.record-field-empty');
        emptyFields.forEach(f => f.style.display = show ? '' : 'none');

        // Hide sections that have no visible fields
        const sections = overlay.querySelectorAll('.record-section');
        sections.forEach(sec => {
            if (!show && sec.getAttribute('data-has-data') === 'false') {
                sec.style.display = 'none';
            } else {
                sec.style.display = '';
            }
        });
    }

    // ── Boot ───────────────────────────────────────────────────────
    document.addEventListener('DOMContentLoaded', init);

    return {
        goTo, extract, autoCorrect, convertUnits, exportCSV, exportType, exportPDF,
        savePaths, refreshDashboard, clearLogs,
        onReportChange, onDateModeChange, onMultipleChange,
        prepareFiles, clearExtraction,
        toggleChip, toggleAllConcessions, switchDPRSource,
        handleFileUpload, removeUpload,
        filterOutputTable, toggleOutputCompact,
        // CRUD operations
        addRecord, deleteRecord, bulkDeleteRecords, cleanEmptyRows,
        undoRecord, redoRecord,
        toggleRowSelect, toggleSelectAll,
        // Record detail
        openRecordDetail, closeRecordDetail, navRecordDetail, toggleRecordEmpty,
        // History operations
        loadHistory, loadSavedExtraction, deleteHistory, renameHistory,
        onHistoryCheck, toggleAllHistory, compareSelected,
    };
})();
