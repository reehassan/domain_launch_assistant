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
"""

from decouple import config

from .base import *  # noqa

DEBUG = False

ALLOWED_HOSTS = config(
    "DJANGO_ALLOWED_HOSTS",
    cast=lambda v: [h.strip() for h in v.split(",") if h.strip()],
)