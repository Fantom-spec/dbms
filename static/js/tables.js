/**
 * Table Rendering Module
 * Renders data tables from API responses (object rows or array rows for reports)
 * Supports badges, formatters, row click handlers, CSV export
 */

import { formatCurrency, formatDateTime } from './api.js';

/**
 * Default formatters for common column types
 */
const DEFAULT_FORMATTERS = {
    currency: (value) => formatCurrency(value),
    datetime: (value) => formatDateTime(value),
    date: (value) => value ? value.split(' ')[0] : '—',
    badge: (value, row, colDef) => {
        if (colDef.badgeMap && colDef.badgeMap[value]) {
            const { class: cls, label } = colDef.badgeMap[value];
            return `<span class="badge ${cls}">${label || value}</span>`;
        }
        return `<span class="badge bg-secondary">${value}</span>`;
    },
    boolean: (value) => value ? '<i class="bi bi-check text-success"></i>' : '<i class="bi bi-x text-danger"></i>',
    truncate: (value, row, colDef) => {
        const maxLen = colDef.maxLength || 50;
        if (!value) return '—';
        const str = String(value);
        return str.length > maxLen ? str.substring(0, maxLen) + '…' : str;
    }
};

/**
 * Render a table into a container
 * @param {HTMLElement} container - Container element
 * @param {Array<string|object>} columns - Column definitions: string (key) or {key, label, formatter, badgeMap, className, width, align}
 * @param {Array<object|Array>} rows - Data rows (objects or arrays for reports)
 * @param {object} options - { badgeColumns, formatters, onRowClick, emptyMessage, sortable, csvExport, csvFilename }
 */
export function renderTable(container, columns, rows, options = {}) {
    const {
        badgeColumns = {},
        formatters = {},
        onRowClick = null,
        emptyMessage = 'No rows to display',
        sortable = false,
        csvExport = true,
        csvFilename = 'export.csv',
        rowClass = null,
        showIndex = false
    } = options;

    // Merge default and custom formatters
    const allFormatters = { ...DEFAULT_FORMATTERS, ...formatters };

    // Normalize columns to objects
    const normalizedColumns = columns.map((col, idx) => {
        if (typeof col === 'string') {
            return { key: col, label: col.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase()) };
        }
        return { ...col, key: col.key || col.label?.toLowerCase().replace(/\s+/g, '_') };
    });

    // Build table HTML
    let html = '';

    if (csvExport && rows.length > 0) {
        html += `
            <div class="table-toolbar mb-2 d-flex justify-content-end">
                <button class="btn btn-sm btn-outline-secondary csv-export-btn" data-csv-filename="${csvFilename}">
                    <i class="bi bi-download"></i> Export CSV
                </button>
            </div>
        `;
    }

    html += '<div class="table-responsive"><table class="table table-hover table-striped align-middle mb-0">';

    // Header
    html += '<thead><tr>';
    if (showIndex) html += '<th scope="col" style="width: 40px;">#</th>';
    normalizedColumns.forEach(col => {
        const style = col.width ? `style="width: ${col.width};"` : '';
        const sortAttr = sortable ? `data-sort="${col.key}"` : '';
        html += `<th scope="col" ${style} ${sortAttr}>${col.label || col.key}</th>`;
    });
    html += '</tr></thead>';

    // Body
    html += '<tbody>';
    if (rows.length === 0) {
        const colspan = normalizedColumns.length + (showIndex ? 1 : 0);
        html += `<tr><td colspan="${colspan}" class="text-center text-muted py-4">${emptyMessage}</td></tr>`;
    } else {
        rows.forEach((row, rowIdx) => {
            const rowData = Array.isArray(row) ? row : row;
            const rowCls = rowClass ? (typeof rowClass === 'function' ? rowClass(row) : rowClass) : '';
            const clickAttr = onRowClick ? `data-row-index="${rowIdx}" class="cursor-pointer ${rowCls}"` : `class="${rowCls}"`;

            html += `<tr ${clickAttr}>`;
            if (showIndex) html += `<td>${rowIdx + 1}</td>`;

            normalizedColumns.forEach((col, colIdx) => {
                let value;
                if (Array.isArray(row)) {
                    value = row[colIdx];
                } else {
                    value = row[col.key];
                }

                let formattedValue;
                const badgeConfig = badgeColumns[col.key];

                if (col.formatter && allFormatters[col.formatter]) {
                    formattedValue = allFormatters[col.formatter](value, row, col);
                } else if (badgeConfig) {
                    formattedValue = DEFAULT_FORMATTERS.badge(value, row, { badgeMap: badgeConfig });
                } else if (value === null || value === undefined) {
                    formattedValue = '<span class="text-muted">—</span>';
                } else if (typeof value === 'number' && Number.isInteger(value) && col.key.includes('id')) {
                    formattedValue = value;
                } else if (typeof value === 'number' && (col.key.includes('amount') || col.key.includes('charge') || col.key.includes('price') || col.key.includes('cost') || col.key.includes('total'))) {
                    formattedValue = formatCurrency(value);
                } else if (typeof value === 'string' && value.match(/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$/)) {
                    formattedValue = formatDateTime(value);
                } else if (typeof value === 'string' && value.match(/^\d{4}-\d{2}-\d{2}$/)) {
                    formattedValue = value;
                } else {
                    formattedValue = escapeHtml(String(value));
                }

                const align = col.align ? `class="text-${col.align}"` : '';
                html += `<td ${align}>${formattedValue}</td>`;
            });
            html += '</tr>';
        });
    }
    html += '</tbody></table></div>';

    container.innerHTML = html;

    // Attach event listeners
    if (onRowClick) {
        container.querySelectorAll('tbody tr[data-row-index]').forEach(tr => {
            tr.addEventListener('click', (e) => {
                if (e.target.closest('button, a, input, select')) return;
                const rowIdx = parseInt(tr.dataset.rowIndex, 10);
                onRowClick(rows[rowIdx], rowIdx, tr);
            });
        });
    }

    // CSV Export
    if (csvExport) {
        const csvBtn = container.querySelector('.csv-export-btn');
        if (csvBtn) {
            csvBtn.addEventListener('click', () => exportToCsv(normalizedColumns, rows, csvBtn.dataset.csvFilename));
        }
    }

    // Sortable headers
    if (sortable) {
        container.querySelectorAll('th[data-sort]').forEach(th => {
            th.style.cursor = 'pointer';
            th.addEventListener('click', () => sortTable(container, normalizedColumns, rows, th.dataset.sort));
        });
    }
}

/**
 * Sort table by column
 */
function sortTable(container, columns, rows, key) {
    const col = columns.find(c => c.key === key);
    if (!col) return;

    const currentSort = container.dataset.sortKey === key ? container.dataset.sortDir : 'asc';
    const newDir = currentSort === 'asc' ? 'desc' : 'asc';

    rows.sort((a, b) => {
        const av = Array.isArray(a) ? a[columns.findIndex(c => c.key === key)] : a[key];
        const bv = Array.isArray(b) ? b[columns.findIndex(c => c.key === key)] : b[key];

        if (av === null || av === undefined) return 1;
        if (bv === null || bv === undefined) return -1;

        let cmp = 0;
        if (typeof av === 'number' && typeof bv === 'number') {
            cmp = av - bv;
        } else {
            cmp = String(av).localeCompare(String(bv));
        }
        return newDir === 'asc' ? cmp : -cmp;
    });

    container.dataset.sortKey = key;
    container.dataset.sortDir = newDir;

    // Re-render body only
    const tbody = container.querySelector('tbody');
    if (tbody) {
        let html = '';
        rows.forEach((row, rowIdx) => {
            html += '<tr' + (col.onRowClick ? ` data-row-index="${rowIdx}" class="cursor-pointer"` : '') + '>';
            columns.forEach((c, ci) => {
                let value = Array.isArray(row) ? row[ci] : row[c.key];
                let formattedValue = value === null || value === undefined ? '<span class="text-muted">—</span>' : escapeHtml(String(value));
                html += `<td>${formattedValue}</td>`;
            });
            html += '</tr>';
        });
        tbody.innerHTML = html;
    }
}

/**
 * Export table data to CSV
 */
function exportToCsv(columns, rows, filename) {
    const headers = columns.map(c => c.label || c.key).join(',');
    const dataRows = rows.map(row => {
        return columns.map((col, idx) => {
            const value = Array.isArray(row) ? row[idx] : row[col.key];
            if (value === null || value === undefined) return '';
            const str = String(value).replace(/"/g, '""');
            return str.includes(',') || str.includes('"') || str.includes('\n') ? `"${str}"` : str;
        }).join(',');
    });
    const csv = [headers, ...dataRows].join('\n');
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = filename;
    link.click();
    URL.revokeObjectURL(link.href);
}

/**
 * Escape HTML to prevent XSS
 */
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

/**
 * Create a table with pagination (for large datasets)
 */
export function renderPaginatedTable(container, columns, rows, options = {}) {
    const { pageSize = 25, ...tableOptions } = options;
    let currentPage = 1;

    function renderPage() {
        const start = (currentPage - 1) * pageSize;
        const end = start + pageSize;
        const pageRows = rows.slice(start, end);

        renderTable(container, columns, pageRows, {
            ...tableOptions,
            csvExport: false // Disable per-page export
        });

        // Add pagination controls
        const totalPages = Math.ceil(rows.length / pageSize);
        if (totalPages > 1) {
            const pagination = document.createElement('nav');
            pagination.className = 'mt-3';
            pagination.innerHTML = `
                <ul class="pagination pagination-sm justify-content-center">
                    <li class="page-item ${currentPage === 1 ? 'disabled' : ''}">
                        <button class="page-link" data-page="${currentPage - 1}">&laquo; Previous</button>
                    </li>
                    ${Array.from({ length: totalPages }, (_, i) => i + 1).map(p => `
                        <li class="page-item ${p === currentPage ? 'active' : ''}">
                            <button class="page-link" data-page="${p}">${p}</button>
                        </li>
                    `).join('')}
                    <li class="page-item ${currentPage === totalPages ? 'disabled' : ''}">
                        <button class="page-link" data-page="${currentPage + 1}">Next &raquo;</button>
                    </li>
                </ul>
            `;
            container.appendChild(pagination);

            pagination.querySelectorAll('button[data-page]').forEach(btn => {
                btn.addEventListener('click', () => {
                    const page = parseInt(btn.dataset.page, 10);
                    if (page >= 1 && page <= totalPages) {
                        currentPage = page;
                        renderPage();
                    }
                });
            });
        }
    }

    renderPage();
}

/**
 * Update a single row in an existing table
 */
export function updateTableRow(container, rowIndex, newRowData, columns) {
    const tr = container.querySelector(`tbody tr[data-row-index="${rowIndex}"]`);
    if (!tr) return;

    const normalizedColumns = columns.map(col =>
        typeof col === 'string' ? { key: col } : col
    );

    normalizedColumns.forEach((col, idx) => {
        const td = tr.cells[idx];
        if (!td) return;
        const value = Array.isArray(newRowData) ? newRowData[idx] : newRowData[col.key];
        td.innerHTML = value === null || value === undefined ? '<span class="text-muted">—</span>' : escapeHtml(String(value));
    });
}

export function showEmptyState(container, message = 'No data available', icon = 'bi-inbox') {
    if (!container) return;
    container.innerHTML = `<div class="empty-state"><i class="bi ${escapeHtml(icon)}"></i><p>${escapeHtml(message)}</p></div>`;
}

export { escapeHtml };