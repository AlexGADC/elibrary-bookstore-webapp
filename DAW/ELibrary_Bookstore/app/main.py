import os
from fastapi import FastAPI, Request
from app.core.database import engine, Base
from app.api.books import router as books_router
from app.api.categories import router as categories_router
from app.api.auth import router as auth_router
from fastapi.staticfiles import StaticFiles
from slowapi.errors import RateLimitExceeded
from app.core.limiter import limiter
from fastapi.responses import JSONResponse, HTMLResponse
from contextlib import asynccontextmanager
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates


Base.metadata.create_all(bind=engine)

app = FastAPI(title="ELibrary & Bookstore API")

@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        with engine.connect() as connection:
            print("==== POSTGRESQL CONNECTION SUCCESSFULLY ESTABLISHED! ====")
    except Exception as e:
        print(f"==== CONNECTION ERROR: {e} ====")
    yield

app = FastAPI(title="ELibrary & Bookstore API", lifespan=lifespan)

app.state.limiter = limiter
os.makedirs("uploads/covers", exist_ok=True)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

app.include_router(books_router)
app.include_router(categories_router)
app.include_router(auth_router)

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    """
    Ruta principală care servește interfața de Login (index.html).
    Trimitem obiectul 'request' către Jinja2 pentru a putea genera corect link-urile către CSS/JS.
    """

    return templates.TemplateResponse(request=request, name="index.html", context={})

@app.get("/catalog", response_class=HTMLResponse)
async def read_catalog(request: Request):
    """
    Ruta care servește interfața principală cu lista de cărți.
    """
    return templates.TemplateResponse(request=request, name="catalog.html", context={})

@app.exception_handler(RateLimitExceeded)
async def rate_limit_custom_handler(request: Request, exc: RateLimitExceeded):
    """
    Prinde eroarea de Rate Limiting (peste 100 cereri/min) și 
    returnează un mesaj personalizat, rezolvând conflictul de tipizare.
    """
    return JSONResponse(
        status_code=429,
        content={"detail": "Prea multe cereri! Ai depășit limita. Te rugăm să aștepți un minut."}
    )

@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    """
    Middleware pentru Securitate Avansată (Barem 10.04).
    Adaugă headere de protecție la absolut fiecare răspuns trimis de server.
    """
    response = await call_next(request)
    
    response.headers["X-Content-Type-Options"] = "nosniff" 
    response.headers["X-Frame-Options"] = "DENY"         
    response.headers["X-XSS-Protection"] = "1; mode=block" 
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains" 
    response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://www.google.com https://www.gstatic.com; frame-src 'self' https://www.google.com; style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; img-src 'self' data: https://fastapi.tiangolo.com;"
    return response