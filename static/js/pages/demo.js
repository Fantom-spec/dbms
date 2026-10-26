/**
 * Guided Demo Page Script
 * Runs T1-T6 demo steps with inspector
 */

import { get, post, handle } from '../api.js';
import { openInspector, closeInspector, render as renderInspector } from '../inspector.js';
import { showEmptyState, escapeHtml } from '../tables.js';

let demoSteps = [];
let demoState = { completed: [], context: {} };
let currentStepIndex = -1;
let runAllInterval = null;

export async function loadDemo() {
    await fetchDemoSteps();
    await fetchDemoState();
    renderStepper();
    setupControls();
    setupPresenterMode();
}

async function fetchDemoSteps() {
    const envelope = await get('/demo/steps');
    handle(envelope, {
        successToast: false,
        errorToast: true,
        onSuccess: (env) => {
            demoSteps = env.data || [];
        }
    });
}

async function fetchDemoState() {
    const envelope = await get('/demo/state');
    handle(envelope, {
        successToast: false,
        errorToast: true,
        onSuccess: (env) => {
            demoState = env.data || { completed: [], context: {} };
            updateStepperStatus();
        }
    });
}

function renderStepper() {
    const container = document.getElementById('demoStepper');
    if (!container) return;

    let html = '';
    demoSteps.forEach((txn, txnIdx) => {
        html += `
            <div class="list-group-item">
                <div class="fw-bold text-primary mb-1">${txn.transaction}: ${txn.title}</div>
                <small class="text-muted">${txn.goal}</small>
                <div class="mt-2">
        `;
        txn.steps.forEach((step, stepIdx) => {
            const globalIdx = getGlobalStepIndex(txnIdx, stepIdx);
            const isCompleted = demoState.completed.includes(step.id);
            const isCurrent = globalIdx === currentStepIndex;
            const statusClass = isCompleted ? 'text-success' : isCurrent ? 'text-primary fw-bold' : 'text-muted';

            html += `
                <div class="demo-step-item d-flex align-items-center gap-2 py-1 ${isCurrent ? 'bg-light rounded' : ''}" data-step-id="${step.id}" data-global-idx="${globalIdx}">
                    <span class="${statusClass}" style="width: 20px;">
                        ${isCompleted ? '<i class="bi bi-check-circle-fill"></i>' : '<i class="bi bi-circle"></i>'}
                    </span>
                    <span class="small flex-grow-1">${step.id}: ${step.title}</span>
                    <span class="badge bg-secondary">${step.role}</span>
                </div>
            `;
        });
        html += '</div></div>';
    });
    container.innerHTML = html;

    // Click to select step
    container.querySelectorAll('.demo-step-item').forEach(item => {
        item.addEventListener('click', () => {
            const globalIdx = parseInt(item.dataset.globalIdx, 10);
            selectStep(globalIdx);
        });
    });
}

function getGlobalStepIndex(txnIdx, stepIdx) {
    let idx = 0;
    for (let i = 0; i <= txnIdx; i++) {
        if (i === txnIdx) return idx + stepIdx;
        idx += demoSteps[i].steps.length;
    }
    return idx;
}

function getStepByGlobalIndex(globalIdx) {
    let idx = 0;
    for (const txn of demoSteps) {
        for (const step of txn.steps) {
            if (idx === globalIdx) return { step, txn };
            idx++;
        }
    }
    return null;
}

function updateStepperStatus() {
    document.querySelectorAll('.demo-step-item').forEach(item => {
        const stepId = item.dataset.stepId;
        const isCompleted = demoState.completed.includes(stepId);
        const iconEl = item.querySelector('span');
        if (iconEl) {
            iconEl.innerHTML = isCompleted ? '<i class="bi bi-check-circle-fill"></i>' : '<i class="bi bi-circle"></i>';
            iconEl.className = isCompleted ? 'text-success' : 'text-muted';
        }
        item.classList.remove('bg-light', 'text-primary', 'fw-bold');
    });

    if (currentStepIndex >= 0) {
        const currentItem = document.querySelector(`.demo-step-item[data-global-idx="${currentStepIndex}"]`);
        if (currentItem) {
            currentItem.classList.add('bg-light', 'rounded');
            const iconEl = currentItem.querySelector('span');
            if (iconEl) {
                iconEl.className = 'text-primary fw-bold';
            }
        }
    }
}

function selectStep(globalIdx) {
    const stepData = getStepByGlobalIndex(globalIdx);
    if (!stepData) return;

    currentStepIndex = globalIdx;
    const { step, txn } = stepData;

    updateStepperStatus();
    renderStepContent(step, txn);
    document.getElementById('demoStepFooter').style.display = 'flex';
}

function renderStepContent(step, txn) {
    const headerEl = document.getElementById('demoStepHeader');
    const contentEl = document.getElementById('demoStepContent');
    const runBtn = document.getElementById('runStepBtn');
    const nextBtn = document.getElementById('nextStepBtn');
    const prevBtn = document.getElementById('prevStepBtn');
    const inspectorContainer = document.getElementById('demoInspectorContainer');
    const inspectorBody = document.getElementById('demoInspectorBody');

    const isCompleted = demoState.completed.includes(step.id);
    const isFailedStep = ['T1.3', 'T2.3', 'T3.3', 'T4.3', 'T4.4', 'T6.2', 'T6.3'].includes(step.id);

    headerEl.innerHTML = `
        <div class="d-flex justify-content-between align-items-center">
            <div>
                <h5 class="mb-1">${step.id}: ${step.title}</h5>
                <span class="badge bg-secondary">${step.role}</span>
            </div>
            ${isCompleted ? '<span class="badge bg-success fs-6">Completed</span>' : ''}
        </div>
    `;

    let contentHtml = `
        <div class="mb-3">
            <h6>Narration</h6>
            <p>${escapeHtml(step.narration)}</p>
        </div>
        <div class="mb-3">
            <h6>Expected Outcome</h6>
            <ul class="mb-0">
                ${step.expect.map(e => `<li>${escapeHtml(e)}</li>`).join('')}
            </ul>
        </div>
    `;

    if (isCompleted) {
        contentHtml += `
            <div class="alert alert-success">
                <i class="bi bi-check-circle"></i> This step has already been completed.
            </div>
        `;
    } else if (isFailedStep) {
        contentHtml += `
            <div class="alert alert-warning">
                <i class="bi bi-exclamation-triangle"></i> <strong>This step is designed to fail.</strong> It demonstrates a constraint/trigger violation.
                The "Run Step" button will show a "Blocked as expected" banner, not an error toast.
            </div>
        `;
    }

    contentEl.innerHTML = contentHtml;

    // Inspector
    inspectorContainer.style.display = 'none';
    inspectorBody.innerHTML = '';

    // Buttons
    runBtn.disabled = isCompleted;
    runBtn.textContent = isCompleted ? 'Already Completed' : 'Run Step';
    runBtn.onclick = () => runStep(step);

    prevBtn.style.display = currentStepIndex > 0 ? 'inline-block' : 'none';
    prevBtn.onclick = () => selectStep(currentStepIndex - 1);

    nextBtn.style.display = (currentStepIndex < getTotalSteps() - 1) ? 'inline-block' : 'none';
    nextBtn.onclick = () => selectStep(currentStepIndex + 1);
}

function getTotalSteps() {
    return demoSteps.reduce((sum, txn) => sum + txn.steps.length, 0);
}

async function runStep(step) {
    const runBtn = document.getElementById('runStepBtn');
    const inspectorContainer = document.getElementById('demoInspectorContainer');
    const inspectorBody = document.getElementById('demoInspectorBody');
    const isFailedStep = ['T1.3', 'T2.3', 'T3.3', 'T4.3', 'T4.4', 'T6.2', 'T6.3'].includes(step.id);

    runBtn.disabled = true;
    runBtn.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Running...';

    const envelope = await post(`/demo/${step.id}/run`, {});
    handle(envelope, {
        successToast: !isFailedStep,
        errorToast: !isFailedStep,
        inspectorEl: inspectorBody,
        onSuccess: (env) => {
            inspectorContainer.style.display = 'block';
            renderInspector(env.inspector, inspectorBody);

            if (isFailedStep && env.ok === false) {
                showBlockedAsExpected(env, inspectorBody);
            }

            // Refresh state
            fetchDemoState().then(() => {
                updateStepperStatus();
                renderStepContent(step, demoSteps.find(t => t.steps.some(s => s.id === step.id)));
            });
        },
        onError: (env) => {
            inspectorContainer.style.display = 'block';
            renderInspector(env.inspector, inspectorBody);

            if (isFailedStep) {
                showBlockedAsExpected(env, inspectorBody);
            }
        }
    });

    runBtn.disabled = false;
    runBtn.innerHTML = '<i class="bi bi-play"></i> Run Step';
}

function showBlockedAsExpected(envelope, container) {
    const banner = document.createElement('div');
    banner.className = 'alert alert-warning border-warning mb-3';
    banner.innerHTML = `
        <h6 class="alert-heading"><i class="bi bi-shield-check"></i> Blocked as Expected</h6>
        <p class="mb-0">${envelope.message}</p>
        ${envelope.error?.code ? `<hr><small><strong>Error Code:</strong> ${envelope.error.code}</small>` : ''}
        ${envelope.error?.constraint ? `<small class="d-block"><strong>Constraint:</strong> ${envelope.error.constraint}</small>` : ''}
    `;
    container.insertBefore(banner, container.firstChild);
}

function setupControls() {
    const runAllBtn = document.getElementById('runAllBtn');
    const pauseCheckbox = document.getElementById('pauseBetweenSteps');
    const resetBtn = document.getElementById('resetDemoBtn');

    if (runAllBtn) {
        runAllBtn.addEventListener('click', runAllSteps);
    }

    if (resetBtn) {
        resetBtn.addEventListener('click', resetDemo);
    }
}

async function runAllSteps() {
    const runAllBtn = document.getElementById('runAllBtn');
    const pauseCheckbox = document.getElementById('pauseBetweenSteps');
    const pauseBetween = pauseCheckbox?.checked !== false;

    runAllBtn.disabled = true;
    runAllBtn.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Running All...';

    const totalSteps = getTotalSteps();

    for (let i = 0; i < totalSteps; i++) {
        const stepData = getStepByGlobalIndex(i);
        if (!stepData) continue;

        const { step } = stepData;
        const isCompleted = demoState.completed.includes(step.id);

        if (isCompleted) {
            currentStepIndex = i;
            selectStep(i);
            if (pauseBetween) await sleep(500);
            continue;
        }

        currentStepIndex = i;
        selectStep(i);

        // Wait for step to complete
        await new Promise(resolve => {
            const checkComplete = setInterval(() => {
                if (demoState.completed.includes(step.id)) {
                    clearInterval(checkComplete);
                    resolve();
                }
            }, 200);
        });

        if (pauseBetween) await sleep(1000);

        // Re-fetch state
        await fetchDemoState();
    }

    runAllBtn.disabled = false;
    runAllBtn.innerHTML = '<i class="bi bi-play-fill"></i> Run All Steps';
}

function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

async function resetDemo() {
    if (!confirm('Reset the demo? This will clear all progress and restore the database.')) return;

    const resetBtn = document.getElementById('resetDemoBtn');
    resetBtn.disabled = true;
    resetBtn.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Resetting...';

    const envelope = await post('/reset', {});
    handle(envelope, {
        successToast: true,
        errorToast: true,
        onSuccess: () => {
            demoState = { completed: [], context: {} };
            currentStepIndex = -1;
            renderStepper();
            document.getElementById('demoStepHeader').innerHTML = '<h5 class="mb-0">Select a step from the left to begin</h5>';
            document.getElementById('demoStepContent').innerHTML = '<div class="text-center py-5 text-muted"><i class="bi bi-play-circle" style="font-size: 3rem;"></i><p class="mt-2">Choose a demo step from the sidebar to see details and run it.</p></div>';
            document.getElementById('demoStepFooter').style.display = 'none';
            document.getElementById('demoInspectorContainer').style.display = 'none';
        }
    });

    resetBtn.disabled = false;
    resetBtn.innerHTML = '<i class="bi bi-arrow-clockwise"></i> Reset Demo';
}

function setupPresenterMode() {
    const toggle = document.getElementById('presenterMode');
    const sidebar = document.getElementById('sidebar');
    const mainWrapper = document.querySelector('.main-wrapper');

    if (toggle) {
        toggle.addEventListener('change', (e) => {
            const enabled = e.target.checked;
            document.body.classList.toggle('presenter-mode', enabled);

            if (enabled) {
                sidebar.style.transform = 'translateX(-100%)';
                mainWrapper.style.marginLeft = '0';
                document.documentElement.style.fontSize = '18px';
            } else {
                sidebar.style.transform = '';
                mainWrapper.style.marginLeft = '';
                document.documentElement.style.fontSize = '';
            }
        });
    }
}

window.pageRefresh = loadDemo;