/**
 * Schema Explorer Page Script
 * 7 tabs: ER, Tables, Relationships, Constraints, Triggers, DDL, SQL Console
 */

import { get, post, handle } from '../api.js';
import { renderTable, showEmptyState, escapeHtml } from '../tables.js';
import { openInspector } from '../inspector.js';

let schemaData = {
    tables: [],
    relationships: [],
    constraints: [],
    indexes: [],
    triggers: [],
    functions: [],
    violations: [],
    er: null,
    ddl: null
};

export async function loadSchema() {
    initMermaid();
    setupTabs();
    await fetchSchemaOverview();
    await fetchER();
}

function initMermaid() {
    if (window.mermaid) {
        window.mermaid.initialize({
            startOnLoad: false,
            theme: 'default',
            securityLevel: 'loose',
            flowchart: { useMaxWidth: true, htmlLabels: true }
        });
    }
}

function setupTabs() {
    const tabEl = document.getElementById('schemaTabs');
    if (!tabEl) return;

    // Lazy load tab content
    tabEl.addEventListener('shown.bs.tab', async (e) => {
        const target = e.target.getAttribute('data-bs-target');
        if (target === '#tabTables' && schemaData.tables.length === 0) await fetchTables();
        if (target === '#tabRelationships' && schemaData.relationships.length === 0) await fetchRelationships();
        if (target === '#tabConstraints' && schemaData.constraints.length === 0) await fetchConstraints();
        if (target === '#tabTriggers' && schemaData.triggers.length === 0) await fetchTriggers();
        if (target === '#tabDDL' && !schemaData.ddl) await fetchDDL();
    });
}

async function fetchSchemaOverview() {
    const envelope = await get('/schema/overview');
    handle(envelope, { successToast: false, errorToast: true });
}

async function fetchER() {
    const envelope = await get('/schema/er');
    handle(envelope, {
        successToast: false,
        errorToast: true,
        onSuccess: (env) => {
            schemaData.er = env.data?.mermaid;
            renderERDiagram();
        }
    });
}

function renderERDiagram() {
    const staticEl = document.getElementById('liveERDiagram');
    if (staticEl && schemaData.er) {
        staticEl.textContent = schemaData.er;
        if (window.mermaid) {
            window.mermaid.run({ nodes: [staticEl] }).catch(console.error);
        }
    }
}

async function fetchTables() {
    const envelope = await get('/schema/tables');
    handle(envelope, {
        successToast: false,
        errorToast: true,
        onSuccess: (env) => {
            schemaData.tables = env.data || [];
            renderTableList();
        }
    });
}

function renderTableList() {
    const container = document.getElementById('tableList');
    if (!container) return;

    if (!schemaData.tables.length) {
        container.innerHTML = '<div class="text-center p-3 text-muted">No tables found</div>';
        return;
    }

    let html = '';
    schemaData.tables.forEach(table => {
        html += `
            <button class="list-group-item list-group-item-action d-flex justify-content-between align-items-center table-list-item" data-table="${table.name}">
                <span>${table.name}</span>
                <span class="badge bg-secondary">${table.rows} rows, ${table.columns} cols</span>
            </button>
        `;
    });
    container.innerHTML = html;

    container.querySelectorAll('.table-list-item').forEach(btn => {
        btn.addEventListener('click', () => loadTableDetails(btn.dataset.table));
    });

    // Load first table by default
    if (schemaData.tables[0]) {
        loadTableDetails(schemaData.tables[0].name);
    }
}

async function loadTableDetails(tableName) {
    const nameEl = document.getElementById('selectedTableName');
    const detailsEl = document.getElementById('tableDetails');
    if (!nameEl || !detailsEl) return;

    nameEl.textContent = tableName;
    detailsEl.innerHTML = '<div class="text-center py-3"><div class="spinner-border"></div></div>';

    // Update active state
    document.querySelectorAll('.table-list-item').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.table === tableName);
    });

    const envelope = await get(`/schema/tables/${encodeURIComponent(tableName)}?preview=10`);
    handle(envelope, {
        successToast: false,
        errorToast: true,
        onSuccess: (env) => renderTableDetails(env.data, tableName)
    });
}

function renderTableDetails(data, tableName) {
    const detailsEl = document.getElementById('tableDetails');
    if (!detailsEl) return;

    const columns = data.columns || [];
    const preview = data.preview || { columns: [], rows: [] };

    let html = `
        <div class="mb-3">
            <h6>Columns (${columns.length})</h6>
            <div class="table-responsive">
                <table class="table table-sm table-bordered">
                    <thead><tr><th>Name</th><th>Type</th><th>PK</th><th>Not Null</th><th>Default</th><th>Unique</th><th>FK</th><th>Checks</th></tr></thead>
                    <tbody>
    `;

    columns.forEach(col => {
        const badges = [];
        if (col.pk) badges.push('<span class="badge bg-primary">PK</span>');
        if (col.notnull) badges.push('<span class="badge bg-secondary">NOT NULL</span>');
        if (col.unique) badges.push('<span class="badge bg-info text-dark">UNIQUE</span>');
        if (col.fk) badges.push('<span class="badge bg-warning text-dark">FK</span>');
        if (col.checks?.length) badges.push('<span class="badge bg-danger">CHECK</span>');
        if (col.default !== null && col.default !== undefined) badges.push(`<span class="badge bg-light text-dark">DEFAULT: ${col.default}</span>`);

        html += `
            <tr>
                <td><strong>${col.name}</strong></td>
                <td><code>${col.type}</code></td>
                <td>${col.pk ? '<i class="bi bi-check text-success"></i>' : ''}</td>
                <td>${col.notnull ? '<i class="bi bi-check text-success"></i>' : ''}</td>
                <td>${col.default !== null && col.default !== undefined ? `<code>${col.default}</code>` : ''}</td>
                <td>${col.unique ? '<i class="bi bi-check text-success"></i>' : ''}</td>
                <td>${col.fk ? `<code>${col.fk}</code>` : ''}</td>
                <td>${col.checks?.join(', ') || ''}</td>
            </tr>
        `;
    });

    html += '</tbody></table></div></div>';

    // Preview
    if (preview.columns?.length && preview.rows?.length) {
        html += `
            <div class="mb-3">
                <h6>Data Preview (${preview.rows.length} rows)</h6>
                <div class="table-responsive">
                    <table class="table table-sm table-bordered">
                        <thead><tr>${preview.columns.map(c => `<th>${c}</th>`).join('')}</tr></thead>
                        <tbody>
        `;
        preview.rows.forEach(row => {
            html += '<tr>' + row.map(cell => `<td>${cell === null ? '<span class="text-muted">—</span>' : escapeHtml(String(cell))}</td>`).join('') + '</tr>';
        });
        html += '</tbody></table></div></div>';
    } else {
        html += '<p class="text-muted">No preview data available</p>';
    }

    detailsEl.innerHTML = html;
}

async function fetchRelationships() {
    const envelope = await get('/schema/relationships');
    handle(envelope, {
        successToast: false,
        errorToast: true,
        onSuccess: (env) => {
            schemaData.relationships = env.data || [];
            renderRelationships();
            renderRelationshipER();
        }
    });
}

function renderRelationships() {
    const container = document.getElementById('relationshipsTable');
    if (!container) return;

    if (!schemaData.relationships.length) {
        showEmptyState(container, 'No relationships found');
        return;
    }

    renderTable(container, [
        { key: 'from_table', label: 'From Table' },
        { key: 'from_col', label: 'From Column' },
        { key: 'to_table', label: 'To Table' },
        { key: 'to_col', label: 'To Column' },
        { key: 'cardinality', label: 'Cardinality' },
        { key: 'note', label: 'Note' }
    ], schemaData.relationships, { csvExport: true, csvFilename: 'relationships.csv' });
}

function renderRelationshipER() {
    const el = document.getElementById('relationshipER');
    if (!el || !window.mermaid) return;

    let mermaid = 'erDiagram\n';
    schemaData.relationships.forEach(r => {
        const card = r.cardinality || '1:N';
        mermaid += `    ${r.from_table} ||--o{ ${r.to_table} : "${r.from_col} -> ${r.to_col}"\n`;
    });
    el.textContent = mermaid;
    window.mermaid.run({ nodes: [el] }).catch(console.error);
}

async function fetchConstraints() {
    const [constraintsEnv, indexesEnv, violationsEnv] = await Promise.all([
        get('/schema/constraints'),
        get('/schema/indexes'),
        get('/schema/violations')
    ]);

    handle(constraintsEnv, { successToast: false, errorToast: true, onSuccess: (env) => schemaData.constraints = env.data || [] });
    handle(indexesEnv, { successToast: false, errorToast: true, onSuccess: (env) => schemaData.indexes = env.data || [] });
    handle(violationsEnv, { successToast: false, errorToast: true, onSuccess: (env) => {
        schemaData.violations = env.data || [];
        renderConstraints();
        renderIndexes();
        renderViolations();
    }});
}

function renderConstraints() {
    const container = document.getElementById('constraintsTable');
    if (!container) return;

    renderTable(container, [
        { key: 'table', label: 'Table' },
        { key: 'name', label: 'Constraint Name' },
        { key: 'type', label: 'Type' },
        { key: 'rule', label: 'Rule' },
        { key: 'expression', label: 'Expression' }
    ], schemaData.constraints, { csvExport: true, csvFilename: 'constraints.csv' });
}

function renderIndexes() {
    const container = document.getElementById('indexesTable');
    if (!container) return;

    renderTable(container, [
        { key: 'name', label: 'Index Name' },
        { key: 'table', label: 'Table' },
        { key: 'unique', label: 'Unique', align: 'center', formatter: 'bool' },
        { key: 'partial_where', label: 'Partial Where' },
        { key: 'purpose', label: 'Purpose' }
    ], schemaData.indexes, {
        csvExport: true,
        csvFilename: 'indexes.csv',
        formatters: { bool: (v) => v ? '<i class="bi bi-check text-success"></i>' : '<i class="bi bi-x text-danger"></i>' }
    });
}

function renderViolations() {
    const container = document.getElementById('violationsTable');
    if (!container) return;

    if (!schemaData.violations.length) {
        showEmptyState(container, 'No violation tests defined');
        return;
    }

    renderTable(container, [
        { key: 'id', label: 'ID', width: '70px' },
        { key: 'title', label: 'Test' },
        { key: 'rule', label: 'Rule' },
        { key: 'enforced_by', label: 'Enforced By' },
        { key: 'sql', label: 'Test SQL', formatter: 'sql' },
        { key: 'actions', label: 'Action', width: '120px', formatter: 'actions' }
    ], schemaData.violations, {
        csvExport: false,
        formatters: {
            sql: (v) => `<code class="small">${v}</code>`,
            actions: (v, row) => `
                <button class="btn btn-sm btn-outline-danger run-violation" data-id="${row.id}" title="Run violation test">
                    <i class="bi bi-play"></i> Run
                </button>
            `
        }
    });

    document.querySelectorAll('.run-violation').forEach(btn => {
        btn.addEventListener('click', () => runViolation(btn.dataset.id));
    });

    // Run All button
    const runAllBtn = document.getElementById('runAllViolationsBtn');
    if (runAllBtn) {
        runAllBtn.onclick = runAllViolations;
    }
}

async function runViolation(violationId) {
    const btn = document.querySelector(`.run-violation[data-id="${violationId}"]`);
    if (btn) { btn.disabled = true; btn.innerHTML = '<span class="spinner-border spinner-border-sm"></span>'; }

    const envelope = await post(`/schema/violations/${violationId}/run`, {});
    handle(envelope, {
        successToast: true,
        errorToast: true,
        inspectorEl: document.getElementById('inspectorBody'),
        onSuccess: (env) => {
            const data = env.data;
            if (data.blocked) {
                showToast(`✅ ${violationId} BLOCKED: ${data.error}`, 'success');
            } else {
                showToast(`⚠️ ${violationId} NOT BLOCKED!`, 'warning');
            }
        }
    });

    if (btn) { btn.disabled = false; btn.innerHTML = '<i class="bi bi-play"></i> Run'; }
}

async function runAllViolations() {
    const btn = document.getElementById('runAllViolationsBtn');
    if (btn) { btn.disabled = true; btn.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Running...'; }

    for (const v of schemaData.violations) {
        await runViolation(v.id);
        await sleep(300);
    }

    if (btn) { btn.disabled = false; btn.innerHTML = '<i class="bi bi-play-fill"></i> Run All 11 Violation Tests'; }
}

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

async function fetchTriggers() {
    const [triggersEnv, functionsEnv] = await Promise.all([
        get('/schema/triggers'),
        get('/schema/functions')
    ]);

    handle(triggersEnv, { successToast: false, errorToast: true, onSuccess: (env) => {
        schemaData.triggers = env.data || [];
        renderTriggers();
    }});
    handle(functionsEnv, { successToast: false, errorToast: true, onSuccess: (env) => {
        schemaData.functions = env.data || [];
        renderFunctions();
    }});
}

function renderTriggers() {
    const container = document.getElementById('triggersList');
    if (!container) return;

    if (!schemaData.triggers.length) {
        container.innerHTML = '<p class="text-muted">No triggers found</p>';
        return;
    }

    let html = '';
    schemaData.triggers.forEach(trigger => {
        const physical = trigger.physical || [];
        html += `
            <div class="card mb-2">
                <div class="card-header d-flex justify-content-between align-items-center">
                    <div>
                        <strong>${trigger.logical_name}</strong>
                        <span class="badge bg-secondary ms-2">${trigger.timing} ${trigger.events?.join(', ')}</span>
                        <span class="badge bg-info text-dark ms-2">${trigger.table}</span>
                    </div>
                    <button class="btn btn-sm btn-outline-primary run-trigger-demo" data-name="${trigger.logical_name}">
                        <i class="bi bi-play"></i> Demonstrate
                    </button>
                </div>
                <div class="card-body">
                    <p class="small text-muted mb-2">${trigger.purpose}</p>
                    <details>
                        <summary class="small text-muted">Physical Triggers (${physical.length})</summary>
                        <ul class="small mt-1">
                            ${physical.map(p => `<li><code>${p}</code></li>`).join('')}
                        </ul>
                    </details>
                    <details class="mt-2">
                        <summary class="small text-muted">SQL</summary>
                        <pre class="sql-block small mt-1">${trigger.sql}</pre>
                    </details>
                </div>
            </div>
        `;
    });
    container.innerHTML = html;

    document.querySelectorAll('.run-trigger-demo').forEach(btn => {
        btn.addEventListener('click', () => runTriggerDemo(btn.dataset.name));
    });
}

async function runTriggerDemo(logicalName) {
    const btn = document.querySelector(`.run-trigger-demo[data-name="${logicalName}"]`);
    if (btn) { btn.disabled = true; btn.innerHTML = '<span class="spinner-border spinner-border-sm"></span>'; }

    const envelope = await post(`/schema/triggers/${encodeURIComponent(logicalName)}/demo`, {});
    handle(envelope, {
        successToast: true,
        errorToast: true,
        inspectorEl: document.getElementById('inspectorBody'),
        onSuccess: () => {}
    });

    if (btn) { btn.disabled = false; btn.innerHTML = '<i class="bi bi-play"></i> Demonstrate'; }
}

function renderFunctions() {
    const container = document.getElementById('functionsList');
    if (!container) return;

    if (!schemaData.functions.length) {
        container.innerHTML = '<p class="text-muted">No functions found</p>';
        return;
    }

    let html = '';
    schemaData.functions.forEach(fn => {
        html += `
            <div class="card mb-2">
                <div class="card-body p-2">
                    <strong>${fn.name}</strong> <code class="small">${fn.signature}</code>
                    <div class="small text-muted">${fn.purpose}</div>
                    ${fn.oracle_equivalent ? `<div class="small text-info">Oracle: ${fn.oracle_equivalent}</div>` : ''}
                </div>
            </div>
        `;
    });
    container.innerHTML = html;
}

async function fetchDDL() {
    const envelope = await get('/schema/ddl');
    handle(envelope, {
        successToast: false,
        errorToast: true,
        onSuccess: (env) => {
            schemaData.ddl = env.data?.ddl;
            renderDDL();
        }
    });
}

function renderDDL() {
    const container = document.getElementById('ddlContent');
    if (!container) return;

    container.textContent = schemaData.ddl || 'No DDL available';

    const copyBtn = document.getElementById('copyDdlBtn');
    if (copyBtn) {
        copyBtn.onclick = () => {
            navigator.clipboard.writeText(schemaData.ddl || '').then(() => {
                copyBtn.innerHTML = '<i class="bi bi-check"></i> Copied!';
                setTimeout(() => copyBtn.innerHTML = '<i class="bi bi-clipboard"></i> Copy', 2000);
            });
        };
    }
}

// SQL Console
document.addEventListener('DOMContentLoaded', () => {
    const runBtn = document.getElementById('runSqlBtn');
    const clearBtn = document.getElementById('clearSqlBtn');
    const sqlInput = document.getElementById('sqlInput');
    const samplesSelect = document.getElementById('sqlSamples');

    if (runBtn) runBtn.addEventListener('click', runSQL);
    if (clearBtn) clearBtn.addEventListener('click', () => { sqlInput.value = ''; });
    if (sqlInput) {
        sqlInput.addEventListener('keydown', (e) => {
            if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') runSQL();
        });
    }
    if (samplesSelect) {
        samplesSelect.addEventListener('change', async (e) => {
            const reportId = e.target.value;
            if (!reportId) return;
            const envelope = await get(`/reports/${reportId}`);
            if (envelope.ok && envelope.data?.sql) {
                sqlInput.value = envelope.data.sql;
            }
            e.target.value = '';
        });
    }
});

async function runSQL() {
    const sqlInput = document.getElementById('sqlInput');
    const resultsContainer = document.getElementById('sqlResultsContainer');
    const sql = sqlInput?.value?.trim();

    if (!sql) return showToast('Enter a SQL query', 'warning');
    if (!/^\s*(SELECT|WITH)\s/i.test(sql)) return showToast('Only SELECT/WITH queries allowed', 'danger');

    const runBtn = document.getElementById('runSqlBtn');
    runBtn.disabled = true;
    runBtn.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Running...';

    const envelope = await post('/sql', { sql });
    handle(envelope, {
        successToast: true,
        errorToast: true,
        onSuccess: (env) => {
            const data = env.data;
            if (!data) return;

            let html = `
                <div class="mb-2">
                    <strong>Rows: ${data.row_count}</strong> | <strong>Time: ${data.elapsed_ms} ms</strong>
                </div>
            `;

            if (data.columns && data.rows.length) {
                html += '<div class="table-responsive"><table class="table table-sm table-bordered"><thead><tr>';
                data.columns.forEach(c => html += `<th>${c}</th>`);
                html += '</tr></thead><tbody>';
                data.rows.forEach(row => {
                    html += '<tr>' + row.map(cell => `<td>${cell === null ? '<span class="text-muted">—</span>' : escapeHtml(String(cell))}</td>`).join('') + '</tr>';
                });
                html += '</tbody></table></div>';
            } else {
                html += '<p class="text-muted">No results</p>';
            }

            resultsContainer.innerHTML = html;
        }
    });

    runBtn.disabled = false;
    runBtn.innerHTML = '<i class="bi bi-play"></i> Run (Ctrl+Enter)';
}

function showToast(msg, type) {
    if (window.toast) window.toast.show(msg, type);
}

window.pageRefresh = loadSchema;