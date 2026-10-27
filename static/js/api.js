/**
 * API Helper Module
 * Provides callApi() for fetching from /api/* endpoints with the standard envelope format.
 * Never throws on ok:false - returns the envelope for caller to handle.
 */

const API_BASE = window.__API_BASE__ || '/api';

/**
 * Core API call function
 * @param {string} method - HTTP method (GET, POST, PUT, DELETE)
 * @param {string} url - API endpoint path (e.g., '/patients', '/appointments')
 * @param {object|null} body - Request body for POST/PUT
 * @returns {Promise<object>} Parsed envelope {ok, message, data, error, inspector}
 */
export async function callApi(method, url, body = null) {
    const token = getAuthToken();
    const headers = {
        'Content-Type': 'application/json',
        'X-Role': getCurrentRole(),
        'X-Requested-With': 'HospitalApp'      // CSRF defence: required by the server on writes
    };

    if (token) {
        headers['Authorization'] = `Bearer ${token}`;
        headers['X-Session-Token'] = token;
    }

    const options = {
        method: method.toUpperCase(),
        headers,
        credentials: 'include' // Supports cookies across subdomains or origins
    };

    if (body !== null) {
        options.body = JSON.stringify(body);
    }

    try {
        const response = await fetch(`${API_BASE}${url}`, options);

        if (response.status === 401 && !url.startsWith('/auth/')) {
            // Unauthorized on protected route: clear local token & redirect if in main app
            clearAuth();
            if (window.location.pathname !== '/login') {
                window.location.href = `/login?next=${encodeURIComponent(window.location.pathname)}`;
            }
        }

        let envelope;
        try {
            envelope = await response.json();
        } catch (parseErr) {
            envelope = null;
        }
        if (!envelope || typeof envelope !== 'object' || !('ok' in envelope)) {
            return {
                ok: false, message: `Unexpected server response (HTTP ${response.status})`, data: null, inspector: null,
                error: { kind: 'internal', code: 'BAD_RESPONSE', constraint: null, detail: `HTTP ${response.status}` }
            };
        }
        return envelope;
    } catch (err) {
        console.error(`API call failed: ${method} ${url}`, err);
        return {
            ok: false,
            message: 'Cannot reach server',
            error: { kind: 'internal', code: 'NETWORK_ERROR', constraint: null, detail: err.message },
            data: null,
            inspector: null
        };
    }
}


/**
 * Convenience methods
 */
export const get = (url) => callApi('GET', url);
export const post = (url, body) => callApi('POST', url, body);
export const put = (url, body) => callApi('PUT', url, body);
export const del = (url) => callApi('DELETE', url);

/**
 * Authentication storage helpers
 */
export function getAuthToken() {
    try { return localStorage.getItem('hospital_token') || null; } catch (e) { return null; }
}

export function setAuthToken(token) {
    try { localStorage.setItem('hospital_token', token); } catch (e) {}
}

export function clearAuth() {
    try {
        localStorage.removeItem('hospital_token');
        localStorage.removeItem('hospital_user');
        localStorage.removeItem('hospital_role');
    } catch (e) {}
}

export async function logout() {
    try {
        await post('/auth/logout');
    } catch (e) {}
    clearAuth();
    window.location.href = '/login';
}

/**
 * Get current role from localStorage or default
 */
export function getCurrentRole() {
    try { return localStorage.getItem('hospital_role') || 'Admin'; } catch (e) { return 'Admin'; }
}

/**
 * Set current role in localStorage
 */
export function setCurrentRole(role) {
    try { localStorage.setItem('hospital_role', role); } catch (e) { /* storage unavailable */ }
}


/**
 * Handle envelope response - shows toast, renders inspector, returns ok status
 * @param {object} envelope - API response envelope
 * @param {object} options - { successToast: boolean, inspectorEl: HTMLElement, errorToast: boolean }
 * @returns {boolean} envelope.ok
 */
export function handle(envelope, options = {}) {
    const {
        successToast = true,
        errorToast = true,
        inspectorEl = null,
        onSuccess = null,
        onError = null
    } = options;

    if (envelope.ok) {
        if (successToast && envelope.message) {
            showToast(envelope.message, 'success');
        }
        if (envelope.inspector && inspectorEl) {
            renderInspector(envelope.inspector, inspectorEl);
        }
        if (onSuccess) onSuccess(envelope);
        return true;
    } else {
        if (errorToast) {
            let msg = envelope.message || 'Operation failed';
            if (envelope.error && envelope.error.code) {
                msg += ` (${envelope.error.code})`;
            }
            if (envelope.error && envelope.error.constraint) {
                msg += ` [${envelope.error.constraint}]`;
            }
            showToast(msg, 'danger');
        }
        if (envelope.inspector && inspectorEl) {
            renderInspector(envelope.inspector, inspectorEl);
        }
        if (onError) onError(envelope);
        return false;
    }
}

/**
 * Show toast notification (delegates to toast.js)
 */
function showToast(message, type = 'info') {
    if (window.toast && typeof window.toast.show === 'function') {
        window.toast.show(message, type);
    } else {
        // Fallback if toast not loaded yet
        console.log(`[${type.toUpperCase()}] ${message}`);
    }
}

/**
 * Render inspector panel (delegates to inspector.js)
 */
function renderInspector(inspector, container) {
    if (window.inspector && typeof window.inspector.render === 'function') {
        window.inspector.render(inspector, container);
    } else {
        // Fallback: store for later rendering
        container.dataset.pendingInspector = JSON.stringify(inspector);
    }
}

/**
 * Format currency
 */
export function formatCurrency(value) {
    if (value === null || value === undefined) return '—';
    return new Intl.NumberFormat('en-IN', {
        style: 'currency',
        currency: 'INR',
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
    }).format(value);
}

/**
 * Format date/time
 */
export function formatDateTime(value) {
    if (!value) return '—';
    return value.replace('T', ' ');
}

export function formatDate(value) {
    if (!value) return '—';
    return value.split(' ')[0];
}

/**
 * Debounce utility
 */
export function debounce(fn, delay) {
    let timeoutId;
    return (...args) => {
        clearTimeout(timeoutId);
        timeoutId = setTimeout(() => fn(...args), delay);
    };
}

/**
 * Prevent double form submission
 * Disables the submit button and adds a submitting state
 * @param {HTMLFormElement} form - The form element
 * @param {Function} handler - The async handler function
 * @returns {Function} Event handler that prevents double submission
 */
export function preventDoubleSubmit(form, handler) {
    let isSubmitting = false;
    return async (e) => {
        e.preventDefault();
        if (isSubmitting) return;
        isSubmitting = true;
        
        const submitBtn = form.querySelector('button[type="submit"]');
        const originalHtml = submitBtn ? submitBtn.innerHTML : '';
        if (submitBtn) {
            submitBtn.disabled = true;
            submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Submitting...';
        }
        
        try {
            await handler(e);
        } finally {
            isSubmitting = false;
            if (submitBtn) {
                submitBtn.disabled = false;
                submitBtn.innerHTML = originalHtml;
            }
        }
    };
}

/**
 * Generate UUID for temporary IDs
 */
export function generateId() {
    return Date.now().toString(36) + Math.random().toString(36).substr(2);
}