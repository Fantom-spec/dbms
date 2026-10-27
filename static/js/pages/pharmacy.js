/**
 * Pharmacy Page Script
 * Medicine inventory, restock, prescriptions
 */

import { get, post, del, handle, preventDoubleSubmit } from '../api.js';
import { renderTable } from '../tables.js';
import { openInspector, formatCurrency, showEmptyState } from '../app.js';

let medicinesData = [];
let prescriptionsData = [];

export async function loadPharmacy() {
    await fetchMedicines();
    await fetchLowStock();
    await loadMedicineSelect();
    setupForms();
}

async function fetchMedicines() {
    const envelope = await get('/medicines');
    handle(envelope, {
        successToast: false,
        errorToast: true,
        onSuccess: (env) => {
            medicinesData = env.data || [];
            renderMedicinesTable(medicinesData);
        },
        onError: () => showEmptyState(document.getElementById('medicinesTableContainer'), 'Failed to load medicines')
    });
}

function renderMedicinesTable(data) {
    const container = document.getElementById('medicinesTableContainer');
    if (!container) return;

    if (!data || data.length === 0) {
        showEmptyState(container, 'No medicines found');
        return;
    }

    renderTable(container, [
        { key: 'medicine_id', label: 'ID', align: 'center', width: '70px' },
        { key: 'medicine_name', label: 'Medicine' },
        { key: 'stock_quantity', label: 'Stock', align: 'center', width: '90px', formatter: 'stock' },
        { key: 'price_per_unit', label: 'Price (₹)', align: 'right', width: '110px', formatter: 'currency' },
        { key: 'actions', label: 'Actions', width: '150px', formatter: 'actions' }
    ], data, {
        emptyMessage: 'No medicines found',
        csvExport: true,
        csvFilename: 'medicines.csv',
        formatters: {
            stock: (value, row) => {
                const cls = value < 20 ? 'text-danger fw-bold' : '';
                return `<span class="${cls}">${value}</span>`;
            },
            currency: (value) => formatCurrency(value),
            actions: (value, row) => `
                <div class="btn-group btn-group-sm" role="group">
                    <button class="btn btn-outline-success restock-btn" data-id="${row.medicine_id}" data-stock="${row.stock_quantity}" title="Restock">
                        <i class="bi bi-plus-circle"></i> Restock
                    </button>
                </div>
            `
        }
    });

    document.querySelectorAll('.restock-btn').forEach(btn => {
        btn.addEventListener('click', () => openRestockModal(btn.dataset.id, btn.dataset.stock));
    });
}

async function fetchLowStock() {
    const envelope = await get('/medicines/low-stock');
    handle(envelope, {
        successToast: false,
        errorToast: true,
        onSuccess: (env) => {
            renderLowStockList(env.data || []);
            updateLowStockCount(env.data?.length || 0);
        }
    });
}

function renderLowStockList(data) {
    const container = document.getElementById('lowStockList');
    if (!container) return;

    if (!data || data.length === 0) {
        container.innerHTML = '<div class="p-3 text-center text-success"><i class="bi bi-check-circle" style="font-size: 2rem;"></i><p class="mb-0">All medicines well stocked</p></div>';
        return;
    }

    let html = '<ul class="list-group list-group-flush">';
    data.forEach(med => {
        const badgeClass = med.stock_quantity === 0 ? 'bg-danger' : med.stock_quantity < 10 ? 'bg-warning text-dark' : 'bg-info';
        html += `
            <li class="list-group-item d-flex justify-content-between align-items-center">
                <div>
                    <strong>${med.medicine_name}</strong>
                    <small class="text-muted ms-2">ID: ${med.medicine_id}</small>
                </div>
                <span class="badge ${badgeClass}">${med.stock_quantity} units</span>
            </li>
        `;
    });
    html += '</ul>';
    container.innerHTML = html;
}

function updateLowStockCount(count) {
    const el = document.getElementById('lowStockCount');
    if (el) el.textContent = count;
}

async function loadMedicineSelect() {
    const envelope = await get('/medicines');
    if (envelope.ok && envelope.data) {
        const select = document.getElementById('rxMedicineId');
        if (select) {
            const current = select.value;
            select.innerHTML = '<option value="">Select medicine...</option>';
            envelope.data.forEach(m => {
                const opt = document.createElement('option');
                opt.value = m.medicine_id;
                opt.textContent = `${m.medicine_name} (Stock: ${m.stock_quantity}, ₹${m.price_per_unit})`;
                opt.dataset.stock = m.stock_quantity;
                opt.dataset.price = m.price_per_unit;
                select.appendChild(opt);
            });
            if (current) select.value = current;
        }
    }
}

function setupForms() {
    // Quick Prescription Form
    const rxForm = document.getElementById('quickPrescriptionForm');
    if (rxForm) {
        rxForm.addEventListener('submit', preventDoubleSubmit(rxForm, addPrescription));
    }

    // Add Medicine Form
    const addMedForm = document.getElementById('addMedicineForm');
    if (addMedForm) {
        addMedForm.addEventListener('submit', preventDoubleSubmit(addMedForm, addMedicine));
    }

    // Add Medicine Admin Form
    const addMedAdminForm = document.getElementById('addMedicineAdminForm');
    if (addMedAdminForm) {
        addMedAdminForm.addEventListener('submit', preventDoubleSubmit(addMedAdminForm, addMedicine));
    }

    // Refresh buttons
    const refreshMedBtn = document.getElementById('refreshMedicinesBtn');
    if (refreshMedBtn) refreshMedBtn.addEventListener('click', () => { fetchMedicines(); fetchLowStock(); });

    const refreshRxBtn = document.getElementById('refreshPrescriptionsBtn');
    if (refreshRxBtn) refreshRxBtn.addEventListener('click', () => fetchPrescriptionsForVisit());
}

function openRestockModal(medicineId, currentStock) {
    const quantity = prompt(`Restock medicine ID ${medicineId} (current stock: ${currentStock}). Enter quantity to add:`, '10');
    if (quantity === null) return;
    const qty = parseInt(quantity, 10);
    if (isNaN(qty) || qty <= 0) return alert('Invalid quantity');

    restockMedicine(medicineId, qty);
}

async function restockMedicine(medicineId, quantity) {
    const envelope = await post(`/medicines/${medicineId}/restock`, { quantity });
    handle(envelope, {
        successToast: true,
        errorToast: true,
        inspectorEl: document.getElementById('inspectorBody'),
        onSuccess: () => {
            fetchMedicines();
            fetchLowStock();
            loadMedicineSelect();
        }
    });
}

async function addMedicine() {
    const form = document.querySelector('#addMedicineForm, #addMedicineAdminForm');
    if (!form) return;
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
            fetchLowStock();
            loadMedicineSelect();
        }
    });
}

async function addPrescription() {
    const form = document.getElementById('quickPrescriptionForm');
    if (!form) return;
    const formData = new FormData(form);
    const data = Object.fromEntries(formData);
    data.visit_id = parseInt(data.visit_id, 10);
    data.medicine_id = parseInt(data.medicine_id, 10);
    data.duration_days = parseInt(data.duration_days, 10);
    data.quantity = parseInt(data.quantity, 10);

    const envelope = await post('/prescriptions', data);
    handle(envelope, {
        successToast: true,
        errorToast: true,
        inspectorEl: document.getElementById('inspectorBody'),
        onSuccess: () => {
            form.reset();
            fetchPrescriptionsForVisit();
        }
    });
}

function fetchPrescriptionsForVisit() {
    const visitId = document.getElementById('rxVisitId')?.value;
    if (!visitId) return;

    document.getElementById('rxVisitDisplay').textContent = `(Visit ${visitId})`;

    get(`/visits/${visitId}/prescriptions`).then(envelope => {
        handle(envelope, {
            successToast: false,
            errorToast: true,
            onSuccess: (env) => {
                prescriptionsData = env.data || [];
                renderPrescriptionsTable(prescriptionsData);
            }
        });
    });
}

function renderPrescriptionsTable(data) {
    const container = document.getElementById('prescriptionsTableContainer');
    if (!container) return;

    if (!data || data.length === 0) {
        showEmptyState(container, 'No prescriptions for this visit');
        return;
    }

    renderTable(container, [
        { key: 'prescription_id', label: 'Rx ID', align: 'center', width: '80px' },
        { key: 'medicine_name', label: 'Medicine' },
        { key: 'dosage', label: 'Dosage' },
        { key: 'duration_days', label: 'Days', align: 'center', width: '70px' },
        { key: 'quantity', label: 'Qty', align: 'center', width: '70px' },
        { key: 'price_per_unit', label: 'Price', align: 'right', width: '100px', formatter: 'currency' },
        { key: 'actions', label: 'Actions', width: '100px', formatter: 'actions' }
    ], data, {
        emptyMessage: 'No prescriptions',
        csvExport: false,
        formatters: {
            currency: (value) => formatCurrency(value),
            actions: (value, row) => `
                <button class="btn btn-sm btn-outline-danger delete-rx" data-id="${row.prescription_id}" title="Delete" aria-label="Delete Prescription">
                    <i class="bi bi-trash"></i>
                </button>
            `
        }
    });

    document.querySelectorAll('.delete-rx').forEach(btn => {
        btn.addEventListener('click', () => deletePrescription(btn.dataset.id));
    });
}

async function deletePrescription(id) {
    if (!confirm('Delete this prescription? Stock will be restored.')) return;

    const envelope = await del(`/prescriptions/${id}`);
    handle(envelope, {
        successToast: true,
        errorToast: true,
        inspectorEl: document.getElementById('inspectorBody'),
        onSuccess: () => fetchPrescriptionsForVisit()
    });
}

window.pageRefresh = loadPharmacy;

// Initial load (module scripts run after the DOM is parsed, so this works whether or not DOMContentLoaded already fired)
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', loadPharmacy);
} else {
    loadPharmacy();
}
