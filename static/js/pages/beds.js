/**
 * Beds Page Script
 * Bed grid by ward, allot bed, discharge, set bed status
 */

import { get, post, handle, preventDoubleSubmit } from '../api.js';
import { renderTable, escapeHtml } from '../tables.js';
import { openInspector, getBedStatusBadgeClass, showLoading, showEmptyState } from '../app.js';

let bedsData = null;

export async function loadBeds() {
    await fetchBeds();
    await fetchAdmittedPatients();
    setupForms();
}

async function fetchBeds() {
    const envelope = await get('/beds');
    handle(envelope, {
        successToast: false,
        errorToast: true,
        onSuccess: (env) => {
            bedsData = env.data;
            renderBedWards(env.data);
        },
        onError: () => {
            showEmptyState(document.getElementById('bedWardsContainer'), 'Failed to load beds');
        }
    });
}

function renderBedWards(data) {
    const container = document.getElementById('bedWardsContainer');
    if (!container) return;

    if (!data) {
        showEmptyState(container, 'No bed data');
        return;
    }

    const wardOrder = ['General', 'Private', 'ICU', 'Emergency'];
    let html = '';

    wardOrder.forEach(wardType => {
        const beds = data[wardType] || [];
        if (beds.length === 0) return;

        const occupied = beds.filter(b => b.bed_status === 'Occupied').length;
        const free = beds.filter(b => b.bed_status === 'Free').length;
        const cleaning = beds.filter(b => b.bed_status === 'Cleaning').length;

        html += `
            <div class="mb-4">
                <div class="d-flex justify-content-between align-items-center mb-2">
                    <h6 class="mb-0">${wardType} Ward</h6>
                    <div class="d-flex gap-2">
                        <span class="badge badge-bed-free">Free: ${free}</span>
                        <span class="badge badge-bed-occupied">Occupied: ${occupied}</span>
                        <span class="badge badge-bed-cleaning">Cleaning: ${cleaning}</span>
                    </div>
                </div>
                <div class="bed-grid" id="bedGrid-${wardType}"></div>
            </div>
        `;
    });

    container.innerHTML = html || '<p class="text-muted">No wards configured</p>';

    // Render individual bed tiles
    wardOrder.forEach(wardType => {
        const beds = data[wardType] || [];
        const gridEl = document.getElementById(`bedGrid-${wardType}`);
        if (!gridEl) return;

        gridEl.innerHTML = beds.map(bed => `
            <div class="bed-tile ${bed.bed_status.toLowerCase()}">
                <div class="bed-id">${bed.bed_id}</div>
                <div class="bed-status">
                    <span class="badge ${getBedStatusBadgeClass(bed.bed_status)}">${bed.bed_status}</span>
                </div>
                <div class="bed-charge">₹${bed.daily_charge}/day</div>
                ${bed.patient_name ? `<div class="patient-name">${escapeHtml(bed.patient_name)} (Visit ${bed.visit_id})</div>` : ''}
                ${bed.bed_status === 'Cleaning' ? `
                    <button class="btn btn-sm btn-success mt-2 mark-free" data-bed-id="${bed.bed_id}">
                        <i class="bi bi-check"></i> Mark Free
                    </button>
                ` : ''}
            </div>
        `).join('');
    });

    // Attach mark free buttons
    document.querySelectorAll('.mark-free').forEach(btn => {
        btn.addEventListener('click', () => setBedStatus(btn.dataset.bedId, 'Free'));
    });
}

async function fetchAdmittedPatients() {
    const envelope = await get('/visits?status=Admitted');
    handle(envelope, {
        successToast: false,
        errorToast: true,
        onSuccess: (env) => {
            renderAdmittedPatients(env.data || []);
        }
    });
}

function renderAdmittedPatients(data) {
    const container = document.getElementById('admittedPatientsTable');
    if (!container) return;

    if (!data || data.length === 0) {
        showEmptyState(container, 'No admitted patients');
        return;
    }

    renderTable(container, [
        { key: 'visit_id', label: 'Visit ID', align: 'center', width: '90px' },
        { key: 'patient_name', label: 'Patient' },
        { key: 'doctor_name', label: 'Doctor' },
        { key: 'visit_datetime', label: 'Admitted', width: '180px' },
        { key: 'visit_type', label: 'Type', width: '120px' },
        { key: 'actions', label: 'Actions', width: '180px', formatter: 'actions' }
    ], data, {
        emptyMessage: 'No admitted patients',
        csvExport: false,
        formatters: {
            actions: (value, row) => `
                <div class="btn-group btn-group-sm" role="group">
                    <button class="btn btn-sm btn-outline-danger discharge-btn" data-id="${row.visit_id}" title="Discharge">
                        <i class="bi bi-door-open"></i> Discharge
                    </button>
                </div>
            `
        }
    });

    document.querySelectorAll('.discharge-btn').forEach(btn => {
        btn.addEventListener('click', () => openDischargeModal(btn.dataset.id));
    });
}

function setupForms() {
    // Add Bed Form
    const addBedForm = document.getElementById('addBedForm');
    if (addBedForm) {
        addBedForm.addEventListener('submit', preventDoubleSubmit(addBedForm, addBed));
    }

    // Add Bed Admin Form (from admin page)
    const addBedAdminForm = document.getElementById('addBedAdminForm');
    if (addBedAdminForm) {
        addBedAdminForm.addEventListener('submit', preventDoubleSubmit(addBedAdminForm, addBed));
    }

    // Allot Bed Form
    const allotBedForm = document.getElementById('allotBedForm');
    if (allotBedForm) {
        allotBedForm.addEventListener('submit', preventDoubleSubmit(allotBedForm, allotBed));
    }

    // Discharge Confirm
    const confirmDischargeBtn = document.getElementById('confirmDischargeBtn');
    if (confirmDischargeBtn) {
        confirmDischargeBtn.addEventListener('click', confirmDischarge);
    }

    // Set Bed Status Form
    const setBedStatusForm = document.getElementById('setBedStatusForm');
    if (setBedStatusForm) {
        setBedStatusForm.addEventListener('submit', preventDoubleSubmit(setBedStatusForm, submitSetBedStatus));
    }

    // Refresh buttons
    const refreshBedsBtn = document.getElementById('refreshBedsBtn');
    if (refreshBedsBtn) {
        refreshBedsBtn.addEventListener('click', () => {
            fetchBeds();
            fetchAdmittedPatients();
        });
    }
}

async function addBed() {
    const form = document.querySelector('#addBedForm, #addBedAdminForm');
    if (!form) return;
    const formData = new FormData(form);
    const data = Object.fromEntries(formData);
    data.daily_charge = parseFloat(data.daily_charge);

    const envelope = await post('/beds', data);
    handle(envelope, {
        successToast: true,
        errorToast: true,
        inspectorEl: document.getElementById('inspectorBody'),
        onSuccess: () => {
            bootstrap.Modal.getInstance(form.closest('.modal'))?.hide();
            form.reset();
            fetchBeds();
        }
    });
}

function openAllotBedModal(visitId) {
    const modal = new bootstrap.Modal(document.getElementById('allotBedModal'));
    document.getElementById('allotBedVisitId').value = visitId;
    document.getElementById('allotBedVisitDisplay').value = visitId;
    document.getElementById('allotBedWardType').value = '';
    document.getElementById('freeBedsInfo').textContent = '';
    modal.show();
}

async function allotBed() {
    const form = document.getElementById('allotBedForm');
    if (!form) return;
    const formData = new FormData(form);
    const data = Object.fromEntries(formData);
    const visitId = data.visit_id;

    const envelope = await post(`/visits/${visitId}/allot-bed`, { ward_type: data.ward_type });
    handle(envelope, {
        successToast: true,
        errorToast: true,
        inspectorEl: document.getElementById('inspectorBody'),
        onSuccess: () => {
            bootstrap.Modal.getInstance(form.closest('.modal'))?.hide();
            fetchBeds();
            fetchAdmittedPatients();
        }
    });
}

function openDischargeModal(visitId) {
    const modal = new bootstrap.Modal(document.getElementById('dischargeModal'));
    document.getElementById('dischargeVisitId').textContent = visitId;
    document.getElementById('confirmDischargeBtn').dataset.visitId = visitId;
    modal.show();
}

async function confirmDischarge() {
    const btn = document.getElementById('confirmDischargeBtn');
    const visitId = btn.dataset.visitId;
    if (!visitId) return;

    btn.disabled = true;
    btn.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Discharging...';

    const envelope = await post(`/visits/${visitId}/discharge`, {});
    handle(envelope, {
        successToast: true,
        errorToast: true,
        inspectorEl: document.getElementById('inspectorBody'),
        onSuccess: () => {
            bootstrap.Modal.getInstance(document.getElementById('dischargeModal'))?.hide();
            fetchBeds();
            fetchAdmittedPatients();
        }
    });

    btn.disabled = false;
    btn.innerHTML = '<i class="bi bi-check-circle"></i> Confirm Discharge';
}

function openSetBedStatusModal(bedId) {
    const modal = new bootstrap.Modal(document.getElementById('setBedStatusModal'));
    document.getElementById('setBedStatusId').value = bedId;
    document.getElementById('setBedStatusDisplay').value = bedId;
    document.getElementById('setBedStatusSelect').value = 'Free';
    modal.show();
}

async function setBedStatus(bedId, status) {
    const envelope = await post(`/beds/${bedId}/status`, { status });
    handle(envelope, {
        successToast: true,
        errorToast: true,
        inspectorEl: document.getElementById('inspectorBody'),
        onSuccess: () => fetchBeds()
    });
}

async function submitSetBedStatus() {
    const form = document.getElementById('setBedStatusForm');
    if (!form) return;
    const formData = new FormData(form);
    const data = Object.fromEntries(formData);
    const bedId = data.bed_id;
    delete data.bed_id;

    await setBedStatus(bedId, data.status);
    bootstrap.Modal.getInstance(form.closest('.modal'))?.hide();
}

window.pageRefresh = loadBeds;