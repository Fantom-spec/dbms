/**
 * Reports Page Script
 * 19 reports with SQL, results, charts
 */

import { get, handle } from '../api.js';
import { renderTable } from '../tables.js';
import { chartFromReport, destroyChart } from '../charts.js';

let reportsCatalogue = [];
let currentReport = null;

export async function loadReports() {
    await fetchReportsCatalogue();
    setupSearch();
    setupRunButton();
    setupCopySql();
}

async function fetchReportsCatalogue() {
    const envelope = await get('/reports');
    handle(envelope, {
        successToast: false,
        errorToast: true,
        onSuccess: (env) => {
            reportsCatalogue = env.data || [];
            renderReportsList(reportsCatalogue);
        }
    });
}

function renderReportsList(reports) {
    const select = document.getElementById('reportSelect');
    if (!select) return;

    // Group by concept
    const grouped = {};
    reports.forEach(r => {
        if (!grouped[r.concept]) grouped[r.concept] = [];
        grouped[r.concept].push(r);
    });

    let html = '';
    Object.entries(grouped).forEach(([concept, items]) => {
        html += `<optgroup label="${concept}">`;
        items.forEach(r => {
            html += `<option value="${r.id}">${r.label} - ${r.title}</option>`;
        });
        html += '</optgroup>';
    });
    select.innerHTML = html;

    select.addEventListener('change', onReportSelect);
}

function onReportSelect() {
    const select = document.getElementById('reportSelect');
    const reportId = select.value;
    const runBtn = document.getElementById('runReportBtn');
    const paramContainer = document.getElementById('reportParamContainer');
    const paramLabel = document.getElementById('reportParamLabel');
    const paramInput = document.getElementById('reportParam');

    if (!reportId) {
        runBtn.disabled = true;
        paramContainer.style.display = 'none';
        clearReportInfo();
        return;
    }

    const report = reportsCatalogue.find(r => r.id === reportId);
    if (!report) return;

    currentReport = report;
    runBtn.disabled = false;

    // Show parameter input if needed
    if (reportId === 'q01') {
        paramContainer.style.display = 'block';
        paramLabel.textContent = 'Patient Name';
        paramInput.placeholder = 'Enter patient name (default: Aakash Gupta)';
        paramInput.value = 'Aakash Gupta';
    } else {
        paramContainer.style.display = 'none';
    }

    // Update report info
    updateReportInfo(report);
}

function updateReportInfo(report) {
    const infoEl = document.getElementById('reportInfo');
    if (!infoEl) return;

    infoEl.innerHTML = `
        <div class="mb-2"><span class="badge bg-info text-dark">${report.concept}</span></div>
        <h6 class="mb-2">${report.title}</h6>
        <p class="small text-muted mb-0">${report.label}</p>
    `;
}

function clearReportInfo() {
    const infoEl = document.getElementById('reportInfo');
    if (infoEl) infoEl.innerHTML = '<p class="text-muted small">Select a report to see details.</p>';
}

function setupSearch() {
    const searchInput = document.getElementById('reportSearch');
    const select = document.getElementById('reportSelect');
    if (!searchInput || !select) return;

    searchInput.addEventListener('input', (e) => {
        const term = e.target.value.toLowerCase();
        Array.from(select.options).forEach(opt => {
            if (opt.tagName === 'OPTGROUP') return;
            const text = opt.textContent.toLowerCase();
            opt.style.display = text.includes(term) ? '' : 'none';
        });
    });
}

function setupRunButton() {
    const runBtn = document.getElementById('runReportBtn');
    if (runBtn) {
        runBtn.addEventListener('click', runReport);
    }
}

async function runReport() {
    if (!currentReport) return;

    const param = document.getElementById('reportParam')?.value;
    const runBtn = document.getElementById('runReportBtn');
    const tableContainer = document.getElementById('reportTableContainer');
    const sqlContainer = document.getElementById('reportSqlContainer');
    const chartContainer = document.getElementById('reportChartContainer');
    const titleEl = document.getElementById('reportResultTitle');
    const copyBtn = document.getElementById('copySqlBtn');

    runBtn.disabled = true;
    runBtn.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Running...';

    const envelope = await get(`/reports/${currentReport.id}${param ? '?param=' + encodeURIComponent(param) : ''}`);
    handle(envelope, {
        successToast: true,
        errorToast: true,
        onSuccess: (env) => {
            const data = env.data;
            if (!data) return;

            // Update title
            if (titleEl) titleEl.textContent = data.title;

            // Show SQL
            if (sqlContainer && data.sql) {
                document.getElementById('reportSql').textContent = data.sql;
                sqlContainer.style.display = 'block';
                if (copyBtn) copyBtn.style.display = 'inline-block';
            }

            // Show Chart
            if (chartContainer && data.chart) {
                chartFromReport('reportChart', data.chart, data);
                chartContainer.style.display = 'block';
            } else if (chartContainer) {
                chartContainer.style.display = 'none';
                destroyChart('reportChart');
            }

            // Render Results Table
            if (tableContainer && data.columns && data.rows) {
                renderTable(tableContainer, data.columns, data.rows, {
                    emptyMessage: 'No results',
                    csvExport: true,
                    csvFilename: `${currentReport.id}_${currentReport.title.replace(/\s+/g, '_')}.csv`
                });
            } else if (tableContainer) {
                showEmptyState(tableContainer, 'No results');
            }
        }
    });

    runBtn.disabled = false;
    runBtn.innerHTML = '<i class="bi bi-play"></i> Run Report';
}

function setupCopySql() {
    const copyBtn = document.getElementById('copySqlBtn');
    if (copyBtn) {
        copyBtn.addEventListener('click', () => {
            const sqlEl = document.getElementById('reportSql');
            if (sqlEl) {
                navigator.clipboard.writeText(sqlEl.textContent).then(() => {
                    copyBtn.innerHTML = '<i class="bi bi-check"></i> Copied!';
                    setTimeout(() => copyBtn.innerHTML = '<i class="bi bi-clipboard"></i> Copy SQL', 2000);
                });
            }
        });
    }
}

window.pageRefresh = loadReports;

// Initial load (module scripts run after the DOM is parsed, so this works whether or not DOMContentLoaded already fired)
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', loadReports);
} else {
    loadReports();
}
