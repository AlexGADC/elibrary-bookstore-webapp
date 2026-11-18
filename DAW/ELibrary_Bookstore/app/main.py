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
from fastapi.openapi.docs import get_swagger_ui_html, get_swagger_ui_oauth2_redirect_html
from app.core.csrf import csrf_protection_middleware, CSRF_COOKIE_NAME, CSRF_HEADER_NAME


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

# docs_url=None: dezactivăm pagina /docs implicită, pentru că o servim noi mai jos (cu suport CSRF).
app = FastAPI(title="ELibrary & Bookstore API", lifespan=lifespan, docs_url=None)

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

SWAGGER_CSRF_INTERCEPTOR = """SwaggerUIBundle({
        requestInterceptor: (request) => {
            const match = document.cookie.match(/(?:^|; )%s=([^;]*)/);
            if (match) {
                request.headers['%s'] = decodeURIComponent(match[1]);
            }
            return request;
        },""" % (CSRF_COOKIE_NAME, CSRF_HEADER_NAME)

@app.get("/docs", include_in_schema=False)
async def swagger_ui_with_csrf():
    """
    Pagina Swagger (/docs), identică cu cea implicită, dar cu un 'requestInterceptor':
    o funcție care adaugă automat header-ul X-CSRF-Token la fiecare cerere trimisă din Swagger.
    Fără ea, protecția CSRF ar bloca toate cererile POST/PATCH/DELETE făcute din /docs.
    """
    page = get_swagger_ui_html(
        openapi_url=app.openapi_url or "/openapi.json",
        title=f"{app.title} - Swagger UI",
        oauth2_redirect_url=app.swagger_ui_oauth2_redirect_url,
    )
    html = bytes(page.body).decode("utf-8").replace("SwaggerUIBundle({", SWAGGER_CSRF_INTERCEPTOR, 1)
    return HTMLResponse(html)

@app.get(app.swagger_ui_oauth2_redirect_url or "/docs/oauth2-redirect", include_in_schema=False)
async def swagger_ui_oauth2_redirect():
    return get_swagger_ui_oauth2_redirect_html()

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

# Protecție CSRF (Barem 9.01). Este înregistrat ÎNAINTE de middleware-ul de headere, astfel încât
# headerele de securitate să fie adăugate și pe răspunsurile 403 date de protecția CSRF
# (în FastAPI, ultimul middleware înregistrat este cel mai din exterior).
app.middleware("http")(csrf_protection_middleware)

# Paginile de documentație au nevoie de un script inline ca să pornească; restul aplicației NU.
DOCS_PATHS = ("/docs", "/redoc")

@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    """
    Middleware pentru Securitate Avansată (Barem 10.04).
    Adaugă headere de protecție la absolut fiecare răspuns trimis de server.
    """
    response = await call_next(request)

    # Protecție XSS (Barem 9.02): pe paginile aplicației NU permitem scripturi inline
    # (fără 'unsafe-inline'), deci un atribut injectat de tip onerror="..." nu se mai execută.
    script_sources = "'self' https://cdn.jsdelivr.net https://www.google.com https://www.gstatic.com"
    if request.url.path.startswith(DOCS_PATHS):
        script_sources = "'self' 'unsafe-inline' https://cdn.jsdelivr.net"

    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Content-Security-Policy"] = f"default-src 'self'; script-src {script_sources}; frame-src 'self' https://www.google.com; style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; img-src 'self' data: https://fastapi.tiangolo.com; object-src 'none'; base-uri 'self';"
    return response