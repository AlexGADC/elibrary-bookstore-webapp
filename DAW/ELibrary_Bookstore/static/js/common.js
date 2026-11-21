// =====================================================================
// common.js - loaded on every page.
// Holds the helpers the other scripts use: talking to the server,
// remembering who is logged in, showing messages, and the menu.
// =====================================================================

// ---------- Login state ----------
// After a successful login the server gives us a token; we keep it in the browser.
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
// The server puts a token in a cookie named "csrf_token". We read it and send it back
// in the "X-CSRF-Token" header on every request that changes data.
function getCsrfToken() {
    const match = document.cookie.match(/(?:^|; )csrf_token=([^;]*)/);
    return match ? decodeURIComponent(match[1]) : '';
}

// ---------- Talking to the server ----------
// Use apiFetch() instead of fetch(). It adds, automatically:
//   - the CSRF header on POST / PUT / PATCH / DELETE
//   - the login token, if the visitor is logged in
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

// Turns an error answer from the server into one readable sentence.
async function readErrorMessage(response, fallback = 'Something went wrong. Please try again.') {
    try {
        const data = await response.json();

        if (typeof data.detail === 'string') {
            return data.detail;
        }

        // Validation errors arrive as a list, one entry per wrong field
        if (Array.isArray(data.detail)) {
            return data.detail
                .map((problem) => {
                    const field = problem.loc ? problem.loc[problem.loc.length - 1] : '';
                    return field ? `${field}: ${problem.msg}` : problem.msg;
                })
                .join(' ');
        }
    } catch (error) {
        // The answer was not JSON; use the fallback below
    }

    return fallback;
}

// ---------- Messages ----------
// Shows a message box. "type" is 'error' or 'success'. The text is always inserted
// as plain text, never as HTML, so it cannot be used to inject code into the page.
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

// ---------- Menu ----------
document.addEventListener('DOMContentLoaded', () => {
    // Show "Log in / Create account" to visitors and "Log out" to logged-in users
    const loggedIn = isLoggedIn();

    document.querySelectorAll('[data-auth="guest"]').forEach((element) => {
        element.hidden = loggedIn;
    });

    document.querySelectorAll('[data-auth="user"]').forEach((element) => {
        element.hidden = !loggedIn;
    });

    // Highlight the menu link of the page we are on
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

    // The three-line button opens and closes the menu on phones
    const navToggle = document.getElementById('navToggle');
    const siteNav = document.getElementById('siteNav');

    if (navToggle && siteNav) {
        navToggle.addEventListener('click', () => {
            const isOpen = siteNav.classList.toggle('is-open');
            navToggle.setAttribute('aria-expanded', String(isOpen));
        });
    }
});
