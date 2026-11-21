// =====================================================================
// book.js - the page of one book: borrow, return, buy the printed book,
// buy the e-book and download it.
// Needs common.js (apiFetch, showMessage, isLoggedIn ...).
//
// The book's details are written in book.html by the server. This script only
// decides which buttons to show and makes them work.
//
// The rules:
//   - Borrowing and buying the PRINTED book use the stock (printed copies).
//   - The E-BOOK is a separate purchase at half price. It never runs out of stock.
//   - Only people who bought the e-book can download it.
// =====================================================================

document.addEventListener('DOMContentLoaded', () => {
    const bookDetail = document.getElementById('bookDetail');
    if (!bookDetail) {
        return;
    }

    const bookId = bookDetail.dataset.bookId;
    const bookTitle = bookDetail.dataset.bookTitle;
    const hasEbook = bookDetail.dataset.hasFile === 'true';
    let stock = Number(bookDetail.dataset.stock);

    const messageBox = document.getElementById('bookMessage');
    const ownershipNote = document.getElementById('ownershipNote');
    const stockBadge = document.getElementById('stockBadge');
    const stockCell = document.getElementById('stockCell');

    const borrowButton = document.getElementById('borrowBtn');
    const buyButton = document.getElementById('buyBtn');
    const buyEbookButton = document.getElementById('buyEbookBtn');  
    const returnButton = document.getElementById('returnBtn');
    const downloadButton = document.getElementById('downloadBtn');

    let myTransactions = [];

    function formatDate(isoText) {
        return new Date(isoText).toLocaleDateString('en-GB', { day: 'numeric', month: 'long', year: 'numeric' });
    }

    function findActiveLoan() {
        return myTransactions.find((item) => item.type === 'loan' && item.status === 'active');
    }

    function ownsPrintedBook() {
        return myTransactions.some((item) => item.type === 'buy' && item.status === 'completed');
    }

    function ownsEbook() {
        return myTransactions.some((item) => item.type === 'buy_ebook' && item.status === 'completed');
    }

    function updatePage() {
        const loggedIn = isLoggedIn();
        const activeLoan = findActiveLoan();
        const ownsPrinted = ownsPrintedBook();
        const ownsDigital = ownsEbook();
        const inStock = stock > 0;

        stockBadge.textContent = inStock ? 'In stock' : 'Out of stock';
        stockBadge.className = `badge ${inStock ? 'badge-in-stock' : 'badge-out-of-stock'}`;
        stockCell.textContent = String(stock);

        borrowButton.hidden = !(loggedIn && !activeLoan && inStock);
        buyButton.hidden = !(loggedIn && !ownsPrinted && inStock);
        returnButton.hidden = !(loggedIn && activeLoan);
        downloadButton.hidden = !(loggedIn && hasEbook && ownsDigital);

        if (buyEbookButton) {
            buyEbookButton.hidden = !(loggedIn && !ownsDigital);
        }

        const notes = [];
        if (ownsPrinted) {
            notes.push('You own the printed book.');
        }
        if (ownsDigital) {
            notes.push('You own the e-book.');
        }
        if (activeLoan) {
            notes.push(
                activeLoan.due_date
                    ? `You are borrowing this book until ${formatDate(activeLoan.due_date)}.`
                    : 'You are borrowing this book.'
            );
        }
        if (loggedIn && !inStock && !ownsPrinted && !activeLoan) {
            notes.push(
                hasEbook && !ownsDigital
                    ? 'The printed book is out of stock right now, but you can still buy the e-book.'
                    : 'The printed book is out of stock right now, so it cannot be borrowed or bought.'
            );
        }

        ownershipNote.textContent = notes.join(' ');
        ownershipNote.hidden = notes.length === 0;
    }

    function handleExpiredLogin() {
        clearToken();
        applyAuthState();
        myTransactions = [];
        updatePage();
        showMessage(messageBox, 'Your session has ended. Please log in again.');
    }

    async function loadMyTransactions() {
        if (!isLoggedIn()) {
            myTransactions = [];
            return;
        }

        const response = await apiFetch(`/books/my-transactions?book_id=${encodeURIComponent(bookId)}`);

        if (response.status === 401) {
            clearToken();
            applyAuthState();
            myTransactions = [];
            return;
        }

        myTransactions = response.ok ? await response.json() : [];
    }

    async function loadStock() {
        const response = await apiFetch(`/books/${encodeURIComponent(bookId)}`);
        if (response.ok) {
            const book = await response.json();
            stock = Number(book.stock);
        }
    }

    async function refresh() {
        try {
            await Promise.all([loadMyTransactions(), loadStock()]);
        } catch (error) {
            console.error('Could not refresh the book page:', error);
        }
        updatePage();
    }

    async function runAction(button, busyText, action) {
        const normalText = button.textContent;
        button.disabled = true;
        button.textContent = busyText;
        hideMessage(messageBox);

        try {
            await action();
        } catch (error) {
            console.error(error);
            showMessage(messageBox, 'Could not reach the server. Please try again.');
        }

        button.disabled = false;
        button.textContent = normalText;
    }

    // ---------- Borrow ----------
    borrowButton.addEventListener('click', () => runAction(borrowButton, 'Borrowing...', async () => {
        const response = await apiFetch(`/books/${bookId}/borrow`, { method: 'POST' });

        if (response.status === 401) {
            handleExpiredLogin();
            return;
        }

        if (!response.ok) {
            showMessage(messageBox, await readErrorMessage(response, 'Could not borrow the book.'));
            return;
        }

        const loan = await response.json();
        await refresh();
        showMessage(
            messageBox,
            loan.due_date ? `Borrowed! Please return it by ${formatDate(loan.due_date)}.` : 'Borrowed!',
            'success'
        );
    }));

    // ---------- Return ----------
    returnButton.addEventListener('click', () => runAction(returnButton, 'Returning...', async () => {
        const response = await apiFetch(`/books/${bookId}/return`, { method: 'POST' });

        if (response.status === 401) {
            handleExpiredLogin();
            return;
        }

        if (!response.ok) {
            showMessage(messageBox, await readErrorMessage(response, 'Could not return the book.'));
            return;
        }

        await refresh();
        showMessage(messageBox, 'Thank you! The book was returned.', 'success');
    }));

    // ---------- Buy (printed book or e-book) ----------
    async function startPayment(buyAddress) {
        const response = await apiFetch(buyAddress, { method: 'POST' });

        if (response.status === 401) {
            handleExpiredLogin();
            return;
        }

        if (!response.ok) {
            showMessage(messageBox, await readErrorMessage(response, 'Could not start the payment.'));
            return;
        }

        const purchase = await response.json();

        if (!purchase.payment_url) {
            showMessage(messageBox, 'The payment page could not be opened. Please try again.');
            return;
        }

        window.location.href = purchase.payment_url;
    }

    buyButton.addEventListener('click', () => runAction(
        buyButton, 'Opening the payment page...', () => startPayment(`/books/${bookId}/buy`)
    ));

    if (buyEbookButton) {
        buyEbookButton.addEventListener('click', () => runAction(
            buyEbookButton, 'Opening the payment page...', () => startPayment(`/books/${bookId}/buy-ebook`)
        ));
    }

    // ---------- Download the e-book ----------
    downloadButton.addEventListener('click', () => runAction(downloadButton, 'Preparing the file...', async () => {
        const response = await apiFetch(`/books/${bookId}/download`, { cache: 'no-store' });

        if (response.status === 401) {
            handleExpiredLogin();
            return;
        }

        if (!response.ok) {
            showMessage(messageBox, await readErrorMessage(response, 'Could not download the file.'));
            return;
        }

        const fileContent = await response.blob();

        const serverName = (response.headers.get('Content-Disposition') || '').match(/filename="?([^";]+)"?/);
        const extension = serverName && serverName[1].includes('.') ? serverName[1].slice(serverName[1].lastIndexOf('.')) : '.pdf';
        const safeTitle = bookTitle.replace(/[\\/:*?"<>|]/g, '').trim() || 'book';

        const temporaryAddress = URL.createObjectURL(fileContent);
        const link = document.createElement('a');
        link.href = temporaryAddress;
        link.download = `${safeTitle}${extension}`;
        document.body.appendChild(link);
        link.click();
        link.remove();
        URL.revokeObjectURL(temporaryAddress);

        showMessage(messageBox, 'Your download has started.', 'success');
    }));

    if (new URLSearchParams(window.location.search).get('payment') === 'cancelled') {
        showMessage(messageBox, 'The payment was cancelled. You have not been charged.', 'info');
    }

    refresh();
});
