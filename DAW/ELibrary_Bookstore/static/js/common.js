// =====================================================================
// common.js - loaded on every page.
// Holds the helpers the other scripts use: talking to the server,
// remembering who is logged in, showing messages, and the menu.
// =====================================================================

// ---------- Login state ----------
function getToken() {
    return localStorage.getItem('token');
}

function setToken(token) {
    localStorage.setItem('token', token);
}

function clearToken() {
    localStorage.removeItem('token');
}

function isLoggedIn() {
    return Boolean(getToken());
}

// ---------- CSRF protection ----------
function getCsrfToken() {
    const match = document.cookie.match(/(?:^|; )csrf_token=([^;]*)/);
    return match ? decodeURIComponent(match[1]) : '';
}

// ---------- Talking to the server ----------
function apiFetch(url, options = {}) {
    const method = (options.method || 'GET').toUpperCase();
    const headers = { ...(options.headers || {}) };

    if (!['GET', 'HEAD', 'OPTIONS'].includes(method)) {
        headers['X-CSRF-Token'] = getCsrfToken();
    }

    const token = getToken();
    if (token && !headers['Authorization']) {
        headers['Authorization'] = `Bearer ${token}`;
    }

    return fetch(url, { ...options, headers });
}

async function readErrorMessage(response, fallback = 'Something went wrong. Please try again.') {
    try {
        const data = await response.json();

        if (typeof data.detail === 'string') {
            return data.detail;
        }

        if (Array.isArray(data.detail)) {
            return data.detail
                .map((problem) => {
                    const field = problem.loc ? problem.loc[problem.loc.length - 1] : '';
                    return field ? `${field}: ${problem.msg}` : problem.msg;
                })
                .join(' ');
        }
    } catch (error) {
    }

    return fallback;
}

// ---------- Messages ----------
function showMessage(element, text, type = 'error') {
    if (!element) {
        return;
    }

    element.textContent = text;
    element.className = `alert alert-${type}`;
    element.hidden = false;
}

function hideMessage(element) {
    if (element) {
        element.hidden = true;
    }
}

// ---------- Visitor or logged-in user ----------
function applyAuthState() {
    const loggedIn = isLoggedIn();

    document.querySelectorAll('[data-auth="guest"]').forEach((element) => {
        element.hidden = loggedIn;
    });

    document.querySelectorAll('[data-auth="user"]').forEach((element) => {
        element.hidden = !loggedIn;
    });
}

// ---------- Menu ----------
document.addEventListener('DOMContentLoaded', () => {
    applyAuthState();

    document.querySelectorAll('.site-nav .nav-link').forEach((link) => {
        if (link.getAttribute('href') === window.location.pathname) {
            link.classList.add('is-current');
            link.setAttribute('aria-current', 'page');
        }
    });

    const logoutButton = document.getElementById('logoutBtn');
    if (logoutButton) {
        logoutButton.addEventListener('click', () => {
            clearToken();
            window.location.href = '/catalog';
        });
    }

    const navToggle = document.getElementById('navToggle');
    const siteNav = document.getElementById('siteNav');

    if (navToggle && siteNav) {
        navToggle.addEventListener('click', () => {
            const isOpen = siteNav.classList.toggle('is-open');
            navToggle.setAttribute('aria-expanded', String(isOpen));
        });
    }
});
