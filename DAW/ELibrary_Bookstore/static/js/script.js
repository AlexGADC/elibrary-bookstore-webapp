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
                const response = await fetch('/auth/login', {
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
                
                booksContainer.innerHTML = '';

                if (books.length === 0) {
                    booksContainer.innerHTML = '<p style="text-align: center; width: 100%;">Nu există cărți în baza de date momentan.</p>';
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
                        imgSrc = 'data:image/svg+xml;charset=UTF-8,%3Csvg xmlns="http://www.w3.org/2000/svg" width="300" height="400" viewBox="0 0 300 400"%3E%3Crect fill="%23e0e0e0" width="300" height="400"/%3E%3Ctext fill="%23888" x="50%25" y="50%25" text-anchor="middle" font-family="sans-serif" font-size="16" dy=".3em"%3EFara Coperta%3C/text%3E%3C/svg%3E';
                    }

                    card.innerHTML = `
                        <div class="book-cover-container">
                            <img src="${imgSrc}" alt="Copertă ${book.title}" class="book-cover">
                        </div>
                        <h3 class="book-title">${book.title}</h3>
                        <p class="book-author">de ${authorName}</p>
                        <p class="book-price">${book.price} RON</p>
                        <p style="font-size: 12px; color: gray;">Stoc: ${book.stock}</p>
                    `;
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