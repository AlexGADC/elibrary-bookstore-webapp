// =====================================================================
// payment.js - the page Stripe sends the buyer back to after paying.
// Needs common.js (apiFetch, readErrorMessage).
//
// The address looks like /payment/success?session_id=...&transaction_id=...
// We ask our server to confirm with Stripe that the payment really went through.
// =====================================================================

document.addEventListener('DOMContentLoaded', async () => {
    const title = document.getElementById('paymentTitle');
    const text = document.getElementById('paymentText');
    const links = document.getElementById('paymentLinks');
    const bookLink = document.getElementById('paymentBookLink');

    function showResult(heading, message, bookId = null) {
        title.textContent = heading;
        text.textContent = message;

        if (bookId) {
            bookLink.href = `/book/${encodeURIComponent(bookId)}`;
            bookLink.hidden = false;
        } else {
            bookLink.hidden = true;
        }

        links.hidden = false;
    }

    const addressParams = new URLSearchParams(window.location.search);
    const sessionId = addressParams.get('session_id');
    const transactionId = addressParams.get('transaction_id');

    if (!sessionId || !transactionId) {
        showResult('No payment to check', 'This page is shown after a payment. Open a book and press Buy to start one.');
        return;
    }

    try {
        const query = new URLSearchParams({ session_id: sessionId, transaction_id: transactionId });
        const response = await apiFetch(`/books/payment-success?${query.toString()}`);

        if (!response.ok) {
            showResult('The payment could not be confirmed', await readErrorMessage(response, 'Please contact us if you were charged.'));
            return;
        }

        const result = await response.json();

        if (result.paid) {
            const whatWasBought = result.type === 'buy_ebook'
                ? 'The e-book is now yours. You can download it from the book\'s page.'
                : 'The printed book is now yours.';
            showResult('Thank you! Your payment was successful', whatWasBought, result.book_id);
        } else {
            showResult('The payment is not finished yet', result.message || 'Please try again in a moment.');
        }
    } catch (error) {
        console.error(error);
        showResult('The payment could not be checked', 'We could not reach the server. Please reload this page.');
    }
});
