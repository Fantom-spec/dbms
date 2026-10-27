        document.addEventListener('DOMContentLoaded', () => {
            const form = document.getElementById('loginForm');
            const alertEl = document.getElementById('loginAlert');
            const loginBtn = document.getElementById('loginBtn');
            const btnText = document.getElementById('loginBtnText');
            const btnSpinner = document.getElementById('loginBtnSpinner');
            const togglePassword = document.getElementById('togglePassword');
            const passwordInput = document.getElementById('passwordInput');
            const togglePasswordIcon = document.getElementById('togglePasswordIcon');
            const nextParam = document.getElementById('nextParam').value;

            // Password visibility toggle
            togglePassword.addEventListener('click', () => {
                const isPassword = passwordInput.getAttribute('type') === 'password';
                passwordInput.setAttribute('type', isPassword ? 'text' : 'password');
                togglePasswordIcon.className = isPassword ? 'bi bi-eye-slash' : 'bi bi-eye';
            });

            form.addEventListener('submit', async (e) => {
                e.preventDefault();
                alertEl.classList.add('d-none');
                alertEl.textContent = '';

                const username = document.getElementById('usernameInput').value.trim();
                const password = passwordInput.value;

                if (!username || !password) {
                    alertEl.textContent = 'Please provide both username and password.';
                    alertEl.classList.remove('d-none');
                    return;
                }

                loginBtn.disabled = true;
                btnText.classList.add('d-none');
                btnSpinner.classList.remove('d-none');

                try {
                    const resp = await fetch('/api/auth/login', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'X-Requested-With': 'HospitalApp'
                        },
                        credentials: 'same-origin',
                        body: JSON.stringify({ username, password })
                    });

                    const data = await resp.json();

                    if (resp.ok && data.ok) {
                        // Redirect to next or dashboard
                        const targetUrl = nextParam || '/';
                        window.location.href = targetUrl;
                    } else {
                        const errMsg = (data && data.error && data.error.detail) ||
                                       (data && data.message) ||
                                       'Login failed. Please check your credentials.';
                        alertEl.textContent = errMsg;
                        alertEl.classList.remove('d-none');
                    }
                } catch (err) {
                    alertEl.textContent = 'Unable to reach the server. Please try again.';
                    alertEl.classList.remove('d-none');
                } finally {
                    loginBtn.disabled = false;
                    btnText.classList.remove('d-none');
                    btnSpinner.classList.add('d-none');
                }
            });
        });
