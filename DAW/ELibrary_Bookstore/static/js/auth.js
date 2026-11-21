// =====================================================================
// auth.js - the login page and the create-account page.
// Needs common.js (apiFetch, showMessage, setToken ...).
// =====================================================================

document.addEventListener('DOMContentLoaded', () => {
    const messageBox = document.getElementById('formMessage');
    const submitButton = document.getElementById('submitBtn');

    // Reads the answer of the "I'm not a robot" box. Returns '' if it was not ticked.
    function getCaptchaAnswer() {
        if (typeof grecaptcha === 'undefined' || typeof grecaptcha.getResponse !== 'function') {
            return '';
        }
        return grecaptcha.getResponse();
    }

    function resetCaptcha() {
        if (typeof grecaptcha !== 'undefined' && typeof grecaptcha.reset === 'function') {
            grecaptcha.reset();
        }
    }

    // Disables the button while we wait for the server, so the form is not sent twice
    function setBusy(isBusy, busyText, normalText) {
        submitButton.disabled = isBusy;
        submitButton.textContent = isBusy ? busyText : normalText;
    }

    // ---------- Log in ----------
    const loginForm = document.getElementById('loginForm');

    if (loginForm) {
        // Coming from the create-account page: confirm the account exists
        if (new URLSearchParams(window.location.search).get('registered') === '1') {
            showMessage(messageBox, 'Your account was created. You can log in now.', 'success');
        }

        loginForm.addEventListener('submit', async (event) => {
            event.preventDefault();
            hideMessage(messageBox);

            const email = document.getElementById('email').value.trim();
            const password = document.getElementById('password').value;
            const captchaAnswer = getCaptchaAnswer();

            if (!email || !password) {
                showMessage(messageBox, 'Please enter your email address and password.');
                return;
            }

            if (!captchaAnswer) {
                showMessage(messageBox, 'Please tick the "I\'m not a robot" box.');
                return;
            }

            const formData = new URLSearchParams();
            formData.append('username', email);
            formData.append('password', password);
            formData.append('captcha', captchaAnswer);

            setBusy(true, 'Logging in...', 'Log in');

            try {
                const response = await apiFetch('/auth/login', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                    body: formData
                });

                if (response.ok) {
                    const data = await response.json();
                    setToken(data.access_token);
                    window.location.href = '/catalog';
                    return;
                }

                showMessage(messageBox, await readErrorMessage(response, 'Could not log in.'));
                resetCaptcha();
            } catch (error) {
                console.error(error);
                showMessage(messageBox, 'Could not reach the server. Please try again.');
            }

            setBusy(false, 'Logging in...', 'Log in');
        });
    }

    // ---------- Create account ----------
    const registerForm = document.getElementById('registerForm');

    if (registerForm) {
        registerForm.addEventListener('submit', async (event) => {
            event.preventDefault();
            hideMessage(messageBox);

            const username = document.getElementById('username').value.trim();
            const email = document.getElementById('email').value.trim();
            const password = document.getElementById('password').value;
            const confirmPassword = document.getElementById('confirmPassword').value;
            const captchaAnswer = getCaptchaAnswer();

            if (username.length < 2) {
                showMessage(messageBox, 'Please enter your name.');
                return;
            }

            if (!email) {
                showMessage(messageBox, 'Please enter your email address.');
                return;
            }

            if (password.length < 8) {
                showMessage(messageBox, 'The password must have at least 8 characters.');
                return;
            }

            if (password !== confirmPassword) {
                showMessage(messageBox, 'The two passwords do not match.');
                return;
            }

            if (!captchaAnswer) {
                showMessage(messageBox, 'Please tick the "I\'m not a robot" box.');
                return;
            }

            setBusy(true, 'Creating account...', 'Create account');

            try {
                const response = await apiFetch('/auth/register', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ username, email, password, captcha: captchaAnswer })
                });

                if (response.ok) {
                    window.location.href = '/login?registered=1';
                    return;
                }

                showMessage(messageBox, await readErrorMessage(response, 'Could not create the account.'));
                resetCaptcha();
            } catch (error) {
                console.error(error);
                showMessage(messageBox, 'Could not reach the server. Please try again.');
            }

            setBusy(false, 'Creating account...', 'Create account');
        });
    }
});
