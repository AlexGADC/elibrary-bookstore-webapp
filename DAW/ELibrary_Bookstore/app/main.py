from fastapi import FastAPI
from app.core.database import engine, Base
from app.api.books import router as books_router
from app.api.categories import router as categories_router
from app.api.auth import router as auth_router
import os
from fastapi.staticfiles import StaticFiles

Base.metadata.create_all(bind=engine)

app = FastAPI(title="ELibrary & Bookstore API")

os.makedirs("uploads/covers", exist_ok=True)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

app.include_router(books_router)
app.include_router(categories_router)
app.include_router(auth_router)

@app.on_event("startup")
def startup_event():
    try:
        with engine.connect() as connection:
            print("==== POSTGRESQL CONNECTION SUCCESSFULLY ESTABLISHED! ====")
    except Exception as e:
        print(f"==== CONNECTION ERROR: {e} ====")

@app.get("/")
def read_root():
    return {"message": "Server is running perfectly!"}