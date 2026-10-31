from fastapi import FastAPI
from app.core.database import engine

app = FastAPI(title="ELibrary & Bookstore API")

@app.on_event("startup")
def startup_event():
    try:
        # Încercăm să deschidem o conexiune rapidă la baza de date
        with engine.connect() as connection:
            print("==== POSTGRESQL CONNECTION SUCCESSFULLY ESTABLISHED! ====")
    except Exception as e:
        # Prindem eroarea și o afișăm în consolă în caz că parola sau numele bazei de date sunt greșite
        print(f"==== CONNECTION ERROR: {e} ====")

@app.get("/")
def read_root():
    # Returnăm starea serverului
    return {"message": "Server is running perfectly!"}