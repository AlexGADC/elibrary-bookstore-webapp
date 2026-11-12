from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

# ==========================================
# TESTUL 1: Verificăm dacă serverul este "treaz"
# ==========================================
def test_read_root():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "Server is running perfectly!"}

# ==========================================
# TESTUL 2: Verificăm obținerea listei de cărți
# ==========================================
def test_get_all_books():
    response = client.get("/books/") 
    assert response.status_code == 200
    assert isinstance(response.json(), list)

# ==========================================
# TESTUL 3: Tratarea excepțiilor - Carte inexistentă
# ==========================================
def test_get_nonexistent_book():
    response = client.get("/books/999999")
    assert response.status_code == 404
    assert response.json()["detail"] == "Book not found."

# ==========================================
# TESTUL 4: Securitate - Acces interzis fără Token JWT
# ==========================================
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

# ==========================================
# TESTUL 5: Logare eșuată - Date greșite
# ==========================================
def test_login_wrong_credentials():
    response = client.post(
        "/auth/login", 
        data={"username": "hacker@test.com", "password": "parolagresita"}
    )
    assert response.status_code in [401, 403, 404] 