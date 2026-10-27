/**
 * Main Application Module
 * Handles global UI: sidebar, role switcher, reset, inspector panel, navigation
 */

import { get, formatCurrency } from './api.js';
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
    initInspectorSwitch();
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
 * Role display is sourced from the authenticated server session; users cannot
 * switch their own permissions in the browser.
 */
function initRoleSwitcher() {
    const roleDisplay = document.getElementById('currentRole');
    if (roleDisplay) roleDisplay.textContent = 'Signed in';
}

function switchRole(role) {
    currentRole = role;
    const roleDisplay = document.getElementById('currentRole');
    if (roleDisplay) roleDisplay.textContent = role;
}

function updateNavVisibility() {
    // Server-side route and API authorization are authoritative. Navigation is
    // not used as a security boundary.
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
        const authResp = await get('/auth/me');
        if (authResp.ok && authResp.data && authResp.data.authenticated && authResp.data.user) {
            const u = authResp.data.user;
            const sidebarName = document.getElementById('sidebarUserName');
            const sidebarRole = document.getElementById('sidebarUserRole');
            if (sidebarName) sidebarName.textContent = u.full_name || u.username;
            if (sidebarRole) sidebarRole.textContent = u.role;
        }

        const envelope = await get('/meta');
        if (envelope.ok && envelope.data) {
            if (envelope.data.role) {
                switchRole(envelope.data.role);
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
