import uuid
import stripe
from decimal import Decimal
from types import SimpleNamespace
from fastapi import Request
from fastapi.testclient import TestClient
from app.main import app
from app.core.limiter import reset_rate_limits
from app.core import security, captcha
from app.api.books import get_site_url, get_ebook_price
from app.core.database import SessionLocal
from app.models.database_models import User
from app.services.repository import role_repo

client = TestClient(app)

# CSRF: the first GET makes the server set the "csrf_token" cookie.
# We send the same value back in the X-CSRF-Token header, like the real frontend does.
client.get("/")
client.headers["X-CSRF-Token"] = client.cookies["csrf_token"]


# Test 1: Check if the server is on and the pages are served
def test_read_root():
    response = client.get("/")  # the home page
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert 'class="hero"' in response.text

    catalog_page = client.get("/catalog")
    assert catalog_page.status_code == 200
    assert 'id="booksContainer"' in catalog_page.text

    login_page = client.get("/login")
    assert login_page.status_code == 200
    assert 'id="loginForm"' in login_page.text

    register_page = client.get("/register")
    assert register_page.status_code == 200
    assert 'id="registerForm"' in register_page.text


# Test 2: Get All Books Test
def test_get_all_books():
    response = client.get("/books/") 
    assert response.status_code == 200
    assert isinstance(response.json(), list)


# Test 3: Exceptions - Inexistent book
def test_get_nonexistent_book():
    response = client.get("/books/999999")
    assert response.status_code == 404
    assert response.json()["detail"] == "Book not found."


# Test 4: Access denied without JWT Token
def test_create_book_without_token():
    book_data = {
        "title": "Carte Hacker",
        "author": "Anonim",
        "price": 50.0,
        "stock": 10,
        "category_id": 1
    }
    response = client.post("/books/", json=book_data)
    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"


# Test 5: Failed Login - Bad Credentials
class FakeCaptchaClient:
    """
    Înlocuiește httpx.AsyncClient în timpul testului, ca să nu apelăm Google reCAPTCHA
    prin rețea. Răspunde mereu că verificarea CAPTCHA a reușit.
    """
    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc_info):
        return False

    async def post(self, *args, **kwargs):
        return SimpleNamespace(json=lambda: {"success": True})


def test_login_wrong_credentials(monkeypatch):
    monkeypatch.setattr("app.core.captcha.httpx.AsyncClient", FakeCaptchaClient)

    response = client.post(
        "/auth/login",
        data={
            "username": "hacker@test.com",
            "password": "parolagresita",
            "captcha": "token-de-test"
        }
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Incorrect email or password"


# Test 6: CSRF - a POST without the CSRF token is rejected
def test_post_without_csrf_token_is_rejected():
    client_without_token = TestClient(app)
    client_without_token.get("/")  # has the cookie, but never sends the header

    response = client_without_token.post(
        "/auth/login",
        data={"username": "hacker@test.com", "password": "parolagresita"}
    )
    assert response.status_code == 403
    assert "CSRF" in response.json()["detail"]


# Test 7: CSRF - a POST coming from another website is rejected, even with a valid token
def test_cross_site_post_is_rejected():
    response = client.post(
        "/auth/login",
        data={"username": "hacker@test.com", "password": "parolagresita"},
        headers={"Origin": "https://evil.example"}
    )
    assert response.status_code == 403
    assert "CSRF" in response.json()["detail"]


# Test 8: Security headers are sent on every response
def test_security_headers_are_present():
    response = client.get("/")
    for header in [
        "Content-Security-Policy",
        "Strict-Transport-Security",
        "X-Frame-Options",
        "X-Content-Type-Options",
        "Referrer-Policy",
        "Permissions-Policy",
    ]:
        assert header in response.headers
    assert "'unsafe-inline'" not in response.headers["Content-Security-Policy"].split("script-src")[1].split(";")[0]


# Test 9: E-book files are not public - no direct link, and the download needs a login
def test_ebook_files_are_protected():
    direct_link = client.get("/uploads/files/book_1.pdf")
    assert direct_link.status_code == 404

    download_without_login = client.get("/books/1/download")
    assert download_without_login.status_code == 401


# Test 10: Rate limiting - after 100 requests in one minute, the next ones are blocked
def test_rate_limit_blocks_after_100_requests():
    reset_rate_limits()  # start counting from zero, whatever the tests above did
    try:
        # 100 requests spread over a page and an API route: the limit is global, not per route
        for _ in range(50):
            assert client.get("/catalog").status_code == 200
            assert client.get("/books/999999").status_code == 404

        blocked = client.get("/books/")  
        assert blocked.status_code == 429
        assert 1 <= int(blocked.headers["Retry-After"]) <= 61
        assert "Too many requests" in blocked.json()["detail"]
        assert "X-Frame-Options" in blocked.headers  
    finally:
        reset_rate_limits() 

# Test 11: Authorization - a logged-in user who is not an admin cannot add books
def test_normal_user_cannot_create_book():
    normal_user = SimpleNamespace(id=999, email="user@test.com", role_id=2)
    app.dependency_overrides[security.get_current_user] = lambda: normal_user
    try:
        response = client.post(
            "/books/",
            json={"title": "Carte Test", "author_name": "Autor", "price": 10.0, "category_id": 1}
        )
        assert response.status_code == 403
    finally:
        app.dependency_overrides.clear()


# Test 12: Stripe return links follow the address the site is opened at (not a fixed localhost)
def test_stripe_return_address_follows_the_site_address(monkeypatch):
    def fake_request(host: str, forwarded_proto: str = "") -> Request:
        headers = [(b"host", host.encode())]
        if forwarded_proto:
            headers.append((b"x-forwarded-proto", forwarded_proto.encode()))
        return Request({"type": "http", "method": "GET", "path": "/", "scheme": "http", "headers": headers})

    monkeypatch.delenv("APP_BASE_URL", raising=False)
    assert get_site_url(fake_request("localhost:8000")) == "http://localhost:8000"
    assert get_site_url(fake_request("demo.trycloudflare.com", "https")) == "https://demo.trycloudflare.com"

    monkeypatch.setenv("APP_BASE_URL", "https://elibrary.example.com/")
    assert get_site_url(fake_request("localhost:8000")) == "https://elibrary.example.com"


# Test 13: Registration - a new account gets the "user" role, and the default roles exist
def test_register_assigns_user_role(monkeypatch):
    monkeypatch.setattr("app.core.captcha.httpx.AsyncClient", FakeCaptchaClient)

    email = f"test-{uuid.uuid4().hex[:12]}@example.com"
    try:
        response = client.post(
            "/auth/register",
            json={
                "username": "Test User",
                "email": email,
                "password": uuid.uuid4().hex,
                "captcha": "token-de-test"
            }
        )
        assert response.status_code == 201

        with SessionLocal() as db:
            admin_role = role_repo.get_by_name(db, "admin")
            user_role = role_repo.get_by_name(db, "user")
        assert admin_role is not None and user_role is not None
        assert response.json()["role_id"] == user_role.id
    finally:
        with SessionLocal() as db:  # remove the test account again
            db.query(User).filter(User.email == email).delete()
            db.commit()


# Test 14: CAPTCHA - registration without a CAPTCHA answer is rejected
def test_register_without_captcha_is_rejected(monkeypatch):
    monkeypatch.setattr(captcha, "ALLOW_DOCS_LOGIN", False)

    response = client.post(
        "/auth/register",
        json={"username": "Bot", "email": f"bot-{uuid.uuid4().hex[:12]}@example.com", "password": uuid.uuid4().hex}
    )
    assert response.status_code == 400
    assert "CAPTCHA" in response.json()["detail"]


# Test 15: CAPTCHA - pretending to be the /docs page skips it only when ALLOW_DOCS_LOGIN is on
def test_docs_shortcut_needs_the_setting(monkeypatch):
    wrong_login = {"username": "hacker@test.com", "password": "parolagresita"}
    from_docs_page = {"Referer": "http://testserver/docs"}

    monkeypatch.setattr(captcha, "ALLOW_DOCS_LOGIN", False)
    response = client.post("/auth/login", data=wrong_login, headers=from_docs_page)
    assert response.status_code == 400
    assert "CAPTCHA" in response.json()["detail"]

    monkeypatch.setattr(captcha, "ALLOW_DOCS_LOGIN", True)
    response = client.post("/auth/login", data=wrong_login, headers=from_docs_page)
    assert response.status_code == 401  

    response = client.post("/auth/login", data=wrong_login, headers={"Referer": "http://evil.example/docs"})
    assert response.status_code == 400


# Test 16: Pages - a book that does not exist shows the "not found" page
def test_missing_book_page_is_not_found():
    response = client.get("/book/999999")
    assert response.status_code == 404
    assert "text/html" in response.headers["content-type"]
    assert "couldn't find" in response.text


# Test 17: Authorization - the list of my loans and purchases needs a login
def test_my_transactions_requires_login():
    response = client.get("/books/my-transactions")
    assert response.status_code == 401


# Test 18: Payments - a paid checkout cannot be used to confirm a different purchase
def test_payment_must_belong_to_the_purchase(monkeypatch):
    paid_checkout = stripe.StripeObject.construct_from(
        {"payment_status": "paid", "amount_total": 3990, "metadata": {"transaction_id": "999999"}},
        "sk_test_fake"
    )
    monkeypatch.setattr("app.api.books.stripe.checkout.Session.retrieve", lambda session_id: paid_checkout)

    response = client.get("/books/payment-success", params={"session_id": "cs_test_fake", "transaction_id": 6})
    assert response.status_code == 400
    assert "does not belong" in response.json()["detail"]

    response = client.get("/books/payment-success", params={"session_id": "cs_test_fake", "transaction_id": 999999})
    assert response.status_code == 404
    assert response.json()["detail"] == "Transaction not found."


# Test 19: E-books - the e-book costs half the printed price, rounded to two decimals
def test_ebook_price_is_half_the_printed_price():
    assert get_ebook_price(Decimal("39.90")) == Decimal("19.95")
    assert get_ebook_price(Decimal("44.90")) == Decimal("22.45")
    assert get_ebook_price(Decimal("29.99")) == Decimal("15.00")  # 14.995 rounds up


# Test 20: Authorization - buying an e-book needs a login
def test_buy_ebook_requires_login():
    response = client.post("/books/1/buy-ebook")
    assert response.status_code == 401
