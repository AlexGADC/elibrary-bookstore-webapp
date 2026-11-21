// =====================================================================
// catalog.js - the book catalog page: loads the books, search and filters.
// Needs common.js (apiFetch, showMessage ...).
// =====================================================================

document.addEventListener('DOMContentLoaded', () => {
    const booksContainer = document.getElementById('booksContainer');
    const messageBox = document.getElementById('catalogMessage');
    const resultCount = document.getElementById('resultCount');
    const filtersForm = document.getElementById('catalogFilters');
    const searchInput = document.getElementById('searchInput');
    const categorySelect = document.getElementById('categorySelect');
    const formatSelect = document.getElementById('formatSelect');

    const PLACEHOLDER_COVER = '/static/img/no-cover.svg';

    // Puts one line of text in the grid (loading, nothing found ...)
    function showGridNote(text) {
        const note = document.createElement('p');
        note.className = 'grid-note';
        note.textContent = text;
        booksContainer.replaceChildren(note);
    }

    function getCoverAddress(book) {
        if (!book.cover_image_url) {
            return PLACEHOLDER_COVER;
        }

        let path = book.cover_image_url.replace(/\\/g, '/');
        if (!path.includes('uploads')) {
            path = 'uploads/covers/' + path;
        }
        return path.startsWith('/') ? path : '/' + path;
    }

    function createBadge(text, className) {
        const badge = document.createElement('span');
        badge.className = `badge ${className}`;
        badge.textContent = text;
        return badge;
    }

    // XSS protection: the card is built with createElement and textContent, never innerHTML,
    // so whatever is stored in a book's title or author is always shown as plain text.
    function createBookCard(book) {
        const card = document.createElement('article');
        card.className = 'book-card';

        const coverContainer = document.createElement('div');
        coverContainer.className = 'book-cover-container';

        const cover = document.createElement('img');
        cover.className = 'book-cover';
        cover.src = getCoverAddress(book);
        cover.alt = `Cover of ${book.title}`;
        cover.loading = 'lazy';
        cover.width = 300;
        cover.height = 450;
        cover.addEventListener('error', () => {
            if (!cover.src.endsWith(PLACEHOLDER_COVER)) {
                cover.src = PLACEHOLDER_COVER;
            }
        });
        coverContainer.appendChild(cover);

        const info = document.createElement('div');
        info.className = 'book-info';

        const title = document.createElement('h2');
        title.className = 'book-title';
        title.textContent = book.title;

        const author = document.createElement('p');
        author.className = 'book-author';
        author.textContent = `by ${book.author_name || 'Unknown author'}`;

        const badges = document.createElement('div');
        badges.className = 'book-badges';
        badges.appendChild(
            book.stock > 0
                ? createBadge('In stock', 'badge-in-stock')
                : createBadge('Out of stock', 'badge-out-of-stock')
        );
        if (book.is_digital) {
            badges.appendChild(createBadge('E-book', 'badge-digital'));
        }

        const meta = document.createElement('div');
        meta.className = 'book-meta';

        const price = document.createElement('p');
        price.className = 'book-price';
        price.textContent = `${Number(book.price).toFixed(2)} RON`;
        meta.appendChild(price);

        info.append(title, author, badges, meta);
        card.append(coverContainer, info);
        return card;
    }

    async function loadCategories() {
        try {
            const response = await apiFetch('/categories/');
            if (!response.ok) {
                return;
            }

            const categories = await response.json();
            categories.forEach((category) => {
                const option = document.createElement('option');
                option.value = category.id;
                option.textContent = category.name;
                categorySelect.appendChild(option);
            });
        } catch (error) {
            console.error('Could not load the categories:', error);
        }
    }

    async function loadBooks() {
        hideMessage(messageBox);

        const params = new URLSearchParams();
        const searchText = searchInput.value.trim();

        if (searchText) {
            params.set('search', searchText);
        }
        if (categorySelect.value) {
            params.set('category_id', categorySelect.value);
        }
        if (formatSelect.value === 'digital') {
            params.set('is_digital', 'true');
        }

        try {
            const response = await apiFetch(`/books/?${params.toString()}`);

            if (!response.ok) {
                showGridNote('');
                resultCount.textContent = '';
                showMessage(messageBox, await readErrorMessage(response, 'Could not load the books.'));
                return;
            }

            const books = await response.json();

            if (books.length === 0) {
                resultCount.textContent = 'No books found';
                showGridNote('No books match your search.');
                return;
            }

            resultCount.textContent = books.length === 1 ? '1 book' : `${books.length} books`;
            booksContainer.replaceChildren(...books.map(createBookCard));
        } catch (error) {
            console.error('Could not load the books:', error);
            showGridNote('');
            resultCount.textContent = '';
            showMessage(messageBox, 'Could not reach the server. Please try again.');
        }
    }

    // Wait until the visitor stops typing before searching, so we do not send a request per letter
    let searchTimer = null;
    searchInput.addEventListener('input', () => {
        clearTimeout(searchTimer);
        searchTimer = setTimeout(loadBooks, 350);
    });

    categorySelect.addEventListener('change', loadBooks);
    formatSelect.addEventListener('change', loadBooks);
    filtersForm.addEventListener('submit', (event) => {
        event.preventDefault();
        loadBooks();
    });

    // Links such as /catalog?search=1984 or /catalog?category_id=2 (used on the home page)
    // open the catalog with that search or category already applied.
    async function start() {
        const addressParams = new URLSearchParams(window.location.search);

        searchInput.value = addressParams.get('search') || '';

        await loadCategories();

        const wantedCategory = addressParams.get('category_id');
        if (wantedCategory && categorySelect.querySelector(`option[value="${CSS.escape(wantedCategory)}"]`)) {
            categorySelect.value = wantedCategory;
        }

        loadBooks();
    }

    start();
});
