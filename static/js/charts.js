/**
 * Chart.js Wrapper Module
 * Provides barChart, pieChart, stackedBar helpers using Chart.js v4
 */

let chartInstances = {};

/**
 * Destroy existing chart for a canvas
 */
function destroyChart(canvasId) {
    if (chartInstances[canvasId]) {
        chartInstances[canvasId].destroy();
        delete chartInstances[canvasId];
    }
}

/**
 * Create or update a bar chart
 * @param {string} canvasId - Canvas element ID
 * @param {Array} labels - X-axis labels
 * @param {Array} datasets - Array of {label, data, backgroundColor, borderColor}
 * @param {object} options - Chart.js options
 */
export function barChart(canvasId, labels, datasets, options = {}) {
    const ctx = document.getElementById(canvasId);
    if (!ctx) {
        console.warn(`Canvas ${canvasId} not found`);
        return;
    }

    destroyChart(canvasId);

    const defaultOptions = {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
            legend: { display: datasets.length > 1, position: 'bottom' },
            tooltip: { mode: 'index', intersect: false }
        },
        scales: {
            y: { beginAtZero: true, ticks: { precision: 0 } },
            x: { ticks: { maxRotation: 45, minRotation: 0 } }
        }
    };

    chartInstances[canvasId] = new Chart(ctx, {
        type: 'bar',
        data: { labels, datasets },
        options: { ...defaultOptions, ...options }
    });

    return chartInstances[canvasId];
}

/**
 * Create or update a pie chart
 */
export function pieChart(canvasId, labels, data, options = {}) {
    const ctx = document.getElementById(canvasId);
    if (!ctx) {
        console.warn(`Canvas ${canvasId} not found`);
        return;
    }

    destroyChart(canvasId);

    const defaultOptions = {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
            legend: { position: 'bottom' },
            tooltip: { callbacks: { label: ctx => `${ctx.label}: ${ctx.parsed}` } }
        }
    };

    chartInstances[canvasId] = new Chart(ctx, {
        type: 'pie',
        data: {
            labels,
            datasets: [{
                data,
                backgroundColor: [
                    '#dc3545', '#fd7e14', '#ffc107', '#198754',
                    '#0dcaf0', '#6f42c1', '#e83e8c', '#20c997'
                ],
                borderWidth: 1,
                borderColor: '#fff'
            }]
        },
        options: { ...defaultOptions, ...options }
    });

    return chartInstances[canvasId];
}

/**
 * Create or update a stacked bar chart
 */
export function stackedBar(canvasId, labels, datasets, options = {}) {
    const ctx = document.getElementById(canvasId);
    if (!ctx) {
        console.warn(`Canvas ${canvasId} not found`);
        return;
    }

    destroyChart(canvasId);

    const defaultOptions = {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
            legend: { position: 'bottom' },
            tooltip: { mode: 'index', intersect: false }
        },
        scales: {
            x: { stacked: true },
            y: { stacked: true, beginAtZero: true }
        }
    };

    chartInstances[canvasId] = new Chart(ctx, {
        type: 'bar',
        data: { labels, datasets },
        options: { ...defaultOptions, ...options }
    });

    return chartInstances[canvasId];
}

/**
 * Create chart from API report chart hint
 * @param {string} canvasId
 * @param {object} chartHint - {type, label_col, value_cols} from API
 * @param {object} reportData - {columns[], rows[][]}
 */
export function chartFromReport(canvasId, chartHint, reportData) {
    if (!chartHint || !reportData || !reportData.rows.length) {
        destroyChart(canvasId);
        const ctx = document.getElementById(canvasId);
        if (ctx) ctx.style.display = 'none';
        return null;
    }

    const ctx = document.getElementById(canvasId);
    if (ctx) ctx.style.display = 'block';

    const labelColIdx = reportData.columns.indexOf(chartHint.label_col);
    const valueColIndices = chartHint.value_cols.map(c => reportData.columns.indexOf(c));

    if (labelColIdx === -1 || valueColIndices.some(i => i === -1)) {
        console.warn('Chart columns not found in report data', chartHint, reportData.columns);
        return null;
    }

    const labels = reportData.rows.map(r => r[labelColIdx]);

    if (chartHint.type === 'pie') {
        const data = reportData.rows.map(r => r[valueColIndices[0]]);
        return pieChart(canvasId, labels, data);
    } else if (chartHint.type === 'bar') {
        const datasets = valueColIndices.map((idx, i) => ({
            label: reportData.columns[idx],
            data: reportData.rows.map(r => r[idx]),
            backgroundColor: getColor(i)
        }));
        return barChart(canvasId, labels, datasets);
    } else if (chartHint.type === 'stacked_bar') {
        const datasets = valueColIndices.map((idx, i) => ({
            label: reportData.columns[idx],
            data: reportData.rows.map(r => r[idx]),
            backgroundColor: getColor(i)
        }));
        return stackedBar(canvasId, labels, datasets);
    }

    return null;
}

function getColor(index) {
    const colors = [
        '#2c7be5', '#198754', '#dc3545', '#ffc107',
        '#0dcaf0', '#6f42c1', '#e83e8c', '#fd7e14',
        '#20c997', '#6c757d', '#343a40'
    ];
    return colors[index % colors.length];
}

/**
 * Destroy all charts
 */
export function destroyAllCharts() {
    Object.keys(chartInstances).forEach(id => destroyChart(id));
}

// Auto-destroy on page unload
window.addEventListener('beforeunload', destroyAllCharts);

export default { barChart, pieChart, stackedBar, chartFromReport, destroyChart, destroyAllCharts };