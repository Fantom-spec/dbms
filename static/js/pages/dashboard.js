/**
 * Dashboard Page Script
 * Loads KPIs, charts, low stock, recent audit
 */

import { get, handle } from '../api.js';
import { renderTable } from '../tables.js';
import { barChart, pieChart, chartFromReport } from '../charts.js';
import { formatCurrency, formatNumber, getTriageLabel } from '../app.js';

let dashboardData = null;

export async function loadDashboard() {
    showLoading(true);

    const envelope = await get('/dashboard');
    handle(envelope, {
        successToast: false,
        errorToast: true,
        onSuccess: (env) => {
            dashboardData = env.data;
            renderDashboard(env.data);
        },
        onError: () => {
            showEmptyState();
        }
    });

    showLoading(false);
}

function renderDashboard(data) {
    if (!data) return;

    // Render KPI Cards
    renderKpiCards(data.kpis);

    // Render Charts
    renderCharts(data);

    // Render Low Stock Table
    renderLowStockTable(data.low_stock);

    // Render Recent Audit Table
    renderRecentAuditTable(data.recent_audit);
}

function renderKpiCards(kpis) {
    const container = document.getElementById('kpiCards');
    if (!container) return;

    const cards = [
        { key: 'patients', label: 'Total Patients', icon: 'bi-people', color: 'primary', value: kpis.patients },
        { key: 'active_visits', label: 'Active Visits', icon: 'bi-person-lines-fill', color: 'info', value: kpis.active_visits },
        { key: 'free_beds', label: 'Free Beds', icon: 'bi-bed', color: 'success', value: kpis.free_beds },
        { key: 'waiting_emergency', label: 'Waiting Emergency', icon: 'bi-exclamation-triangle', color: 'danger', value: kpis.waiting_emergency },
        { key: 'pending_bills', label: 'Pending Bills', icon: 'bi-file-text', color: 'warning', value: kpis.pending_bills },
        { key: 'pending_amount', label: 'Pending Amount', icon: 'bi-cash-stack', color: 'danger', value: kpis.pending_amount, isCurrency: true },
        { key: 'low_stock_count', label: 'Low Stock Items', icon: 'bi-capsule', color: 'secondary', value: kpis.low_stock_count }
    ];

    container.innerHTML = cards.map(card => `
        <div class="col-12 col-sm-6 col-md-4 col-lg-3">
            <div class="card kpi-card h-100">
                <div class="card-body d-flex align-items-center">
                    <div class="kpi-icon bg-${card.color} text-white me-3">
                        <i class="bi ${card.icon}"></i>
                    </div>
                    <div>
                        <div class="kpi-value">${card.isCurrency ? formatCurrency(card.value) : formatNumber(card.value)}</div>
                        <div class="kpi-label">${card.label}</div>
                    </div>
                </div>
            </div>
        </div>
    `).join('');
}

function renderCharts(data) {
    // Bed Occupancy Chart
    if (data.bed_occupancy && data.bed_occupancy.length) {
        const labels = data.bed_occupancy.map(d => d.ward_type);
        const values = data.bed_occupancy.map(d => d.occupancy_pct);
        barChart('bedOccupancyChart', labels, [{
            label: 'Occupancy %',
            data: values,
            backgroundColor: values.map(v => v > 50 ? '#dc3545' : v > 0 ? '#ffc107' : '#198754')
        }], {
            plugins: { legend: { display: false } },
            scales: { y: { max: 100, ticks: { callback: v => v + '%' } } }
        });
    }

    // Triage Chart
    if (data.triage && data.triage.length) {
        const labels = data.triage.map(d => getTriageLabel(d.triage_level));
        const values = data.triage.map(d => d.count);
        const colors = data.triage.map(d => getTriageColor(d.triage_level));
        pieChart('triageChart', labels, values, {
            plugins: {
                legend: { position: 'bottom' },
                tooltip: { callbacks: { label: ctx => `${ctx.label}: ${ctx.parsed}` } }
            }
        });
    }
}

function getTriageColor(level) {
    const map = { 1: '#dc3545', 2: '#fd7e14', 3: '#ffc107', 4: '#198754' };
    return map[level] || '#6c757d';
}

function renderLowStockTable(lowStock) {
    const container = document.getElementById('lowStockTable');
    if (!container) return;

    if (!lowStock || lowStock.length === 0) {
        container.innerHTML = '<div class="empty-state p-3"><i class="bi bi-check-circle text-success" style="font-size: 2rem;"></i><p class="mb-0">No low stock medicines</p></div>';
        return;
    }

    renderTable(container, [
        { key: 'medicine_name', label: 'Medicine' },
        { key: 'stock_quantity', label: 'Stock', align: 'center' },
        { key: 'price_per_unit', label: 'Price', align: 'right', formatter: 'currency' }
    ], lowStock, {
        emptyMessage: 'No low stock medicines',
        csvExport: false
    });
}

function renderRecentAuditTable(audit) {
    const container = document.getElementById('recentAuditTable');
    if (!container) return;

    if (!audit || audit.length === 0) {
        container.innerHTML = '<div class="empty-state p-3"><p class="mb-0">No recent audit entries</p></div>';
        return;
    }

    renderTable(container, [
        { key: 'log_id', label: 'ID', align: 'center', width: '60px' },
        { key: 'table_name', label: 'Table', width: '100px' },
        { key: 'action_type', label: 'Action', width: '100px' },
        { key: 'changed_by', label: 'By', width: '100px' },
        { key: 'change_time', label: 'Time', width: '160px' },
        { key: 'description', label: 'Description' }
    ], audit, {
        emptyMessage: 'No recent audit entries',
        csvExport: false
    });
}

function showLoading(show) {
    const mainContent = document.getElementById('mainContent');
    if (mainContent) {
        if (show) {
            mainContent.classList.add('position-relative');
            if (!mainContent.querySelector('.loading-overlay')) {
                const overlay = document.createElement('div');
                overlay.className = 'loading-overlay';
                overlay.innerHTML = '<div class="spinner-border text-primary" role="status"><span class="visually-hidden">Loading...</span></div>';
                mainContent.appendChild(overlay);
            }
        } else {
            const overlay = mainContent.querySelector('.loading-overlay');
            if (overlay) overlay.remove();
            mainContent.classList.remove('position-relative');
        }
    }
}

function showEmptyState() {
    const container = document.getElementById('kpiCards');
    if (container) {
        container.innerHTML = '<div class="col-12"><div class="empty-state"><i class="bi bi-exclamation-triangle"></i><p>Failed to load dashboard data</p></div></div>';
    }
}

// Initialize on load
document.addEventListener('DOMContentLoaded', loadDashboard);

// Expose refresh function for role changes
window.pageRefresh = loadDashboard;