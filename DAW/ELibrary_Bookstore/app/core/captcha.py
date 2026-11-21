"""
Google reCAPTCHA: keys, the server-side check, and the development shortcut for Swagger.

The real keys are read from .env (RECAPTCHA_SITE_KEY and RECAPTCHA_SECRET_KEY), so the secret
key never appears in the code or in the repository.

If .env does not contain BOTH keys, Google's public test keys are used instead. With the test
keys the CAPTCHA always passes and shows a red "for testing purposes only" warning; this keeps
the app and the automated tests working on a machine that has no keys configured.
"""
import os
from typing import Optional
from urllib.parse import urlparse

import httpx
from dotenv import load_dotenv
from fastapi import HTTPException, Request, status

load_dotenv()

TEST_SITE_KEY = "6LeIxAcTAAAAAJcZVRqyHh71UMIEGNQ_MXjiZKhI"
TEST_SECRET_KEY = "6LeIxAcTAAAAAGG-vFI1TnRWxMZNFuojJ4WifJWe"

_site_key = os.getenv("RECAPTCHA_SITE_KEY", "").strip()
_secret_key = os.getenv("RECAPTCHA_SECRET_KEY", "").strip()

USING_REAL_KEYS = bool(_site_key and _secret_key)

RECAPTCHA_SITE_KEY = _site_key if USING_REAL_KEYS else TEST_SITE_KEY
RECAPTCHA_SECRET_KEY = _secret_key if USING_REAL_KEYS else TEST_SECRET_KEY

VERIFY_URL = "https://www.google.com/recaptcha/api/siteverify"

ALLOW_DOCS_LOGIN = os.getenv("ALLOW_DOCS_LOGIN", "").strip().lower() in ("1", "true", "yes", "on")
DOCS_PATHS = ("/docs", "/redoc")


def is_docs_request(request: Request) -> bool:
    """True only when the shortcut is enabled AND the request was sent from our own /docs page."""
    if not ALLOW_DOCS_LOGIN:
        return False

    referer = urlparse(request.headers.get("referer", ""))
    return referer.netloc == request.headers.get("host") and referer.path.startswith(DOCS_PATHS)


async def verify_captcha(captcha_response: Optional[str]) -> None:
    """Asks Google whether the CAPTCHA answer is valid. Raises a 400 error if it is missing or wrong."""
    if not captcha_response:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please complete the CAPTCHA."
        )

    async with httpx.AsyncClient() as client:
        google_response = await client.post(
            VERIFY_URL,
            data={"secret": RECAPTCHA_SECRET_KEY, "response": captcha_response}
        )

    if not google_response.json().get("success"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="CAPTCHA verification failed. Please try again."
        )
