/**
 * Emergency Page Script
 * Register emergency, view queue, cursor output
 */

import { get, post, handle, preventDoubleSubmit } from '../api.js';
import { renderTable } from '../tables.js';
import { openInspector, getTriageBadgeClass, getTriageLabel, showEmptyState } from '../app.js';

let autoRefreshInterval = null;
let currentQueueData = null;

export async function loadEmergency() {
    await loadPatients();
    await fetchQueue();
    setupAutoRefresh();
    setupForms();
}

async function loadPatients() {
    const env = await get('/lookups');
    if (env.ok && env.data?.patients) {
        const select = document.getElementById('emgPatientId');
        if (select) {
            select.innerHTML = '<option value="">Select patient...</option>';
            env.data.patients.forEach(p => {
                const opt = document.createElement('option');
                opt.value = p.id;
                opt.textContent = p.name;
                select.appendChild(opt);
            });
        }
    }
}

async function fetchQueue() {
    const envelope = await get('/emergency/queue');
    handle(envelope, {
        successToast: false,
        errorToast: true,
        onSuccess: (env) => {
            currentQueueData = env.data;
            renderQueue(env.data);
            renderCursorOutput(env.data);
        },
        onError: () => {
            showEmptyState(document.getElementById('emergencyQueueContainer'), 'Failed to load queue');
        }
    });
}

function renderQueue(data) {
    const container = document.getElementById('emergencyQueueContainer');
    if (!container) return;

    const rows = data?.rows || [];
    if (rows.length === 0) {
        showEmptyState(container, 'No patients in emergency queue', 'bi-check-circle');
        document.getElementById('cursorOutputContainer').style.display = 'none';
        return;
    }

    document.getElementById('cursorOutputContainer').style.display = 'block';

    renderTable(container, [
        { key: 'visit_id', label: 'Visit ID', align: 'center', width: '90px' },
        { key: 'patient_name', label: 'Patient' },
        { key: 'triage_level', label: 'Triage', width: '120px', formatter: 'triage' },
        { key: 'complaint', label: 'Complaint' },
        { key: 'doctor_name', label: 'Assigned Doctor' },
        { key: 'visit_datetime', label: 'Arrival', width: '160px' },
        { key: 'actions', label: 'Actions', width: '180px', formatter: 'actions' }
    ], rows, {
        emptyMessage: 'No patients in queue',
        csvExport: true,
        csvFilename: 'emergency_queue.csv',
        formatters: {
            triage: (value) => {
                const badgeClass = getTriageBadgeClass(value);
                const label = getTriageLabel(value);
                return `<span class="badge ${badgeClass}">${label} (T${value})</span>`;
            },
            actions: (value, row) => {
                const actions = [];
                if (row.visit_status === 'Waiting') {
                    actions.push(`<button class="btn btn-sm btn-outline-primary start-treatment" data-id="${row.visit_id}" title="Start Treatment"><i class="bi bi-play-circle"></i> Start</button>`);
                }
                if (['Waiting', 'Under Treatment', 'Admitted'].includes(row.visit_status)) {
                    actions.push(`<button class="btn btn-sm btn-outline-danger discharge-emergency" data-id="${row.visit_id}" title="Discharge"><i class="bi bi-door-open"></i> Discharge</button>`);
                }
                return `<div class="btn-group btn-group-sm" role="group">${actions.join('')}</div>`;
            }
        }
    });

    attachQueueActions();
}

function attachQueueActions() {
    document.querySelectorAll('.start-treatment').forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.stopPropagation();
            startTreatment(btn.dataset.id);
        });
    });

    document.querySelectorAll('.discharge-emergency').forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.stopPropagation();
            dischargeVisit(btn.dataset.id);
        });
    });
}

function renderCursorOutput(data) {
    const lines = data?.console_lines || [];
    const cursorEl = document.getElementById('cursorLines');
    if (cursorEl) {
        cursorEl.textContent = lines.join('\n');
    }
}

function setupAutoRefresh() {
    const autoRefresh = document.getElementById('autoRefreshQueue');
    const refreshBtn = document.getElementById('refreshQueueBtn');

    if (refreshBtn) {
        refreshBtn.addEventListener('click', fetchQueue);
    }

    if (autoRefresh) {
        autoRefresh.addEventListener('change', (e) => {
            if (e.target.checked) {
                startAutoRefresh();
            } else {
                stopAutoRefresh();
            }
        });
        if (autoRefresh.checked) startAutoRefresh();
    }
}

function startAutoRefresh() {
    stopAutoRefresh();
    autoRefreshInterval = setInterval(fetchQueue, 10000);
}

function stopAutoRefresh() {
    if (autoRefreshInterval) {
        clearInterval(autoRefreshInterval);
        autoRefreshInterval = null;
    }
}

function setupForms() {
    // Register Emergency Form
    const form = document.getElementById('registerEmergencyForm');
    if (form) {
        form.addEventListener('submit', preventDoubleSubmit(form, registerEmergency));
    }

    // Toggle cursor
    const toggleBtn = document.getElementById('toggleCursorBtn');
    const cursorContent = document.getElementById('cursorContent');
    const chevron = document.getElementById('cursorChevron');
    if (toggleBtn && cursorContent) {
        toggleBtn.addEventListener('click', () => {
            const isHidden = cursorContent.style.display === 'none';
            cursorContent.style.display = isHidden ? 'block' : 'none';
            chevron.classList.toggle('bi-chevron-down', !isHidden);
            chevron.classList.toggle('bi-chevron-up', isHidden);
        });
    }
}

async function registerEmergency() {
    const form = document.getElementById('registerEmergencyForm');
    const formData = new FormData(form);
    const data = Object.fromEntries(formData);
    data.triage_level = parseInt(data.triage_level, 10);

    const envelope = await post('/emergency', data);
    handle(envelope, {
        successToast: true,
        errorToast: true,
        inspectorEl: document.getElementById('inspectorBody'),
        onSuccess: () => {
            form.reset();
            fetchQueue();
        }
    });
}

async function startTreatment(id) {
    const envelope = await post(`/visits/${id}/start-treatment`, {});
    handle(envelope, {
        successToast: true,
        errorToast: true,
        inspectorEl: document.getElementById('inspectorBody'),
        onSuccess: () => fetchQueue()
    });
}

async function dischargeVisit(id) {
    if (!confirm('Discharge this emergency patient?')) return;

    const envelope = await post(`/visits/${id}/discharge`, {});
    handle(envelope, {
        successToast: true,
        errorToast: true,
        inspectorEl: document.getElementById('inspectorBody'),
        onSuccess: () => fetchQueue()
    });
}

// Cleanup on page unload
window.addEventListener('beforeunload', stopAutoRefresh);

window.pageRefresh = loadEmergency;

// Initial load (module scripts run after the DOM is parsed, so this works whether or not DOMContentLoaded already fired)
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', loadEmergency);
} else {
    loadEmergency();
}
