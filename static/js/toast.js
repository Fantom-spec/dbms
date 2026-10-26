/**
 * Toast Notification Module
 * Bootstrap 5 toast wrapper with success/danger/info/warning types
 */

class ToastManager {
    constructor() {
        this.container = null;
        this.init();
    }

    init() {
        // Create container if not exists
        this.container = document.getElementById('toastContainer');
        if (!this.container) {
            this.container = document.createElement('div');
            this.container.id = 'toastContainer';
            this.container.className = 'toast-container position-fixed bottom-0 end-0 p-3';
            this.container.setAttribute('aria-live', 'polite');
            this.container.setAttribute('aria-atomic', 'true');
            document.body.appendChild(this.container);
        }
    }

    /**
     * Show a toast notification
     * @param {string} message - Message to display
     * @param {string} type - 'success' | 'danger' | 'warning' | 'info'
     * @param {number} delay - Auto-hide delay in ms (default 5000)
     */
    show(message, type = 'info', delay = 5000) {
        const toastEl = this.createToast(message, type);
        this.container.appendChild(toastEl);

        const toast = new bootstrap.Toast(toastEl, {
            delay: delay,
            autohide: true
        });
        toast.show();

        // Remove from DOM after hidden
        toastEl.addEventListener('hidden.bs.toast', () => {
            toastEl.remove();
        });
    }

    createToast(message, type) {
        const toastEl = document.createElement('div');
        toastEl.className = `toast align-items-center text-bg-${type} border-0 fade-in`;
        toastEl.setAttribute('role', 'alert');
        toastEl.setAttribute('aria-live', 'assertive');
        toastEl.setAttribute('aria-atomic', 'true');

        const iconMap = {
            success: 'bi-check-circle-fill',
            danger: 'bi-exclamation-triangle-fill',
            warning: 'bi-exclamation-triangle-fill',
            info: 'bi-info-circle-fill'
        };

        const icon = iconMap[type] || iconMap.info;

        toastEl.innerHTML = `
            <div class="d-flex">
                <div class="toast-body d-flex align-items-center gap-2">
                    <i class="bi ${icon} fs-5"></i>
                    <span>${this.escapeHtml(message)}</span>
                </div>
                <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
            </div>
        `;

        return toastEl;
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    success(message, delay) { return this.show(message, 'success', delay); }
    danger(message, delay) { return this.show(message, 'danger', delay); }
    warning(message, delay) { return this.show(message, 'warning', delay); }
    info(message, delay) { return this.show(message, 'info', delay); }
}

// Export singleton instance
const toast = new ToastManager();

// Make globally available for api.js fallback
window.toast = toast;

export default toast;
export { ToastManager };