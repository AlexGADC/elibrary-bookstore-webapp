"""
Google reCAPTCHA keys.

The real keys are read from .env (RECAPTCHA_SITE_KEY and RECAPTCHA_SECRET_KEY), so the secret
key never appears in the code or in the repository.

If .env does not contain BOTH keys, Google's public test keys are used instead. With the test
keys the CAPTCHA always passes and shows a red "for testing purposes only" warning; this keeps
the app and the automated tests working on a machine that has no keys configured.
"""
import os

from dotenv import load_dotenv

load_dotenv()

# Google's published test keys (public, the same for everybody).
TEST_SITE_KEY = "6LeIxAcTAAAAAJcZVRqyHh71UMIEGNQ_MXjiZKhI"
TEST_SECRET_KEY = "6LeIxAcTAAAAAGG-vFI1TnRWxMZNFuojJ4WifJWe"

_site_key = os.getenv("RECAPTCHA_SITE_KEY", "").strip()
_secret_key = os.getenv("RECAPTCHA_SECRET_KEY", "").strip()

# The two keys only work as a pair, so the real ones are used only when both are set.
USING_REAL_KEYS = bool(_site_key and _secret_key)

RECAPTCHA_SITE_KEY = _site_key if USING_REAL_KEYS else TEST_SITE_KEY
RECAPTCHA_SECRET_KEY = _secret_key if USING_REAL_KEYS else TEST_SECRET_KEY
