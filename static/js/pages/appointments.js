/**
 * Appointments Page Script
 * Book appointments, view visits, cancel, start treatment
 */

import { get, post, handle } from '../api.js';
import { renderTable } from '../tables.js';
import { openInspector, showLoading, showEmptyState, getVisitStatusBadgeClass, getVisitStatusLabel } from '../app.js';

let visitsData = [];
let lookupsData = null;
let lastBookingData = null;

export async function loadAppointments() {
    await loadLookups();
    await fetchVisits('');
    setupFilters();
}

async function loadLookups() {
    const env = await get('/lookups');
    if (env.ok) {
        lookupsData = env.data;
        populateDoctorSelect();
        populatePatientSelect();
    }
}

function populateDoctorSelect() {
    const select = document.getElementById('apptDoctorId');
    if (!select || !lookupsData?.doctors) return;

    const currentVal = select.value;
    select.innerHTML = '<option value="">Select doctor...</option>';
    lookupsData.doctors.forEach(d => {
        const opt = document.createElement('option');
        opt.value = d.id;
        opt.textContent = `${d.name} (${d.department}, ₹${d.fee})`;
        opt.dataset.department = d.department;
        opt.dataset.fee = d.fee;
        select.appendChild(opt);
    });
    if (currentVal) select.value = currentVal;
}

function populatePatientSelect() {
    const select = document.getElementById('apptPatientId');
    if (!select || !lookupsData?.patients) return;

    const currentVal = select.value;
    select.innerHTML = '<option value="">Select patient...</option>';
    lookupsData.patients.forEach(p => {
        const opt = document.createElement('option');
        opt.value = p.id;
        opt.textContent = p.name;
        select.appendChild(opt);
    });
    if (currentVal) select.value = currentVal;
}

async function fetchVisits(typeFilter) {
    const params = new URLSearchParams();
    if (typeFilter) params.set('type', typeFilter);
    const query = params.toString() ? '?' + params.toString() : '';

    const envelope = await get(`/visits${query}`);
    handle(envelope, {
        successToast: false,
        errorToast: true,
        onSuccess: (env) => {
            visitsData = env.data || [];
            renderVisitsTable(visitsData);
        },
        onError: () => {
            showEmptyState(document.getElementById('visitsTableContainer'), 'Failed to load visits');
        }
    });
}

function renderVisitsTable(data) {
    const container = document.getElementById('visitsTableContainer');
    if (!container) return;

    if (!data || data.length === 0) {
        showEmptyState(container, 'No visits found');
        return;
    }

    renderTable(container, [
        { key: 'visit_id', label: 'Visit ID', align: 'center', width: '90px' },
        { key: 'patient_name', label: 'Patient' },
        { key: 'doctor_name', label: 'Doctor' },
        { key: 'visit_datetime', label: 'Date & Time', width: '180px' },
        { key: 'visit_type', label: 'Type', width: '120px' },
        { key: 'visit_status', label: 'Status', width: '140px', formatter: 'visitStatus' },
        { key: 'complaint', label: 'Complaint' },
        { key: 'actions', label: 'Actions', width: '200px', formatter: 'actions' }
    ], data, {
        emptyMessage: 'No visits found',
        csvExport: true,
        csvFilename: 'visits.csv',
        formatters: {
            visitStatus: (value) => {
                const badgeClass = getVisitStatusBadgeClass(value);
                const label = getVisitStatusLabel(value);
                return `<span class="badge ${badgeClass}">${label}</span>`;
            },
            actions: (value, row) => {
                const actions = [];
                if (row.visit_type === 'Appointment' && row.visit_status === 'Scheduled') {
                    actions.push(`<button class="btn btn-sm btn-outline-danger cancel-visit" data-id="${row.visit_id}" title="Cancel"><i class="bi bi-x-circle"></i> Cancel</button>`);
                }
                if (['Scheduled', 'Waiting'].includes(row.visit_status)) {
                    actions.push(`<button class="btn btn-sm btn-outline-primary start-treatment" data-id="${row.visit_id}" title="Start Treatment"><i class="bi bi-play-circle"></i> Start</button>`);
                }
                actions.push(`<button class="btn btn-sm btn-outline-info view-summary" data-id="${row.visit_id}" title="View Summary"><i class="bi bi-eye"></i></button>`);
                return `<div class="btn-group btn-group-sm" role="group">${actions.join('')}</div>`;
            }
        }
    });

    attachVisitActions();
}

function attachVisitActions() {
    // Cancel
    document.querySelectorAll('.cancel-visit').forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.stopPropagation();
            cancelVisit(btn.dataset.id);
        });
    });

    // Start Treatment
    document.querySelectorAll('.start-treatment').forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.stopPropagation();
            startTreatment(btn.dataset.id);
        });
    });

    // View Summary
    document.querySelectorAll('.view-summary').forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.stopPropagation();
            viewVisitSummary(btn.dataset.id);
        });
    });
}

function setupFilters() {
    document.querySelectorAll('input[name="visitTypeFilter"]').forEach(radio => {
        radio.addEventListener('change', (e) => {
            fetchVisits(e.target.value);
        });
    });
}

// Book Appointment Form
document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('bookAppointmentForm');
    if (form) {
        form.addEventListener('submit', bookAppointment);
    }

    // Doctor info display
    const doctorSelect = document.getElementById('apptDoctorId');
    if (doctorSelect) {
        doctorSelect.addEventListener('change', (e) => {
            const opt = e.target.selectedOptions[0];
            const infoEl = document.getElementById('doctorInfo');
            if (opt.value && infoEl) {
                infoEl.textContent = `Department: ${opt.dataset.department} | Fee: ₹${opt.dataset.fee}`;
            } else if (infoEl) {
                infoEl.textContent = '';
            }
        });
    }

    // Retry last slot
    const retryBtn = document.getElementById('retryLastSlotBtn');
    if (retryBtn) {
        retryBtn.addEventListener('click', () => {
            if (lastBookingData) {
                bookAppointment({ preventDefault: () => {}, target: form }, lastBookingData);
            }
        });
    }

    loadAppointments();
});

async function bookAppointment(e, overrideData = null) {
    e.preventDefault();
    const form = e.target;
    const formData = new FormData(form);
    const data = overrideData || Object.fromEntries(formData);

    // Format slot as YYYY-MM-DD HH:MM:SS
    if (data.slot && data.slot.includes('T')) {
        data.slot = data.slot.replace('T', ' ');
    }

    const envelope = await post('/appointments', data);
    handle(envelope, {
        successToast: true,
        errorToast: true,
        inspectorEl: document.getElementById('inspectorBody'),
        onSuccess: (env) => {
            if (!overrideData) {
                lastBookingData = data;
                document.getElementById('retryLastSlotBtn').disabled = false;
            }
            form.reset();
            fetchVisits(document.querySelector('input[name="visitTypeFilter"]:checked')?.value || '');
        },
        onError: (env) => {
            if (env.error?.code === 'SLOT_TAKEN') {
                lastBookingData = data;
                document.getElementById('retryLastSlotBtn').disabled = false;
            }
        }
    });
}

async function cancelVisit(id) {
    if (!confirm('Cancel this appointment?')) return;

    const envelope = await post(`/visits/${id}/cancel`, {});
    handle(envelope, {
        successToast: true,
        errorToast: true,
        inspectorEl: document.getElementById('inspectorBody'),
        onSuccess: () => {
            fetchVisits(document.querySelector('input[name="visitTypeFilter"]:checked')?.value || '');
        }
    });
}

async function startTreatment(id) {
    const envelope = await post(`/visits/${id}/start-treatment`, {});
    handle(envelope, {
        successToast: true,
        errorToast: true,
        inspectorEl: document.getElementById('inspectorBody'),
        onSuccess: () => {
            fetchVisits(document.querySelector('input[name="visitTypeFilter"]:checked')?.value || '');
        }
    });
}

async function viewVisitSummary(id) {
    const modal = new bootstrap.Modal(document.getElementById('visitSummaryModal'));
    const contentEl = document.getElementById('visitSummaryContent');

    contentEl.innerHTML = '<div class="text-center py-3"><div class="spinner-border"></div></div>';
    modal.show();

    const envelope = await get(`/visits/${id}/summary`);
    handle(envelope, {
        successToast: false,
        errorToast: true,
        onSuccess: (env) => {
            const data = env.data;
            if (!data) return;

            const v = data.visit;
            const p = data.patient;
            const d = data.doctor;
            const b = data.bed;
            const prescriptions = data.prescriptions || [];

            contentEl.innerHTML = `
                <div class="row g-3 mb-3">
                    <div class="col-md-6"><strong>Visit ID:</strong> ${v.visit_id}</div>
                    <div class="col-md-6"><strong>Type:</strong> ${v.visit_type}</div>
                    <div class="col-md-6"><strong>Status:</strong> <span class="badge ${getVisitStatusBadgeClass(v.visit_status)}">${getVisitStatusLabel(v.visit_status)}</span></div>
                    <div class="col-md-6"><strong>Date/Time:</strong> ${v.visit_datetime}</div>
                    <div class="col-md-6"><strong>Patient:</strong> ${p.patient_name} (ID: ${p.patient_id})</div>
                    <div class="col-md-6"><strong>Doctor:</strong> ${d.doctor_name} (${d.department})</div>
                    <div class="col-md-6"><strong>Complaint:</strong> ${v.complaint}</div>
                    ${b ? `<div class="col-md-6"><strong>Bed:</strong> ${b.bed_id} (${b.ward_type}, ₹${b.daily_charge}/day)</div>` : ''}
                    ${data.medicine_cost !== undefined ? `<div class="col-md-6"><strong>Medicine Cost:</strong> ₹${data.medicine_cost}</div>` : ''}
                    ${data.days_stayed !== undefined ? `<div class="col-md-6"><strong>Days Stayed:</strong> ${data.days_stayed}</div>` : ''}
                    ${data.bill ? `<div class="col-md-6"><strong>Bill:</strong> ₹${data.bill.total_amount} (${data.bill.payment_status})</div>` : ''}
                </div>

                ${prescriptions.length ? `
                    <h6>Prescriptions</h6>
                    <div class="table-responsive">
                        <table class="table table-sm">
                            <thead><tr><th>Medicine</th><th>Dosage</th><th>Duration</th><th>Qty</th><th>Price</th></tr></thead>
                            <tbody>
                                ${prescriptions.map(pr => `
                                    <tr>
                                        <td>${pr.medicine_name}</td>
                                        <td>${pr.dosage}</td>
                                        <td>${pr.duration_days} days</td>
                                        <td>${pr.quantity}</td>
                                        <td>₹${pr.price_per_unit}</td>
                                    </tr>
                                `).join('')}
                            </tbody>
                        </table>
                    </div>
                ` : '<p class="text-muted">No prescriptions</p>'}
            `;
        },
        onError: () => {
            contentEl.innerHTML = '<div class="alert alert-danger">Failed to load visit summary</div>';
        }
    });
}

window.pageRefresh = loadAppointments;