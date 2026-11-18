from types import SimpleNamespace
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

# CSRF: the first GET makes the server set the "csrf_token" cookie.
# We send the same value back in the X-CSRF-Token header, like the real frontend does.
client.get("/")
client.headers["X-CSRF-Token"] = client.cookies["csrf_token"]


# Test 1: Check if the server is on
def test_read_root():
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert 'id="loginForm"' in response.text


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
    monkeypatch.setattr("app.api.auth.httpx.AsyncClient", FakeCaptchaClient)

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