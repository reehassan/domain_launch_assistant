"""
Production settings for config project.
Boots with a strict posture by default, deliberately more locked down than
just "DEBUG=False":
- DEBUG is hardcoded here, not read from the environment at all. base.py's
  DEBUG = config("DEBUG", default=False, cast=bool) already defaults to
  False, but that means a stray DEBUG=True in a deploy's .env would flip it
  on and leak debug pages/tracebacks. Hardcoding removes that foot-gun
  entirely for this settings module.
- ALLOWED_HOSTS has NO fallback, unlike base.py's dev-friendly
  "localhost,127.0.0.1" default. A production container has no legitimate
  reason to only accept requests claiming to be localhost — inheriting that
  default here would silently reject all real traffic (DisallowedHost) while
  looking like a "tightened" setting. This raises at import time if
  DJANGO_ALLOWED_HOSTS isn't set, refusing to boot rather than booting into
  a broken or falsely-permissive state.
- CSRF_TRUSTED_ORIGINS follows the same rule, for the same reason:
  base.py's "http://localhost:5173" dev default has no business being
  trusted in production, and silently keeping it would mean CSRF
  protection is quietly weaker than it looks. Refuses to boot without an
  explicit CSRF_TRUSTED_ORIGINS instead.
"""

from decouple import config

from .base import *  # noqa

DEBUG = False

ALLOWED_HOSTS = config(
    "DJANGO_ALLOWED_HOSTS",
    cast=lambda v: [h.strip() for h in v.split(",") if h.strip()],
)

CSRF_TRUSTED_ORIGINS = config(
    "CSRF_TRUSTED_ORIGINS",
    cast=lambda v: [o.strip() for o in v.split(",") if o.strip()],
)

# Behind nginx TLS termination — tells Django the original request was
# HTTPS even though it arrives at gunicorn as plain HTTP from the proxy.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_SSL_REDIRECT = True

# HTTP Strict Transport Security — tells browsers to only ever contact this
# domain over HTTPS for the given duration, even if a user types http://.
# 1 year is the standard recommended value once you're confident TLS won't
# need to be temporarily disabled.
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# The internal Docker health check (see CI/CD deploy step) hits
# http://localhost:8000/health/ directly inside the container — no nginx,
# no TLS, no X-Forwarded-Proto header. Without this exemption,
# SECURE_SSL_REDIRECT above redirects that plain-HTTP request to
# https://localhost:8000/health/, which gunicorn doesn't serve (it only
# speaks plain HTTP on that port), causing the internal check to fail
# with an SSL handshake error. Real external traffic to /health/ still
# goes through nginx+TLS as normal — this only exempts the internal,
# same-container check.
SECURE_REDIRECT_EXEMPT = [r"^health/$"]