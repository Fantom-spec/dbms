/**
 * Transaction Inspector Module
 * Renders the inspector panel with five-box viva header, tabs for SQL, triggers, before/after, raw JSON
 */

import { escapeHtml } from './tables.js';

const INSPECTOR_TEMPLATE = `
<div class="inspector-content">
    <!-- Five-box Viva Header -->
    <div class="viva-header mb-3" id="inspectorVivaHeader"></div>

    <!-- Tabs -->
    <ul class="nav nav-tabs inspector-tabs" id="inspectorTabs" role="tablist">
        <li class="nav-item" role="presentation">
            <button class="nav-link active" data-bs-toggle="tab" data-bs-target="#tabSQL" type="button" role="tab">
                <i class="bi bi-code"></i> SQL Executed
            </button>
        </li>
        <li class="nav-item" role="presentation">
            <button class="nav-link" data-bs-toggle="tab" data-bs-target="#tabTriggers" type="button" role="tab">
                <i class="bi bi-lightning"></i> Triggers & Functions
            </button>
        </li>
        <li class="nav-item" role="presentation">
            <button class="nav-link" data-bs-toggle="tab" data-bs-target="#tabBeforeAfter" type="button" role="tab">
                <i class="bi bi-arrow-left-right"></i> Before / After
            </button>
        </li>
        <li class="nav-item" role="presentation">
            <button class="nav-link" data-bs-toggle="tab" data-bs-target="#tabRaw" type="button" role="tab">
                <i class="bi bi-braces"></i> Raw JSON
            </button>
        </li>
    </ul>

    <div class="tab-content mt-3" id="inspectorTabContent">
        <!-- SQL Executed -->
        <div class="tab-pane fade show active" id="tabSQL" role="tabpanel">
            <div class="inspector-section">
                <div class="d-flex justify-content-between align-items-center mb-2">
                    <h6>SQL Statements</h6>
                    <button class="btn btn-sm btn-outline-secondary" id="copySqlBtn">
                        <i class="bi bi-clipboard"></i> Copy All
                    </button>
                </div>
                <pre class="sql-block" id="inspectorSql"></pre>
            </div>
        </div>

        <!-- Triggers & Functions -->
        <div class="tab-pane fade" id="tabTriggers" role="tabpanel">
            <div class="inspector-section">
                <h6>Triggers Fired</h6>
                <div id="inspectorTriggers"></div>
            </div>
            <div class="inspector-section">
                <h6>Functions Used</h6>
                <div id="inspectorFunctions"></div>
            </div>
        </div>

        <!-- Before / After -->
        <div class="tab-pane fade" id="tabBeforeAfter" role="tabpanel">
            <div id="inspectorBeforeAfter"></div>
        </div>

        <!-- Raw JSON -->
        <div class="tab-pane fade" id="tabRaw" role="tabpanel">
            <div class="inspector-section">
                <div class="d-flex justify-content-between align-items-center mb-2">
                    <h6>Full Inspector Object</h6>
                    <button class="btn btn-sm btn-outline-secondary" id="copyRawBtn">
                        <i class="bi bi-clipboard"></i> Copy
                    </button>
                </div>
                <pre class="sql-block" id="inspectorRawJson" style="max-height: 400px; overflow: auto;"></pre>
            </div>
        </div>
    </div>
</div>
`;

export function render(inspector, container) {
    if (!inspector || !container) return;

    // Clear container and inject template
    container.innerHTML = INSPECTOR_TEMPLATE;

    // Render Viva Header
    renderVivaHeader(inspector, container.querySelector('#inspectorVivaHeader'));

    // Render SQL tab
    renderSqlTab(inspector, container);

    // Render Triggers & Functions tab
    renderTriggersTab(inspector, container);

    // Render Before/After tab
    renderBeforeAfterTab(inspector, container);

    // Render Raw JSON tab
    renderRawJsonTab(inspector, container);

    // Setup copy buttons
    setupCopyButtons(container);
}

/**
 * Render the five-box viva header
 */
function renderVivaHeader(inspector, container) {
    const viva = inspector.viva || {};
    const component = inspector.component || {};
    const elapsed = inspector.elapsed_ms !== undefined ? `${inspector.elapsed_ms.toFixed(1)} ms` : 'N/A';

    const boxes = [
        { label: 'Operation', value: viva.operation || inspector.operation || 'Unknown' },
        { label: 'Tables', value: viva.tables || (inspector.tables ? inspector.tables.join(', ') : '—') },
        { label: 'Component', value: viva.component || `${component.name || 'Unknown'} (${component.type || 'unknown'})` },
        { label: 'DB Effect', value: viva.effect || '—' },
        { label: 'Result', value: viva.result || inspector.message || '—' }
    ];

    let html = '<div class="row g-2">';
    boxes.forEach(box => {
        html += `
            <div class="col-12 col-sm-6 col-md-4 col-lg-2">
                <div class="viva-box p-2 text-center h-100">
                    <div class="viva-label text-muted small text-uppercase fw-bold">${box.label}</div>
                    <div class="viva-value small">${escapeHtml(box.value)}</div>
                </div>
            </div>
        `;
    });
    html += '</div>';

    // Add component badge and elapsed time
    const componentType = component.type || 'unknown';
    const typeBadgeClass = getComponentTypeBadgeClass(componentType);

    html = `
        <div class="d-flex flex-wrap gap-2 mb-2">
            <span class="badge ${typeBadgeClass}">${componentType}</span>
            <span class="badge bg-secondary">${elapsed}</span>
            ${inspector.error ? '<span class="badge bg-danger">Error: ' + escapeHtml(inspector.error.code || 'Unknown') + '</span>' : ''}
        </div>
    ` + html;

    container.innerHTML = html;
}

function getComponentTypeBadgeClass(type) {
    const map = {
        procedure: 'bg-primary',
        function: 'bg-info',
        cursor: 'bg-warning text-dark',
        trigger: 'bg-danger',
        constraint: 'bg-secondary',
        query: 'bg-success',
        index: 'bg-dark'
    };
    return map[type] || 'bg-secondary';
}

/**
 * Render SQL Executed tab
 */
function renderSqlTab(inspector, container) {
    const sqlStatements = inspector.sql || [];
    const sqlEl = container.querySelector('#inspectorSql');

    if (sqlStatements.length === 0) {
        sqlEl.innerHTML = '<span class="text-muted">No SQL recorded</span>';
        return;
    }

    let html = '';
    sqlStatements.forEach((stmt, idx) => {
        const isTrigger = stmt.trim().startsWith('-- TRIGGER');
        const cls = isTrigger ? 'trigger-line' : '';
        html += `<div class="sql-line ${cls}" data-index="${idx}">${highlightSql(escapeHtml(stmt))}</div>`;
    });

    sqlEl.innerHTML = html;
}

/**
 * Basic SQL syntax highlighting
 */
function highlightSql(sql) {
    return sql
        .replace(/\b(SELECT|INSERT|UPDATE|DELETE|CREATE|DROP|ALTER|BEGIN|COMMIT|ROLLBACK|IMMEDIATE|INTO|VALUES|SET|WHERE|FROM|JOIN|ON|AND|OR|ORDER|BY|GROUP|LIMIT|OFFSET|DESC|ASC)\b/gi, '<span class="keyword">$1</span>')
        .replace(/-- TRIGGER .+$/, '<span class="trigger-line">$&</span>')
        .replace(/--.+$/, '<span class="comment">$&</span>');
}

/**
 * Render Triggers & Functions tab
 */
function renderTriggersTab(inspector, container) {
    // Triggers
    const triggers = inspector.triggers_fired || [];
    const triggersEl = container.querySelector('#inspectorTriggers');

    if (triggers.length === 0) {
        triggersEl.innerHTML = '<p class="text-muted small">No triggers fired</p>';
    } else {
        let html = '<div class="row g-2">';
        triggers.forEach(t => {
            html += `
                <div class="col-12">
                    <div class="card card-sm">
                        <div class="card-body p-2">
                            <div class="d-flex justify-content-between">
                                <strong class="small">${escapeHtml(t.name)}</strong>
                                <span class="badge bg-info text-dark small">${escapeHtml(t.event)}</span>
                            </div>
                            <div class="small text-muted">${escapeHtml(t.effect)}</div>
                            ${t.inferred ? '<div class="small text-info"><i class="bi bi-info-circle"></i> Inferred from row changes</div>' : ''}
                        </div>
                    </div>
                </div>
            `;
        });
        html += '</div>';
        triggersEl.innerHTML = html;
    }

    // Add note about trigger inference
    if (inspector.notes) {
        const notesEl = document.createElement('div');
        notesEl.className = 'mt-3 p-2 bg-light rounded';
        notesEl.innerHTML = `<small class="text-muted"><i class="bi bi-info-circle"></i> ${escapeHtml(inspector.notes)}</small>`;
        triggersEl.appendChild(notesEl);
    }

    // Functions
    const functions = inspector.functions_used || [];
    const functionsEl = container.querySelector('#inspectorFunctions');

    if (functions.length === 0) {
        functionsEl.innerHTML = '<p class="text-muted small">No functions used</p>';
    } else {
        let html = '<div class="row g-2">';
        functions.forEach(f => {
            html += `
                <div class="col-12">
                    <div class="card card-sm">
                        <div class="card-body p-2">
                            <strong class="small">${escapeHtml(f.name)}</strong>
                            <div class="small text-muted">${escapeHtml(f.purpose || '')}</div>
                        </div>
                    </div>
                </div>
            `;
        });
        html += '</div>';
        functionsEl.innerHTML = html;
    }
}

/**
 * Render Before/After tab
 */
function renderBeforeAfterTab(inspector, container) {
    const before = inspector.before || {};
    const after = inspector.after || {};
    const el = container.querySelector('#inspectorBeforeAfter');

    const allTables = new Set([...Object.keys(before), ...Object.keys(after)]);

    if (allTables.size === 0) {
        el.innerHTML = '<p class="text-muted">No before/after data available</p>';
        return;
    }

    let html = '';
    allTables.forEach(table => {
        const beforeRows = before[table] || [];
        const afterRows = after[table] || [];

        html += `
            <div class="inspector-section">
                <h6>${escapeHtml(table)}</h6>
                <div class="before-after-container">
                    <div>
                        <div class="small text-muted mb-1">BEFORE (${beforeRows.length} rows)</div>
                        ${renderDataTable(table, beforeRows, afterRows, 'before')}
                    </div>
                    <div>
                        <div class="small text-muted mb-1">AFTER (${afterRows.length} rows)</div>
                        ${renderDataTable(table, afterRows, beforeRows, 'after')}
                    </div>
                </div>
            </div>
        `;
    });

    el.innerHTML = html;
}

/**
 * Render a data table for before/after comparison
 */
function renderDataTable(tableName, rows, otherRows, side) {
    if (rows.length === 0) {
        return '<div class="before-after-table table-responsive"><table class="table table-sm"><tbody><tr><td class="text-muted">(empty)</td></tr></tbody></table></div>';
    }

    // Get all columns from both sides
    const allCols = new Set();
    [...rows, ...otherRows].forEach(row => {
        Object.keys(row).forEach(k => allCols.add(k));
    });
    const columns = Array.from(allCols);

    let html = '<div class="before-after-table table-responsive"><table class="table table-sm table-bordered"><thead><tr>';
    columns.forEach(col => {
        html += `<th class="small">${escapeHtml(col)}</th>`;
    });
    html += '</tr></thead><tbody>';

    rows.forEach(row => {
        html += '<tr>';
        columns.forEach(col => {
            const value = row[col];
            const otherRow = otherRows.find(r => {
                // Try to match by primary key (id column)
                const pkCols = columns.filter(c => c.toLowerCase().includes('id'));
                return pkCols.some(pk => row[pk] !== undefined && r[pk] === row[pk]);
            });
            const otherValue = otherRow ? otherRow[col] : undefined;
            const changed = otherValue !== undefined && otherValue !== value;
            const added = otherValue === undefined;
            const removed = false; // This row exists in 'rows' but not in 'otherRows'

            let cls = '';
            if (side === 'before' && removed) cls = 'cell-removed';
            else if (side === 'after' && added) cls = 'cell-added';
            else if (changed) cls = 'cell-changed';

            const displayValue = value === null || value === undefined ? '<span class="text-muted">—</span>' : escapeHtml(String(value));
            html += `<td class="${cls}">${displayValue}</td>`;
        });
        html += '</tr>';
    });

    // Show rows that were removed (in other but not in this)
    if (side === 'before') {
        otherRows.forEach(otherRow => {
            const pkCols = columns.filter(c => c.toLowerCase().includes('id'));
            const hasMatch = rows.some(row => pkCols.some(pk => row[pk] !== undefined && otherRow[pk] === row[pk]));
            if (!hasMatch) {
                html += '<tr class="cell-removed">';
                columns.forEach(col => {
                    const value = otherRow[col];
                    const displayValue = value === null || value === undefined ? '<span class="text-muted">—</span>' : escapeHtml(String(value));
                    html += `<td>${displayValue}</td>`;
                });
                html += '</tr>';
            }
        });
    }

    html += '</tbody></table></div>';
    return html;
}

/**
 * Render Raw JSON tab
 */
function renderRawJsonTab(inspector, container) {
    const rawEl = container.querySelector('#inspectorRawJson');
    rawEl.textContent = JSON.stringify(inspector, null, 2);
}

/**
 * Setup copy buttons
 */
function setupCopyButtons(container) {
    const copySqlBtn = container.querySelector('#copySqlBtn');
    const copyRawBtn = container.querySelector('#copyRawBtn');

    if (copySqlBtn) {
        copySqlBtn.addEventListener('click', () => {
            const sqlEl = container.querySelector('#inspectorSql');
            navigator.clipboard.writeText(sqlEl.textContent).then(() => {
                copySqlBtn.innerHTML = '<i class="bi bi-check"></i> Copied!';
                setTimeout(() => copySqlBtn.innerHTML = '<i class="bi bi-clipboard"></i> Copy All', 2000);
            });
        });
    }

    if (copyRawBtn) {
        copyRawBtn.addEventListener('click', () => {
            const rawEl = container.querySelector('#inspectorRawJson');
            navigator.clipboard.writeText(rawEl.textContent).then(() => {
                copyRawBtn.innerHTML = '<i class="bi bi-check"></i> Copied!';
                setTimeout(() => copyRawBtn.innerHTML = '<i class="bi bi-clipboard"></i> Copy', 2000);
            });
        });
    }
}

/**
 * Render error banner for failed operations
 */
export function renderErrorBanner(inspector, container) {
    if (!inspector.error) return;

    const error = inspector.error;
    const html = `
        <div class="alert alert-danger mb-3" role="alert">
            <h6 class="alert-heading"><i class="bi bi-x-circle"></i> Operation Blocked</h6>
            <p class="mb-1">${escapeHtml(inspector.message || 'Operation failed')}</p>
            <hr>
            <div class="row g-2">
                <div class="col-auto"><strong>Error Code:</strong></div>
                <div class="col"><code>${escapeHtml(error.code || 'Unknown')}</code></div>
                <div class="col-auto"><strong>Kind:</strong></div>
                <div class="col"><code>${escapeHtml(error.kind || 'Unknown')}</code></div>
                ${error.constraint ? `
                    <div class="col-auto"><strong>Constraint:</strong></div>
                    <div class="col"><code>${escapeHtml(error.constraint)}</code></div>
                ` : ''}
                <div class="col-auto"><strong>Detail:</strong></div>
                <div class="col"><small class="text-muted">${escapeHtml(error.detail || '')}</small></div>
            </div>
        </div>
    `;

    // Prepend to container
    const tempDiv = document.createElement('div');
    tempDiv.innerHTML = html;
    container.insertBefore(tempDiv.firstElementChild, container.firstChild);
}

// Make globally available for app.js fallback
window.inspector = { render };

/** Open the shared slide-in inspector panel (present on every page via base.html). */
export function openInspector(inspectorData) {
    const panel = document.getElementById('inspectorPanel');
    const body = document.getElementById('inspectorBody');
    if (!panel || !body || !inspectorData) return;
    body.innerHTML = '';
    render(inspectorData, body);
    panel.classList.add('open');
}

export function closeInspector() {
    const panel = document.getElementById('inspectorPanel');
    if (panel) panel.classList.remove('open');
}

export default { render, renderErrorBanner, openInspector, closeInspector };