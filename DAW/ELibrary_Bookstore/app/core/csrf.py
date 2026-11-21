"""
Protecție CSRF (Barem 9.01) - modelul "Signed Double-Submit Cookie".

Cum funcționează:
1. La prima vizită, serverul pune în browser un cookie `csrf_token` (valoare aleatoare + semnătură HMAC).
2. La orice cerere care MODIFICĂ date (POST / PUT / PATCH / DELETE), clientul trebuie să trimită
   aceeași valoare și în header-ul `X-CSRF-Token`.
3. Un site străin poate face browserul victimei să trimită cookie-ul automat, dar NU poate citi
   cookie-ul și deci nu poate completa header-ul -> cererea falsificată este respinsă cu 403.

În plus, verificăm header-ul `Origin`: dacă cererea vine de pe alt site, o respingem direct.
"""
import hashlib
import hmac
import secrets
from urllib.parse import urlparse

from fastapi import Request
from fastapi.responses import JSONResponse

from app.core.logger import logger
from app.core.security import SECRET_KEY

CSRF_COOKIE_NAME = "csrf_token"
CSRF_HEADER_NAME = "X-CSRF-Token"
SAFE_METHODS = {"GET", "HEAD", "OPTIONS", "TRACE"}


def _sign(nonce: str) -> str:
    """Semnătura HMAC-SHA256 a valorii aleatoare, făcută cu cheia secretă a serverului."""
    return hmac.new(SECRET_KEY.encode("utf-8"), nonce.encode("utf-8"), hashlib.sha256).hexdigest()


def generate_csrf_token() -> str:
    """Creează un token nou, de forma `<valoare aleatoare>.<semnătură>`."""
    nonce = secrets.token_urlsafe(32)
    return f"{nonce}.{_sign(nonce)}"


def is_valid_csrf_token(token: str | None) -> bool:
    """Verifică dacă token-ul a fost emis de noi (semnătura se potrivește)."""
    if not token:
        return False
    nonce, _, signature = token.partition(".")
    if not nonce or not signature:
        return False
    return hmac.compare_digest(signature.encode("utf-8"), _sign(nonce).encode("utf-8"))


def is_same_origin(request: Request) -> bool:
    """
    Browserele trimit header-ul `Origin` la cererile POST. Dacă există și indică alt site
    decât al nostru, cererea este cross-site. (Clienții non-browser nu trimit Origin.)
    """
    origin = request.headers.get("origin")
    if origin is None:
        return True
    return urlparse(origin).netloc == request.headers.get("host")


def _reject(request: Request, reason: str) -> JSONResponse:
    client_ip = request.client.host if request.client else "necunoscut"
    logger.warning(f"CSRF BLOCKED: {request.method} {request.url.path} from {client_ip} ({reason}).")
    return JSONResponse(status_code=403, content={"detail": f"Request rejected (CSRF): {reason}"})


async def csrf_protection_middleware(request: Request, call_next):
    cookie_token = request.cookies.get(CSRF_COOKIE_NAME)
    has_valid_cookie = is_valid_csrf_token(cookie_token)

    if request.method not in SAFE_METHODS:
        if not is_same_origin(request):
            return _reject(request, "the request comes from another website.")

        header_token = request.headers.get(CSRF_HEADER_NAME)
        tokens_match = (
            has_valid_cookie
            and header_token is not None
            and hmac.compare_digest(header_token.encode("utf-8"), cookie_token.encode("utf-8"))
        )
        if not tokens_match:
            return _reject(request, "missing or invalid CSRF token.")

    response = await call_next(request)

    if not has_valid_cookie:
        response.set_cookie(
            key=CSRF_COOKIE_NAME,
            value=generate_csrf_token(),
            httponly=False,  # JavaScript-ul nostru trebuie să îl poată citi ca să îl pună în header
            samesite="strict",
            secure=request.url.scheme == "https",
            path="/",
        )

    return response
