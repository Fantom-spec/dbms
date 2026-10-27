/**
 * Main Application Module
 * Handles global UI: sidebar, role switcher, reset, inspector panel, navigation
 */

import { callApi, post, get, setCurrentRole, handle, formatCurrency } from './api.js';
import { openInspector, closeInspector } from './inspector.js';

// Global state
let currentRole = 'Admin';
let alwaysShowInspector = false;
let inspectorPanel = null;
let inspectorBody = null;

// Initialize on DOM ready
document.addEventListener('DOMContentLoaded', () => {
    detectIconFont();
    initSidebar();
    initRoleSwitcher();
    initInspectorSwitch();
    initResetButton();
    initInspectorPanel();
    initNavigationHighlight();
    loadMeta();
    restoreInspectorPreference();
});

/**
 * Initialize sidebar toggle
 */
function initSidebar() {
    const sidebar = document.getElementById('sidebar');
    const toggle = document.getElementById('sidebarToggle');
    const mainWrapper = document.querySelector('.main-wrapper');

    if (toggle && sidebar) {
        toggle.addEventListener('click', () => {
            sidebar.classList.toggle('open');
            mainWrapper.classList.toggle('expanded');
        });

        // Close sidebar on link click (mobile)
        document.querySelectorAll('.sidebar-nav .nav-link').forEach(link => {
            link.addEventListener('click', () => {
                if (window.innerWidth <= 1024) {
                    sidebar.classList.remove('open');
                }
            });
        });

        // Close on outside click (mobile)
        document.addEventListener('click', (e) => {
            if (window.innerWidth <= 1024 &&
                !sidebar.contains(e.target) &&
                !toggle.contains(e.target) &&
                sidebar.classList.contains('open')) {
                sidebar.classList.remove('open');
            }
        });
    }
}

/**
 * Initialize role switcher dropdown
 */
function initRoleSwitcher() {
    const dropdownItems = document.querySelectorAll('#roleDropdown + .dropdown-menu .dropdown-item');
    const roleDisplay = document.getElementById('currentRole');

    dropdownItems.forEach(item => {
        item.addEventListener('click', async (e) => {
            e.preventDefault();
            const role = item.dataset.role;
            await switchRole(role);
        });
    });

    // Load saved role
    const savedRole = localStorage.getItem('hospital_role');
    if (savedRole) {
        switchRole(savedRole, false); // Don't call API again, just update UI
    }
}

/**
 * Switch role via API and update UI
 */
async function switchRole(role, callApiEndpoint = true) {
    if (callApiEndpoint) {
        const envelope = await post('/role', { role });
        if (!envelope.ok) {
            handle(envelope, { errorToast: true });
            return;
        }
    }

    currentRole = role;
    setCurrentRole(role);

    // Update display
    const roleDisplay = document.getElementById('currentRole');
    if (roleDisplay) roleDisplay.textContent = role;

    // Update dropdown active state
    document.querySelectorAll('#roleDropdown + .dropdown-menu .dropdown-item').forEach(item => {
        item.classList.toggle('active', item.dataset.role === role);
    });

    // Hide/show nav items based on role
    updateNavVisibility(role);

    // Refresh current page if it has a refresh function
    if (window.pageRefresh) {
        window.pageRefresh();
    }
}

/**
 * Update navigation visibility based on role (ARCHITECTURE section 13)
 */
function updateNavVisibility(role) {
    const roleNavMap = {
        'Admin': ['dashboard', 'patients', 'appointments', 'emergency', 'beds', 'pharmacy', 'billing', 'reports', 'audit', 'demo', 'schema', 'admin'],
        'Receptionist': ['dashboard', 'patients', 'appointments', 'emergency', 'beds', 'demo', 'schema'],
        'Triage Nurse': ['dashboard', 'patients', 'appointments', 'emergency', 'beds', 'demo', 'schema'],
        'Doctor': ['dashboard', 'emergency', 'beds', 'pharmacy', 'demo', 'schema'],
        'Billing': ['dashboard', 'billing', 'reports', 'demo', 'schema']
    };

    const allowedPages = roleNavMap[role] || roleNavMap['Admin'];

    document.querySelectorAll('.sidebar-nav .nav-item').forEach(item => {
        const link = item.querySelector('.nav-link');
        if (link) {
            const page = link.dataset.page;
            item.style.display = allowedPages.includes(page) ? '' : 'none';
        }
    });
}

/**
 * Initialize inspector switch
 */
function initInspectorSwitch() {
    const switchEl = document.getElementById('inspectorSwitch');
    if (switchEl) {
        switchEl.addEventListener('change', (e) => {
            alwaysShowInspector = e.target.checked;
            localStorage.setItem('hospital_inspector_always', alwaysShowInspector);
            updateInspectorVisibility();
        });
    }
}

/**
 * Initialize reset button
 */
function initResetButton() {
    const resetBtn = document.getElementById('resetBtn');
    if (resetBtn) {
        resetBtn.addEventListener('click', async () => {
            if (!confirm('Reset the demo database? This will clear all demo progress and restore seed data.')) {
                return;
            }

            resetBtn.disabled = true;
            resetBtn.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Resetting...';

            try {
                const envelope = await post('/reset', { confirm: true });
                handle(envelope, {
                    successToast: true,
                    errorToast: true,
                    onSuccess: () => {
                        // Reset demo state
                        localStorage.removeItem('hospital_demo_state');
                        // Refresh all pages
                        if (window.pageRefresh) window.pageRefresh();
                        // Reset role to Admin
                        switchRole('Admin');
                    }
                });
            } finally {
                resetBtn.disabled = false;
                resetBtn.innerHTML = '<i class="bi bi-arrow-clockwise"></i> Reset';
            }
        });
    }
}

/**
 * Initialize inspector panel
 */
function initInspectorPanel() {
    inspectorPanel = document.getElementById('inspectorPanel');
    inspectorBody = document.getElementById('inspectorBody');

    const closeBtn = document.getElementById('inspectorClose');
    if (closeBtn) {
        closeBtn.addEventListener('click', () => {
            closeInspector();
            // Also turn off the "always show" switch
            const switchEl = document.getElementById('inspectorSwitch');
            if (switchEl) {
                switchEl.checked = false;
                alwaysShowInspector = false;
                localStorage.setItem('hospital_inspector_always', 'false');
            }
        });
    }
}


/**
 * Update inspector visibility based on switch
 */
function updateInspectorVisibility() {
    const pending = inspectorBody?.dataset.pendingInspector;
    if (pending) {
        try {
            const inspector = JSON.parse(pending);
            if (alwaysShowInspector) {
                openInspector(inspector);
            }
        } catch (e) {
            console.error('Failed to parse pending inspector', e);
        }
    }
}

/**
 * Restore inspector preference from localStorage
 */
function restoreInspectorPreference() {
    const saved = localStorage.getItem('hospital_inspector_always');
    if (saved === 'true') {
        alwaysShowInspector = true;
        const switchEl = document.getElementById('inspectorSwitch');
        if (switchEl) switchEl.checked = true;
    }
}

/**
 * Highlight active navigation item
 */
function initNavigationHighlight() {
    const currentPath = window.location.pathname;
    document.querySelectorAll('.sidebar-nav .nav-link').forEach(link => {
        const href = link.getAttribute('href');
        if (href === currentPath || (currentPath === '/' && href === '/')) {
            link.classList.add('active');
        }
    });
}

/**
 * Load meta data (role, counts) on page load
 */
async function loadMeta() {
    try {
        const envelope = await get('/meta');
        if (envelope.ok && envelope.data) {
            // Update role if provided
            if (envelope.data.role) {
                switchRole(envelope.data.role, false);
            }
        }
    } catch (e) {
        console.warn('Failed to load meta', e);
    }
}

/**
 * Format number with commas
 */
export function formatNumber(num) {
    if (num === null || num === undefined) return '—';
    return new Intl.NumberFormat('en-IN').format(num);
}

/**
 * Format percentage
 */
export function formatPercent(num) {
    if (num === null || num === undefined) return '—%';
    return `${num.toFixed(1)}%`;
}

/**
 * Get triage badge class
 */
export function getTriageBadgeClass(level) {
    const map = { 1: 'badge-triage-1', 2: 'badge-triage-2', 3: 'badge-triage-3', 4: 'badge-triage-4' };
    return map[level] || 'bg-secondary';
}

/**
 * Get triage label
 */
export function getTriageLabel(level) {
    const map = { 1: 'Critical', 2: 'Very Urgent', 3: 'Urgent', 4: 'Minor' };
    return map[level] || 'Unknown';
}

/**
 * Get bed status badge class
 */
export function getBedStatusBadgeClass(status) {
    const map = { Free: 'badge-bed-free', Occupied: 'badge-bed-occupied', Cleaning: 'badge-bed-cleaning' };
    return map[status] || 'bg-secondary';
}

/**
 * Get bill status badge class
 */
export function getBillStatusBadgeClass(status) {
    const map = { Paid: 'badge-bill-paid', Pending: 'badge-bill-pending' };
    return map[status] || 'bg-secondary';
}

/**
 * Get visit status badge class
 */
export function getVisitStatusBadgeClass(status) {
    const map = {
        Scheduled: 'badge-visit-scheduled',
        Waiting: 'badge-visit-waiting',
        'Under Treatment': 'badge-visit-under-treatment',
        Admitted: 'badge-visit-admitted',
        Discharged: 'badge-visit-discharged',
        Cancelled: 'badge-visit-cancelled'
    };
    return map[status] || 'bg-secondary';
}

/**
 * Get visit status label
 */
export function getVisitStatusLabel(status) {
    return status;
}

/**
 * Show loading state on element
 */
export function showLoading(element, show = true) {
    if (!element) return;
    if (show) {
        element.classList.add('position-relative');
        if (!element.querySelector('.loading-overlay')) {
            const overlay = document.createElement('div');
            overlay.className = 'loading-overlay';
            overlay.innerHTML = '<div class="spinner-border text-primary" role="status"><span class="visually-hidden">Loading...</span></div>';
            element.appendChild(overlay);
        }
    } else {
        const overlay = element.querySelector('.loading-overlay');
        if (overlay) overlay.remove();
        element.classList.remove('position-relative');
    }
}

/**
 * Show empty state in container
 */
export function showEmptyState(container, message = 'No data available', icon = 'bi-inbox') {
    if (!container) return;
    container.innerHTML = `
        <div class="empty-state">
            <i class="bi ${icon}"></i>
            <p>${escapeHtml(message)}</p>
        </div>
    `;
}

/**
 * Escape HTML
 */
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Export for use in page scripts
export {
    currentRole,
    alwaysShowInspector,
    openInspector,
    closeInspector,
    formatCurrency,
    switchRole,
    loadMeta
};

/** Degrade icons gracefully when the Bootstrap Icons font files are missing. */
function detectIconFont() {
    if (!document.fonts || !document.fonts.load) return;
    document.fonts.load('1em bootstrap-icons', '\uF3E8').then((faces) => {
        if (!faces || faces.length === 0) document.documentElement.classList.add('no-icon-font');
    }).catch(() => document.documentElement.classList.add('no-icon-font'));
}
