/**
 * Billing Page Script
 * Generate bills, view bills, record payments, pending bills cursor
 */

import { get, post, handle, preventDoubleSubmit } from '../api.js';
import { renderTable } from '../tables.js';
import { openInspector, formatCurrency, getBillStatusBadgeClass, showEmptyState } from '../app.js';

let billsData = [];
let pendingBillsData = null;

export async function loadBilling() {
    await fetchDischargedVisits();
    await fetchBills('');
    await fetchPendingBills();
    setupForms();
}

async function fetchDischargedVisits() {
    const envelope = await get('/visits?status=Discharged');
    handle(envelope, {
        successToast: false,
        errorToast: true,
        onSuccess: (env) => {
            populateVisitSelect(env.data || []);
        }
    });
}

function populateVisitSelect(visits) {
    const select = document.getElementById('billVisitId');
    if (!select) return;

    const current = select.value;
    select.innerHTML = '<option value="">Select a discharged visit...</option>';
    visits.forEach(v => {
        if (!v.bill) { // Only show visits without bills
            const opt = document.createElement('option');
            opt.value = v.visit_id;
            opt.textContent = `Visit ${v.visit_id} - ${v.patient_name} (${v.visit_type})`;
            select.appendChild(opt);
        }
    });
    if (current) select.value = current;
}

async function fetchBills(statusFilter) {
    const query = statusFilter ? `?status=${statusFilter}` : '';
    const envelope = await get(`/bills${query}`);
    handle(envelope, {
        successToast: false,
        errorToast: true,
        onSuccess: (env) => {
            billsData = env.data || [];
            renderBillsTable(billsData);
        }
    });
}

function renderBillsTable(data) {
    const container = document.getElementById('billsTableContainer');
    if (!container) return;

    if (!data || data.length === 0) {
        showEmptyState(container, 'No bills found');
        return;
    }

    renderTable(container, [
        { key: 'bill_id', label: 'Bill ID', align: 'center', width: '80px' },
        { key: 'patient_name', label: 'Patient' },
        { key: 'total_amount', label: 'Amount', align: 'right', width: '120px', formatter: 'currency' },
        { key: 'payment_status', label: 'Status', width: '110px', formatter: 'billStatus' },
        { key: 'payment_mode', label: 'Mode', width: '100px' },
        { key: 'created_at', label: 'Created', width: '180px' },
        { key: 'actions', label: 'Actions', width: '160px', formatter: 'actions' }
    ], data, {
        emptyMessage: 'No bills found',
        csvExport: true,
        csvFilename: 'bills.csv',
        formatters: {
            currency: (value) => formatCurrency(value),
            billStatus: (value) => `<span class="badge ${getBillStatusBadgeClass(value)}">${value}</span>`,
            actions: (value, row) => {
                const actions = [];
                actions.push(`<button class="btn btn-sm btn-outline-info view-bill" data-id="${row.bill_id}" title="View">View</button>`);
                if (row.payment_status === 'Pending') {
                    actions.push(`<button class="btn btn-sm btn-outline-success pay-bill" data-id="${row.bill_id}" data-amount="${row.total_amount}" title="Record Payment">Pay</button>`);
                }
                return `<div class="btn-group btn-group-sm" role="group">${actions.join('')}</div>`;
            }
        }
    });

    document.querySelectorAll('.view-bill').forEach(btn => {
        btn.addEventListener('click', () => viewBillSummary(btn.dataset.id));
    });
    document.querySelectorAll('.pay-bill').forEach(btn => {
        btn.addEventListener('click', () => openPayBillModal(btn.dataset.id, btn.dataset.amount));
    });
}

async function fetchPendingBills() {
    const minAmount = document.getElementById('pendingMinAmount')?.value || 0;
    const envelope = await get(`/bills/pending?min_amount=${minAmount}`);
    handle(envelope, {
        successToast: false,
        errorToast: true,
        onSuccess: (env) => {
            pendingBillsData = env.data;
            renderPendingBills(env.data);
        }
    });
}

function renderPendingBills(data) {
    const container = document.getElementById('pendingBillsContainer');
    if (!container) return;

    if (!data || !data.rows || data.rows.length === 0) {
        container.innerHTML = '<div class="empty-state"><i class="bi bi-check-circle text-success" style="font-size: 2rem;"></i><p class="mb-0">No pending bills</p></div>';
        return;
    }

    let html = `
        <div class="mb-3">
            <div class="row g-3">
                <div class="col-md-3"><strong>Total Pending:</strong> ${data.count} bills</div>
                <div class="col-md-3"><strong>Total Amount:</strong> ${formatCurrency(data.total)}</div>
            </div>
        </div>
    `;

    // Console output
    if (data.console_lines && data.console_lines.length) {
        html += `
            <div class="card mb-3">
                <div class="card-header"><strong>Cursor Output (DBMS_OUTPUT)</strong></div>
                <div class="card-body p-0">
                    <pre class="mb-0 p-3 bg-dark text-light" style="font-size: 0.8rem; max-height: 200px; overflow: auto;">${data.console_lines.join('\n')}</pre>
                </div>
            </div>
        `;
    }

    // Table
    if (data.columns && data.rows.length) {
        html += '<div class="table-responsive"><table class="table table-sm table-hover mb-0"><thead><tr>';
        data.columns.forEach(col => html += `<th>${col}</th>`);
        html += '</tr></thead><tbody>';
        data.rows.forEach(row => {
            html += '<tr>';
            row.forEach((cell, idx) => {
                const col = data.columns[idx];
                let display = cell === null ? '<span class="text-muted">—</span>' : cell;
                if (col?.toLowerCase().includes('amount') || col?.toLowerCase().includes('total')) {
                    display = formatCurrency(cell);
                }
                html += `<td>${display}</td>`;
            });
            html += '</tr>';
        });
        html += '</tbody></table></div>';
    }

    container.innerHTML = html;
}

function setupForms() {
    // Generate Bill Form
    const genBillForm = document.getElementById('generateBillForm');
    if (genBillForm) {
        genBillForm.addEventListener('submit', preventDoubleSubmit(genBillForm, generateBill));
    }

    // Pay Bill Form
    const payBillForm = document.getElementById('payBillForm');
    if (payBillForm) {
        payBillForm.addEventListener('submit', preventDoubleSubmit(payBillForm, payBill));
    }

    // Bill Status Filter
    document.querySelectorAll('input[name="billStatusFilter"]').forEach(radio => {
        radio.addEventListener('change', (e) => {
            fetchBills(e.target.value);
        });
    });

    // Refresh buttons
    const refreshPendingBtn = document.getElementById('refreshPendingBillsBtn');
    if (refreshPendingBtn) {
        refreshPendingBtn.addEventListener('click', fetchPendingBills);
    }

    const pendingMinAmount = document.getElementById('pendingMinAmount');
    if (pendingMinAmount) {
        pendingMinAmount.addEventListener('change', fetchPendingBills);
    }
}

async function generateBill() {
    const form = document.getElementById('generateBillForm');
    const formData = new FormData(form);
    const data = Object.fromEntries(formData);
    data.visit_id = parseInt(data.visit_id, 10);

    const envelope = await post(`/visits/${data.visit_id}/bill`, {});
    handle(envelope, {
        successToast: true,
        errorToast: true,
        inspectorEl: document.getElementById('inspectorBody'),
        onSuccess: (env) => {
            form.reset();
            showBillPreview(env.data);
            fetchBills('');
            fetchPendingBills();
            fetchDischargedVisits();
        }
    });
}

function showBillPreview(bill) {
    const previewEl = document.getElementById('billPreview');
    const contentEl = document.getElementById('billPreviewContent');
    const itemisedEl = document.getElementById('billItemisedCard');
    const itemisedContent = document.getElementById('billItemisedContent');

    if (previewEl && contentEl) {
        contentEl.innerHTML = `
            <div class="row g-2">
                <div class="col-6"><strong>Bill ID:</strong></div><div class="col-6">${bill.bill_id}</div>
                <div class="col-6"><strong>Consultation:</strong></div><div class="col-6">${formatCurrency(bill.consultation_charge)}</div>
                <div class="col-6"><strong>Medicine:</strong></div><div class="col-6">${formatCurrency(bill.medicine_charge)}</div>
                <div class="col-6"><strong>Bed Charges:</strong></div><div class="col-6">${formatCurrency(bill.bed_charge)}</div>
                <div class="col-6"><strong>Total:</strong></div><div class="col-6 fw-bold text-success">${formatCurrency(bill.total_amount)}</div>
                <div class="col-6"><strong>Status:</strong></div><div class="col-6"><span class="badge ${getBillStatusBadgeClass(bill.payment_status)}">${bill.payment_status}</span></div>
            </div>
        `;
        previewEl.style.display = 'block';
    }

    if (itemisedEl && itemisedContent) {
        itemisedContent.innerHTML = `
            <div class="row g-2">
                <div class="col-6"><strong>Consultation Charge:</strong></div><div class="col-6">${formatCurrency(bill.consultation_charge)} (Doctor fee)</div>
                <div class="col-6"><strong>Medicine Charge:</strong></div><div class="col-6">${formatCurrency(bill.medicine_charge)} (fn_medicine_cost)</div>
                <div class="col-6"><strong>Bed Charge:</strong></div><div class="col-6">${formatCurrency(bill.bed_charge)} (daily_charge × fn_days_stayed)</div>
                <hr class="col-12">
                <div class="col-6"><strong>Total Amount:</strong></div><div class="col-6 fw-bold fs-5">${formatCurrency(bill.total_amount)}</div>
                <div class="col-6"><strong>Status:</strong></div><div class="col-6"><span class="badge ${getBillStatusBadgeClass(bill.payment_status)}">${bill.payment_status}</span></div>
            </div>
        `;
        itemisedEl.style.display = 'block';
    }
}

function openPayBillModal(billId, amount) {
    const modal = new bootstrap.Modal(document.getElementById('payBillModal'));
    document.getElementById('payBillId').value = billId;
    document.getElementById('payBillAmount').value = formatCurrency(amount);
    modal.show();
}

async function payBill() {
    const form = document.getElementById('payBillForm');
    const formData = new FormData(form);
    const data = Object.fromEntries(formData);
    data.bill_id = parseInt(data.bill_id, 10);

    const envelope = await post(`/bills/${data.bill_id}/pay`, { payment_mode: data.payment_mode });
    handle(envelope, {
        successToast: true,
        errorToast: true,
        inspectorEl: document.getElementById('inspectorBody'),
        onSuccess: () => {
            bootstrap.Modal.getInstance(form.closest('.modal'))?.hide();
            form.reset();
            fetchBills('');
            fetchPendingBills();
        }
    });
}

async function viewBillSummary(billId) {
    const modal = new bootstrap.Modal(document.getElementById('billSummaryModal'));
    const contentEl = document.getElementById('billSummaryContent');

    contentEl.innerHTML = '<div class="text-center py-3"><div class="spinner-border"></div></div>';
    modal.show();

    // Fetch bill details from bills list
    const bill = billsData.find(b => b.bill_id == billId);
    if (bill) {
        contentEl.innerHTML = `
            <div class="row g-2">
                <div class="col-6"><strong>Bill ID:</strong></div><div class="col-6">${bill.bill_id}</div>
                <div class="col-6"><strong>Patient:</strong></div><div class="col-6">${bill.patient_name}</div>
                <div class="col-6"><strong>Total Amount:</strong></div><div class="col-6 fw-bold">${formatCurrency(bill.total_amount)}</div>
                <div class="col-6"><strong>Status:</strong></div><div class="col-6"><span class="badge ${getBillStatusBadgeClass(bill.payment_status)}">${bill.payment_status}</span></div>
                <div class="col-6"><strong>Payment Mode:</strong></div><div class="col-6">${bill.payment_mode || '—'}</div>
                <div class="col-6"><strong>Created:</strong></div><div class="col-6">${bill.created_at}</div>
            </div>
        `;
    }
}

window.pageRefresh = loadBilling;