/**
 * Patients Page Script
 * Patient listing, search, register, edit, history, delete
 */

import { get, post, put, del, handle, preventDoubleSubmit } from '../api.js';
import { renderTable, escapeHtml } from '../tables.js';
import { openInspector, showLoading, showEmptyState, formatNumber } from '../app.js';

let patientsData = [];
let lookupsData = null;

export async function loadPatients() {
    showTableLoading(true);
    await loadLookups();
    await fetchPatients('');
    showTableLoading(false);
}

async function loadLookups() {
    const env = await get('/lookups');
    if (env.ok) lookupsData = env.data;
}

async function fetchPatients(query) {
    const envelope = await get(`/patients${query ? '?q=' + encodeURIComponent(query) : ''}`);
    handle(envelope, {
        successToast: false,
        errorToast: true,
        onSuccess: (env) => {
            patientsData = env.data || [];
            renderPatientsTable(patientsData);
        },
        onError: () => {
            showEmptyState(document.getElementById('patientsTableContainer'), 'Failed to load patients');
        }
    });
}

function renderPatientsTable(data) {
    const container = document.getElementById('patientsTableContainer');
    if (!container) return;

    if (!data || data.length === 0) {
        showEmptyState(container, 'No patients found');
        return;
    }

    renderTable(container, [
        { key: 'patient_id', label: 'ID', align: 'center', width: '70px' },
        { key: 'patient_name', label: 'Name' },
        { key: 'gender', label: 'Gender', width: '90px' },
        { key: 'date_of_birth', label: 'DOB', width: '120px' },
        { key: 'phone', label: 'Phone', width: '130px' },
        { key: 'blood_group', label: 'Blood', width: '90px' },
        { key: 'visit_count', label: 'Visits', align: 'center', width: '80px' },
        { key: 'actions', label: 'Actions', width: '180px', formatter: 'actions' }
    ], data, {
        emptyMessage: 'No patients found',
        csvExport: true,
        csvFilename: 'patients.csv',
        formatters: {
            actions: (value, row) => `
                <div class="btn-group btn-group-sm" role="group">
                    <button class="btn btn-outline-primary view-history" data-id="${row.patient_id}" title="View History" aria-label="View History">
                        <i class="bi bi-clock-history"></i>
                    </button>
                    <button class="btn btn-outline-secondary edit-patient" data-id="${row.patient_id}" title="Edit" aria-label="Edit Patient">
                        <i class="bi bi-pencil"></i>
                    </button>
                    <button class="btn btn-outline-danger delete-patient" data-id="${row.patient_id}" title="Delete" aria-label="Delete Patient">
                        <i class="bi bi-trash"></i>
                    </button>
                </div>
            `
        }
    });

    // Attach event listeners
    attachPatientActions();
}

function attachPatientActions() {
    // View History
    document.querySelectorAll('.view-history').forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.stopPropagation();
            const id = btn.dataset.id;
            viewPatientHistory(id);
        });
    });

    // Edit Patient
    document.querySelectorAll('.edit-patient').forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.stopPropagation();
            const id = btn.dataset.id;
            editPatient(id);
        });
    });

    // Delete Patient
    document.querySelectorAll('.delete-patient').forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.stopPropagation();
            const id = btn.dataset.id;
            deletePatient(id);
        });
    });
}

// Search functionality
document.addEventListener('DOMContentLoaded', () => {
    const searchInput = document.getElementById('patientSearch');
    if (searchInput) {
        let debounceTimer;
        searchInput.addEventListener('input', (e) => {
            clearTimeout(debounceTimer);
            debounceTimer = setTimeout(() => {
                fetchPatients(e.target.value);
            }, 300);
        });
    }

    // Register form
    const registerForm = document.getElementById('registerPatientForm');
    if (registerForm) {
        registerForm.addEventListener('submit', preventDoubleSubmit(registerForm, registerPatient));
    }

    // Edit form
    const editForm = document.getElementById('editPatientForm');
    if (editForm) {
        editForm.addEventListener('submit', preventDoubleSubmit(editForm, submitEditPatient));
    }

    loadPatients();
});

async function registerPatient() {
    const form = document.getElementById('registerPatientForm');
    const formData = new FormData(form);
    const data = Object.fromEntries(formData);

    const envelope = await post('/patients', data);
    handle(envelope, {
        successToast: true,
        errorToast: true,
        inspectorEl: document.getElementById('inspectorBody'),
        onSuccess: () => {
            bootstrap.Modal.getInstance(document.getElementById('registerPatientModal'))?.hide();
            form.reset();
            fetchPatients(document.getElementById('patientSearch')?.value || '');
        }
    });
}

async function editPatient(id) {
    const patient = patientsData.find(p => p.patient_id == id);
    if (!patient) return;

    document.getElementById('editPatientId').value = patient.patient_id;
    document.getElementById('editPatientName').value = patient.patient_name;
    document.getElementById('editPatientGender').value = patient.gender;
    document.getElementById('editPatientDob').value = patient.date_of_birth;
    document.getElementById('editPatientPhone').value = patient.phone;
    document.getElementById('editPatientBloodGroup').value = patient.blood_group || '';
    document.getElementById('editPatientEmergency').value = patient.emergency_contact || '';
    document.getElementById('editPatientAddress').value = patient.address || '';

    new bootstrap.Modal(document.getElementById('editPatientModal')).show();
}

async function submitEditPatient() {
    const form = document.getElementById('editPatientForm');
    const formData = new FormData(form);
    const data = Object.fromEntries(formData);
    const id = data.patient_id;
    delete data.patient_id;

    const envelope = await put(`/patients/${id}`, data);
    handle(envelope, {
        successToast: true,
        errorToast: true,
        inspectorEl: document.getElementById('inspectorBody'),
        onSuccess: () => {
            bootstrap.Modal.getInstance(document.getElementById('editPatientModal'))?.hide();
            fetchPatients(document.getElementById('patientSearch')?.value || '');
        }
    });
}

async function deletePatient(id) {
    const patient = patientsData.find(p => p.patient_id == id);
    if (!patient) return;

    if (!confirm(`Delete patient "${escapeHtml(patient.patient_name)}" (ID: ${id})? This will fail if the patient has visits.`)) {
        return;
    }

    const envelope = await del(`/patients/${id}`);
    handle(envelope, {
        successToast: true,
        errorToast: true,
        inspectorEl: document.getElementById('inspectorBody'),
        onSuccess: () => {
            fetchPatients(document.getElementById('patientSearch')?.value || '');
        }
    });
}

async function viewPatientHistory(id) {
    const modal = new bootstrap.Modal(document.getElementById('patientHistoryModal'));
    const infoEl = document.getElementById('patientHistoryInfo');
    const tableEl = document.getElementById('patientHistoryTable');

    infoEl.innerHTML = '<div class="text-center py-3"><div class="spinner-border"></div></div>';
    tableEl.innerHTML = '';
    modal.show();

    const envelope = await get(`/patients/${id}/history`);
    handle(envelope, {
        successToast: false,
        errorToast: true,
        onSuccess: (env) => {
            const data = env.data;
            if (!data) return;

            const p = data.patient;
            infoEl.innerHTML = `
                <div class="row g-2 mb-3">
                    <div class="col-md-3"><strong>ID:</strong> ${p.patient_id}</div>
                    <div class="col-md-3"><strong>Name:</strong> ${p.patient_name}</div>
                    <div class="col-md-3"><strong>Phone:</strong> ${p.phone}</div>
                    <div class="col-md-3"><strong>Blood Group:</strong> ${p.blood_group || '—'}</div>
                </div>
            `;

            if (data.visits && data.visits.length) {
                renderTable(tableEl, [
                    { key: 'visit_id', label: 'Visit ID', align: 'center', width: '90px' },
                    { key: 'visit_time', label: 'Date & Time', width: '180px' },
                    { key: 'visit_type', label: 'Type', width: '120px' },
                    { key: 'doctor_name', label: 'Doctor' },
                    { key: 'complaint', label: 'Complaint' },
                    { key: 'visit_status', label: 'Status', width: '140px' }
                ], data.visits, {
                    emptyMessage: 'No visits found',
                    csvExport: true,
                    csvFilename: `patient_${id}_history.csv`
                });
            } else {
                showEmptyState(tableEl, 'No visits found');
            }
        },
        onError: () => {
            showEmptyState(tableEl, 'Failed to load history');
        }
    });
}

function showTableLoading(show) {
    const container = document.getElementById('patientsTableContainer');
    if (!container) return;

    if (show) {
        container.innerHTML = '<div class="table-responsive"><table class="table"><tbody><tr><td class="text-center py-4"><div class="spinner-border"></div></td></tr></tbody></table></div>';
    }
}

window.pageRefresh = loadPatients;