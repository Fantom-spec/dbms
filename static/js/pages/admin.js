/**
 * Admin Page Script
 * Doctors, Medicines, Beds management
 */

import { get, post, put, handle } from '../api.js';
import { renderTable } from '../tables.js';
import { openInspector, showEmptyState } from '../app.js';

let doctorsData = [];
let medicinesData = [];
let bedsData = null;

export async function loadAdmin() {
    await fetchDoctors();
    await fetchMedicines();
    await fetchBeds();
    setupForms();
    setupTabLazyLoad();
}

function setupTabLazyLoad() {
    const tabs = document.getElementById('adminTabs');
    if (!tabs) return;

    tabs.addEventListener('shown.bs.tab', (e) => {
        const target = e.target.getAttribute('data-bs-target');
        if (target === '#tabMedicines' && medicinesData.length === 0) fetchMedicines();
        if (target === '#tabBeds' && !bedsData) fetchBeds();
    });
}

async function fetchDoctors() {
    const envelope = await get('/doctors');
    handle(envelope, {
        successToast: false,
        errorToast: true,
        onSuccess: (env) => {
            doctorsData = env.data || [];
            renderDoctorsTable(doctorsData);
        }
    });
}

function renderDoctorsTable(data) {
    const container = document.getElementById('doctorsTableContainer');
    if (!container) return;

    if (!data || data.length === 0) {
        showEmptyState(container, 'No doctors found');
        return;
    }

    renderTable(container, [
        { key: 'doctor_id', label: 'ID', align: 'center', width: '70px' },
        { key: 'doctor_name', label: 'Name' },
        { key: 'department', label: 'Department' },
        { key: 'specialization', label: 'Specialization' },
        { key: 'consultation_fee', label: 'Fee (₹)', align: 'right', width: '100px', formatter: 'currency' },
        { key: 'shift', label: 'Shift', width: '100px' },
        { key: 'actions', label: 'Actions', width: '120px', formatter: 'actions' }
    ], data, {
        emptyMessage: 'No doctors found',
        csvExport: true,
        csvFilename: 'doctors.csv',
        formatters: {
            currency: (v) => `₹${v}`,
            actions: (v, row) => `
                <div class="btn-group btn-group-sm" role="group">
                    <button class="btn btn-outline-secondary edit-doctor" data-id="${row.doctor_id}" title="Edit">
                        <i class="bi bi-pencil"></i>
                    </button>
                </div>
            `
        }
    });

    document.querySelectorAll('.edit-doctor').forEach(btn => {
        btn.addEventListener('click', () => editDoctor(btn.dataset.id));
    });
}

async function fetchMedicines() {
    const envelope = await get('/medicines');
    handle(envelope, {
        successToast: false,
        errorToast: true,
        onSuccess: (env) => {
            medicinesData = env.data || [];
            renderMedicinesAdminTable(medicinesData);
        }
    });
}

function renderMedicinesAdminTable(data) {
    const container = document.getElementById('medicinesAdminTableContainer');
    if (!container) return;

    if (!data || data.length === 0) {
        showEmptyState(container, 'No medicines found');
        return;
    }

    renderTable(container, [
        { key: 'medicine_id', label: 'ID', align: 'center', width: '70px' },
        { key: 'medicine_name', label: 'Name' },
        { key: 'stock_quantity', label: 'Stock', align: 'center', width: '90px' },
        { key: 'price_per_unit', label: 'Price (₹)', align: 'right', width: '110px', formatter: 'currency' }
    ], data, {
        emptyMessage: 'No medicines found',
        csvExport: true,
        csvFilename: 'medicines_admin.csv',
        formatters: { currency: (v) => `₹${v}` }
    });
}

async function fetchBeds() {
    const envelope = await get('/beds');
    handle(envelope, {
        successToast: false,
        errorToast: true,
        onSuccess: (env) => {
            bedsData = env.data;
            renderBedsAdminTable(bedsData);
        }
    });
}

function renderBedsAdminTable(data) {
    const container = document.getElementById('bedsAdminTableContainer');
    if (!container) return;

    if (!data) {
        showEmptyState(container, 'No bed data');
        return;
    }

    const wardOrder = ['General', 'Private', 'ICU', 'Emergency'];
    const allBeds = [];
    wardOrder.forEach(ward => {
        (data[ward] || []).forEach(b => allBeds.push({ ...b, ward_type: ward }));
    });

    if (allBeds.length === 0) {
        showEmptyState(container, 'No beds found');
        return;
    }

    renderTable(container, [
        { key: 'bed_id', label: 'Bed ID', align: 'center', width: '80px' },
        { key: 'ward_type', label: 'Ward', width: '100px' },
        { key: 'bed_status', label: 'Status', width: '110px', formatter: 'bedStatus' },
        { key: 'daily_charge', label: 'Daily Charge (₹)', align: 'right', width: '140px', formatter: 'currency' },
        { key: 'patient_name', label: 'Patient', formatter: 'patient' },
        { key: 'actions', label: 'Actions', width: '120px', formatter: 'actions' }
    ], allBeds, {
        emptyMessage: 'No beds found',
        csvExport: true,
        csvFilename: 'beds_admin.csv',
        formatters: {
            currency: (v) => `₹${v}`,
            bedStatus: (v) => {
                const map = { Free: 'badge-bed-free', Occupied: 'badge-bed-occupied', Cleaning: 'badge-bed-cleaning' };
                return `<span class="badge ${map[v] || 'bg-secondary'}">${v}</span>`;
            },
            patient: (v, row) => row.patient_name ? `${row.patient_name} (Visit ${row.visit_id})` : '—',
            actions: (v, row) => {
                if (row.bed_status === 'Cleaning') {
                    return `<button class="btn btn-sm btn-success mark-free-admin" data-id="${row.bed_id}">Mark Free</button>`;
                }
                return `<button class="btn btn-sm btn-outline-secondary set-status-admin" data-id="${row.bed_id}" data-status="${row.bed_status}">Set Status</button>`;
            }
        }
    });

    document.querySelectorAll('.mark-free-admin').forEach(btn => {
        btn.addEventListener('click', () => setBedStatus(btn.dataset.id, 'Free'));
    });
    document.querySelectorAll('.set-status-admin').forEach(btn => {
        btn.addEventListener('click', () => openSetBedStatusModal(btn.dataset.id, btn.dataset.status));
    });
}

function setupForms() {
    // Add Doctor
    const addDoctorForm = document.getElementById('addDoctorForm');
    if (addDoctorForm) addDoctorForm.addEventListener('submit', addDoctor);

    // Edit Doctor
    const editDoctorForm = document.getElementById('editDoctorForm');
    if (editDoctorForm) editDoctorForm.addEventListener('submit', submitEditDoctor);

    // Add Medicine
    const addMedicineForm = document.getElementById('addMedicineAdminForm');
    if (addMedicineForm) addMedicineForm.addEventListener('submit', addMedicine);

    // Add Bed
    const addBedForm = document.getElementById('addBedAdminForm');
    if (addBedForm) addBedForm.addEventListener('submit', addBed);

    // Set Bed Status
    const setBedStatusForm = document.getElementById('setBedStatusForm');
    if (setBedStatusForm) setBedStatusForm.addEventListener('submit', submitSetBedStatus);
}

async function addDoctor(e) {
    e.preventDefault();
    const form = e.target;
    const formData = new FormData(form);
    const data = Object.fromEntries(formData);
    data.consultation_fee = parseFloat(data.consultation_fee);

    const envelope = await post('/doctors', data);
    handle(envelope, {
        successToast: true,
        errorToast: true,
        inspectorEl: document.getElementById('inspectorBody'),
        onSuccess: () => {
            bootstrap.Modal.getInstance(form.closest('.modal'))?.hide();
            form.reset();
            fetchDoctors();
        }
    });
}

function editDoctor(id) {
    const doctor = doctorsData.find(d => d.doctor_id == id);
    if (!doctor) return;

    document.getElementById('editDoctorId').value = doctor.doctor_id;
    document.getElementById('editDoctorName').value = doctor.doctor_name;
    document.getElementById('editDoctorDepartment').value = doctor.department;
    document.getElementById('editDoctorSpecialization').value = doctor.specialization || '';
    document.getElementById('editDoctorFee').value = doctor.consultation_fee;
    document.getElementById('editDoctorShift').value = doctor.shift;

    new bootstrap.Modal(document.getElementById('editDoctorModal')).show();
}

async function submitEditDoctor(e) {
    e.preventDefault();
    const form = e.target;
    const formData = new FormData(form);
    const data = Object.fromEntries(formData);
    const id = data.doctor_id;
    data.consultation_fee = parseFloat(data.consultation_fee);
    delete data.doctor_id;

    const envelope = await put(`/doctors/${id}`, data);
    handle(envelope, {
        successToast: true,
        errorToast: true,
        inspectorEl: document.getElementById('inspectorBody'),
        onSuccess: () => {
            bootstrap.Modal.getInstance(form.closest('.modal'))?.hide();
            fetchDoctors();
        }
    });
}

async function addMedicine(e) {
    e.preventDefault();
    const form = e.target;
    const formData = new FormData(form);
    const data = Object.fromEntries(formData);
    data.stock_quantity = parseInt(data.stock_quantity, 10);
    data.price_per_unit = parseFloat(data.price_per_unit);

    const envelope = await post('/medicines', data);
    handle(envelope, {
        successToast: true,
        errorToast: true,
        inspectorEl: document.getElementById('inspectorBody'),
        onSuccess: () => {
            bootstrap.Modal.getInstance(form.closest('.modal'))?.hide();
            form.reset();
            fetchMedicines();
        }
    });
}

async function addBed(e) {
    e.preventDefault();
    const form = e.target;
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

function openSetBedStatusModal(bedId, currentStatus) {
    const modal = new bootstrap.Modal(document.getElementById('setBedStatusModal'));
    document.getElementById('setBedStatusId').value = bedId;
    document.getElementById('setBedStatusDisplay').value = bedId;
    document.getElementById('setBedStatusSelect').value = currentStatus;
    modal.show();
}

async function submitSetBedStatus(e) {
    e.preventDefault();
    const form = e.target;
    const formData = new FormData(form);
    const data = Object.fromEntries(formData);
    const bedId = data.bed_id;
    delete data.bed_id;

    const envelope = await post(`/beds/${bedId}/status`, data);
    handle(envelope, {
        successToast: true,
        errorToast: true,
        inspectorEl: document.getElementById('inspectorBody'),
        onSuccess: () => {
            bootstrap.Modal.getInstance(form.closest('.modal'))?.hide();
            fetchBeds();
        }
    });
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

window.pageRefresh = loadAdmin;