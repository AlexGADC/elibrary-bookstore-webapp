import os
from fastapi import FastAPI, Request, Depends
from sqlalchemy.orm import Session
from app.core.database import engine, Base, SessionLocal, get_db
from app.models.database_models import Book, Category
from app.services.repository import role_repo
from app.api.books import router as books_router, get_ebook_price
from app.api.categories import router as categories_router
from app.api.auth import router as auth_router
from fastapi.staticfiles import StaticFiles
from app.core.limiter import rate_limit_middleware
from app.core.captcha import RECAPTCHA_SITE_KEY
from fastapi.responses import JSONResponse, HTMLResponse, PlainTextResponse
from contextlib import asynccontextmanager
from fastapi.templating import Jinja2Templates
from fastapi.openapi.docs import get_swagger_ui_html, get_swagger_ui_oauth2_redirect_html
from app.core.csrf import csrf_protection_middleware, CSRF_COOKIE_NAME, CSRF_HEADER_NAME


Base.metadata.create_all(bind=engine)

with SessionLocal() as db:
    role_repo.ensure_default_roles(db)

app = FastAPI(title="ELibrary & Bookstore API")

@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        with engine.connect() as connection:
            print("==== POSTGRESQL CONNECTION SUCCESSFULLY ESTABLISHED! ====")
    except Exception as e:
        print(f"==== CONNECTION ERROR: {e} ====")
    yield

app = FastAPI(title="ELibrary & Bookstore API", lifespan=lifespan, docs_url=None)

os.makedirs("uploads/covers", exist_ok=True)
app.mount("/uploads/covers", StaticFiles(directory="uploads/covers"), name="uploads")

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

app.include_router(books_router)
app.include_router(categories_router)
app.include_router(auth_router)

ASSET_VERSION = "2.5"
templates.env.globals["asset_version"] = ASSET_VERSION

NO_COVER_IMAGE = "/static/img/no-cover.svg"
FEATURED_BOOKS_COUNT = 5   
MORE_BOOKS_COUNT = 5       

def book_for_page(book: Book) -> dict:
    """The fields of a book that the page templates show."""
    return {
        "id": book.id,
        "title": book.title,
        "author": book.author_name,
        "description": book.description,
        "price": f"{book.price:.2f}",
        "cover_url": book.cover_image_url or NO_COVER_IMAGE,
        "stock": book.stock or 0,
        "in_stock": (book.stock or 0) > 0,
        "is_digital": bool(book.is_digital),
        "has_digital_file": bool(book.digital_file_url),
        "ebook_price": f"{get_ebook_price(book.price):.2f}" if book.digital_file_url else None,
        "category_id": book.category_id,
        "category_name": book.category.name if book.category else None,
    }

@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def read_home(request: Request, db: Session = Depends(get_db)):
    """
    Pagina de start: caruselul cu cărți recomandate, categoriile și câteva cărți din catalog.
    """
    books = (
        db.query(Book)
        .order_by(Book.id)
        .limit(FEATURED_BOOKS_COUNT + MORE_BOOKS_COUNT)
        .all()
    )
    books_for_page = [book_for_page(book) for book in books]

    return templates.TemplateResponse(
        request=request,
        name="home.html",
        context={
            "featured_books": books_for_page[:FEATURED_BOOKS_COUNT],
            "more_books": books_for_page[FEATURED_BOOKS_COUNT:],
            "categories": db.query(Category).order_by(Category.name).all(),
        }
    )

@app.get("/login", response_class=HTMLResponse, include_in_schema=False)
async def read_login(request: Request):
    """
    Pagina de autentificare.
    """
    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={"recaptcha_site_key": RECAPTCHA_SITE_KEY}
    )

@app.get("/register", response_class=HTMLResponse, include_in_schema=False)
async def read_register(request: Request):
    """
    Pagina de creare a unui cont nou.
    """
    return templates.TemplateResponse(
        request=request,
        name="register.html",
        context={"recaptcha_site_key": RECAPTCHA_SITE_KEY}
    )

@app.get("/catalog", response_class=HTMLResponse, include_in_schema=False)
async def read_catalog(request: Request):
    """
    Pagina cu lista de cărți. Poate fi văzută și fără autentificare.
    """
    return templates.TemplateResponse(request=request, name="catalog.html", context={})

RELATED_BOOKS_COUNT = 5

@app.get("/book/{book_id}", response_class=HTMLResponse, include_in_schema=False)
def read_book(book_id: int, request: Request, db: Session = Depends(get_db)):
    """
    Pagina unei cărți: detalii, împrumut, cumpărare, returnare și descărcare.
    """
    book = db.query(Book).filter(Book.id == book_id).first()

    if not book:
        return templates.TemplateResponse(request=request, name="not_found.html", context={}, status_code=404)

    related_books = []
    if book.category_id is not None:
        related_books = (
            db.query(Book)
            .filter(Book.category_id == book.category_id, Book.id != book.id)
            .order_by(Book.id)
            .limit(RELATED_BOOKS_COUNT)
            .all()
        )

    page_book = book_for_page(book)

    meta_description = f"{book.title} by {book.author_name}. {book.description or ''}".strip()
    if len(meta_description) > 155:
        meta_description = meta_description[:152].rstrip() + "..."

    return templates.TemplateResponse(
        request=request,
        name="book.html",
        context={
            "book": page_book,
            "meta_description": meta_description,
            "related_books": [book_for_page(related) for related in related_books],
        }
    )

@app.get("/payment/success", response_class=HTMLResponse, include_in_schema=False)
async def read_payment_result(request: Request):
    """
    Pagina la care Stripe trimite cumpărătorul după plată. Scriptul paginii cere serverului
    să verifice plata și afișează rezultatul.
    """
    return templates.TemplateResponse(request=request, name="payment_result.html", context={})

@app.get("/robots.txt", response_class=PlainTextResponse, include_in_schema=False)
async def robots_txt():
    """
    Spune motoarelor de căutare ce pagini pot indexa.
    """
    return "User-agent: *\nAllow: /\nDisallow: /docs\nDisallow: /redoc\nDisallow: /auth/\n"

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

app.middleware("http")(csrf_protection_middleware)

app.middleware("http")(rate_limit_middleware)

DOCS_PATHS = ("/docs", "/redoc")

APP_CSP = (
    "default-src 'self'; "
    "script-src 'self' https://www.google.com/recaptcha/ https://www.gstatic.com/recaptcha/; "
    "frame-src https://www.google.com/recaptcha/ https://recaptcha.google.com/recaptcha/; "
    "style-src 'self' 'unsafe-inline'; "
    "img-src 'self'; "
    "object-src 'none'; "
    "base-uri 'self'; "
    "form-action 'self'; "
    "frame-ancestors 'none'"
)

DOCS_CSP = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
    "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
    "img-src 'self' data: https://fastapi.tiangolo.com; "
    "object-src 'none'; "
    "base-uri 'self'; "
    "frame-ancestors 'none'"
)

@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    """
    Middleware pentru Securitate Avansată (Barem 10.04).
    Adaugă headere de protecție la absolut fiecare răspuns trimis de server.
    """
    response = await call_next(request)

    is_docs_page = request.url.path.startswith(DOCS_PATHS)

    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Content-Security-Policy"] = DOCS_CSP if is_docs_page else APP_CSP
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
    response.headers["Cross-Origin-Resource-Policy"] = "same-origin"
    return response