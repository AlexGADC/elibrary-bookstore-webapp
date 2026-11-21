"""
Rate limiting (Barem 10.01).

At most 100 requests per minute from the same IP address, counted across the whole application.
Request number 101 gets a 429 response until the one-minute window expires.

Why not slowapi's own middleware: with the FastAPI version used here it cannot "see" the routes
added with app.include_router() (/books, /categories, /auth), so it silently skipped them.
This middleware counts every request directly, using `limits` (the library slowapi is built on).
"""
import time

from fastapi import Request
from fastapi.responses import JSONResponse
from limits import parse
from limits.storage import MemoryStorage
from limits.strategies import FixedWindowRateLimiter

from app.core.logger import logger

RATE_LIMIT = parse("100/minute")

# Files a page loads by itself (CSS, JS, images) are not counted,
# otherwise simply opening the catalog would use up a large part of the limit.
NOT_COUNTED_PREFIXES = ("/static/", "/uploads/covers/")

_storage = MemoryStorage()
_rate_limiter = FixedWindowRateLimiter(_storage)


def reset_rate_limits() -> None:
    """Forget all counters (used by the tests)."""
    _storage.reset()


async def rate_limit_middleware(request: Request, call_next):
    if request.url.path.startswith(NOT_COUNTED_PREFIXES):
        return await call_next(request)

    client_ip = request.client.host if request.client else "unknown"

    # hit() adds 1 to this IP's counter and returns False once the limit is exceeded.
    if not _rate_limiter.hit(RATE_LIMIT, client_ip):
        window_end = _rate_limiter.get_window_stats(RATE_LIMIT, client_ip).reset_time
        retry_after = max(1, int(window_end - time.time()) + 1)

        logger.warning(f"RATE LIMIT EXCEEDED: {client_ip} was blocked on {request.method} {request.url.path}.")

        return JSONResponse(
            status_code=429,
            content={"detail": "Too many requests! You have exceeded the limit. Please wait a minute."},
            headers={"Retry-After": str(retry_after)}
        )

    return await call_next(request)
