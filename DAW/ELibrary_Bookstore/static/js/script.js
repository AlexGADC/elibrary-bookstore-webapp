// --- Protecție CSRF ---
// Serverul pune token-ul într-un cookie numit "csrf_token". Îl citim de acolo și îl trimitem
// înapoi în header-ul "X-CSRF-Token" la orice cerere care modifică date.
function getCsrfToken() {
    const match = document.cookie.match(/(?:^|; )csrf_token=([^;]*)/);
    return match ? decodeURIComponent(match[1]) : '';
}

// Folosește apiFetch() în loc de fetch() pentru cererile către server:
// adaugă automat header-ul CSRF la POST / PUT / PATCH / DELETE.
function apiFetch(url, options = {}) {
    const method = (options.method || 'GET').toUpperCase();
    const headers = { ...(options.headers || {}) };

    if (!['GET', 'HEAD', 'OPTIONS'].includes(method)) {
        headers['X-CSRF-Token'] = getCsrfToken();
    }

    return fetch(url, { ...options, headers });
}

document.addEventListener('DOMContentLoaded', () => {
    const loginForm = document.getElementById('loginForm');
    const errorDiv = document.getElementById('errorMessage');

    if (loginForm) {
        loginForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            errorDiv.style.display = 'none';

            const email = document.getElementById('email').value;
            const password = document.getElementById('password').value;
            const captchaResponse = grecaptcha.getResponse(); 

            if (!captchaResponse) {
                errorDiv.innerText = "Te rugăm să bifezi căsuța de securitate (CAPTCHA).";
                errorDiv.style.display = "block";
                return;
            }

            const formData = new URLSearchParams();
            formData.append('username', email);
            formData.append('password', password);
            formData.append('captcha', captchaResponse); 

            try {
                const response = await apiFetch('/auth/login', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/x-www-form-urlencoded',
                    },
                    body: formData
                });

                const data = await response.json();

               if (response.ok) {
                    localStorage.setItem('token', data.access_token);
                    
                    window.location.href = '/catalog';
                } else {
                    errorDiv.innerText = data.detail || "Eroare la logare.";
                    errorDiv.style.display = 'block';
                    grecaptcha.reset(); 
                }
            } catch (err) {
                console.error(err);
                errorDiv.innerText = "Eroare de conexiune la server.";
                errorDiv.style.display = 'block';
            }
        });
    }
});

    const booksContainer = document.getElementById('booksContainer');
    if (booksContainer) {
        const token = localStorage.getItem('token');
        if (!token) {
            window.location.href = '/'; 
        }

        async function fetchBooks() {
            try {
                const response = await fetch('/books/', {
                    method: 'GET',
                    headers: {
                        'Authorization': `Bearer ${token}`
                    }
                });

                if (response.status === 401) {
                    localStorage.removeItem('token');
                    window.location.href = '/';
                    return;
                }

                const books = await response.json();
                
                booksContainer.replaceChildren();

                if (books.length === 0) {
                    const emptyMessage = document.createElement('p');
                    emptyMessage.style.textAlign = 'center';
                    emptyMessage.style.width = '100%';
                    emptyMessage.textContent = 'Nu există cărți în baza de date momentan.';
                    booksContainer.appendChild(emptyMessage);
                    return;
                }

                books.forEach(book => {
                    const card = document.createElement('div');
                    card.className = 'book-card';
                    
                    const authorName = book.author_name || "Autor necunoscut";

                    let imagePath = book.cover_image_url;
                    let imgSrc = '';

                    if (imagePath) {
                        let cleanPath = imagePath.replace(/\\/g, '/');
                        
                        if (!cleanPath.includes('uploads')) {
                            cleanPath = 'uploads/covers/' + cleanPath;
                        }
                        
                        imgSrc = cleanPath.startsWith('/') ? cleanPath : '/' + cleanPath;
                    } else {
                        imgSrc = '/static/img/no-cover.svg';
                    }

                    // Protecție XSS: NU construim HTML din datele cărții (fără innerHTML).
                    // Creăm elementele cu createElement și punem datele cu textContent / proprietăți,
                    // astfel încât browserul le tratează mereu ca text simplu, niciodată ca și cod.
                    const coverContainer = document.createElement('div');
                    coverContainer.className = 'book-cover-container';

                    const cover = document.createElement('img');
                    cover.className = 'book-cover';
                    cover.src = imgSrc;
                    cover.alt = `Copertă ${book.title}`;
                    coverContainer.appendChild(cover);

                    const title = document.createElement('h3');
                    title.className = 'book-title';
                    title.textContent = book.title;

                    const author = document.createElement('p');
                    author.className = 'book-author';
                    author.textContent = `de ${authorName}`;

                    const price = document.createElement('p');
                    price.className = 'book-price';
                    price.textContent = `${book.price} RON`;

                    const stock = document.createElement('p');
                    stock.style.fontSize = '12px';
                    stock.style.color = 'gray';
                    stock.textContent = `Stoc: ${book.stock}`;

                    card.append(coverContainer, title, author, price, stock);
                    booksContainer.appendChild(card);
                });

            } catch (err) {
                console.error("Eroare la aducerea cărților:", err);
                document.getElementById('catalogMessage').innerText = "Eroare de conexiune la server.";
                document.getElementById('catalogMessage').style.display = 'block';
            }
        }

        fetchBooks();

        const logoutBtn = document.getElementById('logoutBtn');
        if (logoutBtn) {
            logoutBtn.addEventListener('click', () => {
                localStorage.removeItem('token'); 
                window.location.href = '/'; 
            });
        }
    }