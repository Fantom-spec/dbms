/**
 * Audit Page Script
 * Audit log with filters, tamper test
 */

import { get, post, handle } from '../api.js';
import { renderTable } from '../tables.js';
import { openInspector, showEmptyState, openInspector as openInspectorGlobal } from '../app.js';

export async function loadAudit() {
    await fetchFilterOptions();
    await fetchAudit();
    setupForms();
}

async function fetchFilterOptions() {
    const envelope = await get('/audit?limit=1000');
    if (envelope.ok && envelope.data) {
        const tables = [...new Set(envelope.data.map(r => r.table_name).filter(Boolean))].sort();
        const actions = [...new Set(envelope.data.map(r => r.action_type).filter(Boolean))].sort();

        const tableSelect = document.getElementById('auditTableFilter');
        if (tableSelect) {
            tables.forEach(t => {
                const opt = document.createElement('option');
                opt.value = t;
                opt.textContent = t;
                tableSelect.appendChild(opt);
            });
        }

        const actionSelect = document.getElementById('auditActionFilter');
        if (actionSelect) {
            actions.forEach(a => {
                const opt = document.createElement('option');
                opt.value = a;
                opt.textContent = a;
                actionSelect.appendChild(opt);
            });
        }
    }
}

async function fetchAudit() {
    const table = document.getElementById('auditTableFilter')?.value || '';
    const action = document.getElementById('auditActionFilter')?.value || '';
    const limit = document.getElementById('auditLimit')?.value || 100;

    const params = new URLSearchParams();
    if (table) params.set('table', table);
    if (action) params.set('action', action);
    params.set('limit', limit);

    const envelope = await get(`/audit?${params.toString()}`);
    handle(envelope, {
        successToast: false,
        errorToast: true,
        onSuccess: (env) => {
            renderAuditTable(env.data || []);
        }
    });
}

function renderAuditTable(data) {
    const container = document.getElementById('auditTableContainer');
    const countEl = document.getElementById('auditCount');
    if (!container) return;

    if (countEl) countEl.textContent = `${data.length} entries`;

    if (!data || data.length === 0) {
        showEmptyState(container, 'No audit entries found');
        return;
    }

    renderTable(container, [
        { key: 'log_id', label: 'ID', align: 'center', width: '70px' },
        { key: 'table_name', label: 'Table', width: '100px' },
        { key: 'action_type', label: 'Action', width: '100px' },
        { key: 'record_id', label: 'Record ID', align: 'center', width: '100px' },
        { key: 'changed_by', label: 'User', width: '120px' },
        { key: 'change_time', label: 'Time', width: '180px' },
        { key: 'description', label: 'Description' }
    ], data, {
        emptyMessage: 'No audit entries',
        csvExport: true,
        csvFilename: 'audit_log.csv'
    });
}

function setupForms() {
    const filterForm = document.getElementById('auditFilterForm');
    if (filterForm) {
        filterForm.addEventListener('submit', (e) => {
            e.preventDefault();
            fetchAudit();
        });
    }

    const clearBtn = document.getElementById('clearAuditFilters');
    if (clearBtn) {
        clearBtn.addEventListener('click', () => {
            document.getElementById('auditTableFilter').value = '';
            document.getElementById('auditActionFilter').value = '';
            document.getElementById('auditLimit').value = '100';
            fetchAudit();
        });
    }

    const refreshBtn = document.getElementById('refreshAuditBtn');
    if (refreshBtn) {
        refreshBtn.addEventListener('click', fetchAudit);
    }

    // Tamper test buttons
    const tamperUpdateBtn = document.getElementById('tamperUpdateBtn');
    const tamperDeleteBtn = document.getElementById('tamperDeleteBtn');
    const tamperResult = document.getElementById('tamperResult');

    if (tamperUpdateBtn) {
        tamperUpdateBtn.addEventListener('click', () => runTamperTest('update'));
    }
    if (tamperDeleteBtn) {
        tamperDeleteBtn.addEventListener('click', () => runTamperTest('delete'));
    }
}

async function runTamperTest(mode) {
    const tamperUpdateBtn = document.getElementById('tamperUpdateBtn');
    const tamperDeleteBtn = document.getElementById('tamperDeleteBtn');
    const tamperResult = document.getElementById('tamperResult');

    if (tamperUpdateBtn) tamperUpdateBtn.disabled = true;
    if (tamperDeleteBtn) tamperDeleteBtn.disabled = true;
    if (tamperResult) {
        tamperResult.style.display = 'block';
        tamperResult.innerHTML = '<div class="text-center py-3"><div class="spinner-border"></div></div>';
    }

    const envelope = await post('/audit/tamper-test', { mode });
    handle(envelope, {
        successToast: false, // Don't show toast, we show custom result
        errorToast: false,
        inspectorEl: document.getElementById('inspectorBody'),
        onSuccess: (env) => {
            const data = env.data;
            if (tamperResult) {
                if (data.blocked) {
                    tamperResult.innerHTML = `
                        <div class="alert alert-success">
                            <h6><i class="bi bi-shield-check"></i> Blocked by trg_protect_audit</h6>
                            <p class="mb-0">The database rejected the ${mode.toUpperCase()} attempt.</p>
                            <hr>
                            <code>${data.error || 'AUDIT_LOG entries cannot be modified or deleted'}</code>
                        </div>
                    `;
                } else {
                    tamperResult.innerHTML = `
                        <div class="alert alert-danger">
                            <h6><i class="bi bi-exclamation-triangle"></i> NOT BLOCKED!</h6>
                            <p class="mb-0">The ${mode.toUpperCase()} succeeded (this should not happen).</p>
                        </div>
                    `;
                }
            }
        },
        onError: (env) => {
            if (tamperResult) {
                tamperResult.innerHTML = `
                    <div class="alert alert-danger">
                        <h6><i class="bi bi-x-circle"></i> Error</h6>
                        <p class="mb-0">${env.message}</p>
                    </div>
                `;
            }
        }
    });

    if (tamperUpdateBtn) tamperUpdateBtn.disabled = false;
    if (tamperDeleteBtn) tamperDeleteBtn.disabled = false;
}

window.pageRefresh = loadAudit;