# ELibrary & Bookstore

![Tests](https://github.com/AlexGADC/elibrary-bookstore-webapp/actions/workflows/tests.yml/badge.svg)

An online library and bookstore where users can browse a catalog of books, borrow them, buy them with a card, and download the digital editions they own. Built as a university web development project.

## Features

**For readers**

- Create an account and log in (the login is protected by reCAPTCHA)
- Browse the book catalog, search by title or author, filter by category and format
- Borrow a book for 14 days and return it
- Buy a book through Stripe Checkout
- Download the e-book (PDF or EPUB) of a book they bought or currently borrow

**For administrators**

- Add, edit and delete books
- Upload cover images and e-book files
- Create and delete categories

The web interface currently covers login and the catalog; the other actions are available through the interactive API page (`/docs`) while the remaining pages are being built.

## Technologies

| Area | Used |
|---|---|
| Backend | Python, FastAPI, SQLAlchemy |
| Database | PostgreSQL |
| Frontend | HTML, CSS, JavaScript, Jinja2 templates |
| Authentication | JWT tokens, bcrypt password hashing |
| Payments | Stripe Checkout |
| Testing | pytest, GitHub Actions |

## Architecture

The code is organised in layers, following the Repository pattern:

| Folder | Role |
|---|---|
| `app/api` | Routes (controllers): books, categories, authentication |
| `app/services` | Repositories: all database access goes through them |
| `app/models` | Database tables (SQLAlchemy models) |
| `app/schemas` | Request and response shapes (Pydantic) |
| `app/core` | Database connection, security, CSRF, rate limiting, logging |
| `templates`, `static` | Pages, styles and scripts |

## Security

- **Authentication and roles:** JWT login; admin-only actions are checked on the server
- **CSRF protection:** signed token required on every request that changes data
- **XSS protection:** book data is rendered as plain text, plus a strict Content-Security-Policy
- **SQL injection:** all queries go through the SQLAlchemy ORM
- **Uploads:** 12 MB limit, approved file types only, cover images are re-encoded
- **Rate limiting:** 100 requests per minute per IP address
- **Security headers:** CSP, HSTS, X-Frame-Options, Referrer-Policy, Permissions-Policy
- **Protected files:** e-books are served only after a login and ownership check
- **Activity log:** user actions and blocked requests are written to a log file

## Running it locally

You need Python and PostgreSQL installed.

1. Go to the project folder and install the requirements:

   ```
   cd DAW/ELibrary_Bookstore
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. Create a file named `.env` in that folder with your own values:

   ```
   DATABASE_URL=postgresql+psycopg://USER:PASSWORD@localhost:5432/DATABASE_NAME
   STRIPE_SECRET_KEY=your_stripe_test_key
   ```

3. Start the application:

   ```
   uvicorn app.main:app --reload
   ```

4. Open `http://localhost:8000` for the site, or `http://localhost:8000/docs` for the interactive API documentation.

The tables and the `admin` and `user` roles are created automatically on first start. New accounts get the `user` role; an administrator is promoted by setting that account's role to `admin` in the database.

## Tests

```
python -m pytest test_main.py -v
```

The same tests run automatically on every push through GitHub Actions.

## About

University project for the Web Application Development (DAW) course.
