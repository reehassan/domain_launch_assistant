"""
Django settings for config project.
"""

from datetime import timedelta
from pathlib import Path
from urllib.parse import urlparse

import dj_database_url
from decouple import config

BASE_DIR = Path(__file__).resolve().parent.parent.parent

SECRET_KEY = config("DJANGO_SECRET_KEY")
DEBUG = config("DEBUG", default=False, cast=bool)

ALLOWED_HOSTS = config(
    "DJANGO_ALLOWED_HOSTS",
    default="localhost,127.0.0.1",
    cast=lambda v: [h.strip() for h in v.split(",") if h.strip()],
)

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    "corsheaders",

    "domain_launch_assistant.users.apps.UsersConfig",
    "domain_launch_assistant.accounts.apps.AccountsConfig",
    "domain_launch_assistant.launches.apps.LaunchesConfig",
    "domain_launch_assistant.brands.apps.BrandsConfig",
    "domain_launch_assistant.domains.apps.DomainsConfig",
    "domain_launch_assistant.dns.apps.DnsConfig",
    "domain_launch_assistant.tasks.apps.TasksConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": dj_database_url.parse(config("DATABASE_URL"))
}

AUTH_USER_MODEL = "users.User"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
    "EXCEPTION_HANDLER": "domain_launch_assistant.utils.exceptions.custom_exception_handler",
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {"anon": "20/min", "user": "60/min"},
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=30),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
}

CORS_ALLOWED_ORIGINS = config(
    "CORS_ALLOWED_ORIGINS",
    default="http://localhost:5173",
    cast=lambda v: [o.strip() for o in v.split(",") if o.strip()],
)

CSRF_TRUSTED_ORIGINS = config(
    "CSRF_TRUSTED_ORIGINS",
    default="http://localhost:5173",
    cast=lambda v: [o.strip() for o in v.split(",") if o.strip()],
)

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

# EMAIL_BACKEND is deprecated as of Django 6.1 in favor of MAILERS.
MAILERS = {
    "default": {
        "BACKEND": "django.core.mail.backends.console.EmailBackend",
    },
}

REDIS_URL = config("REDIS_URL")

GEMINI_API_KEY = config("GEMINI_API_KEY")
GEMINI_MODEL = config("GEMINI_MODEL")

BRAND_GENERATION_DEFAULT_COUNT = config("BRAND_GENERATION_DEFAULT_COUNT", default=5, cast=int)

NAMECOM_USERNAME = config("NAMECOM_USERNAME")
NAMECOM_API_TOKEN = config("NAMECOM_API_TOKEN")
NAMECOM_BASE_URL = config("NAMECOM_BASE_URL", default="https://api.name.com/core/v1")
NAMECOM_MAX_RETRIES = config("NAMECOM_MAX_RETRIES", default=3, cast=int)
NAMECOM_RETRY_BACKOFF_BASE = config("NAMECOM_RETRY_BACKOFF_BASE", default=0.5, cast=float)
DOMAIN_FRESHNESS_THRESHOLD_SECONDS = config(
    "DOMAIN_FRESHNESS_THRESHOLD_SECONDS", default=300, cast=int
)

NAMECOM_TEST_USERNAME = config("NAMECOM_TEST_USERNAME")
NAMECOM_TEST_API_TOKEN = config("NAMECOM_TEST_API_TOKEN")
NAMECOM_TEST_BASE_URL = config(
    "NAMECOM_TEST_BASE_URL", default="https://api.dev.name.com/core/v1"
)
# Derived from NAMECOM_TEST_BASE_URL so it can't drift out of sync.
NAMECOM_SANDBOX_HOST = urlparse(NAMECOM_TEST_BASE_URL).hostname

NAMECOM_TEST_CONTACT_FIRST_NAME = config("NAMECOM_TEST_CONTACT_FIRST_NAME", default="Demo")
NAMECOM_TEST_CONTACT_LAST_NAME = config("NAMECOM_TEST_CONTACT_LAST_NAME", default="Registrant")
NAMECOM_TEST_CONTACT_ADDRESS1 = config(
    "NAMECOM_TEST_CONTACT_ADDRESS1", default="123 Demo Street"
)
NAMECOM_TEST_CONTACT_CITY = config("NAMECOM_TEST_CONTACT_CITY", default="Denver")
NAMECOM_TEST_CONTACT_STATE = config("NAMECOM_TEST_CONTACT_STATE", default="CO")
NAMECOM_TEST_CONTACT_ZIP = config("NAMECOM_TEST_CONTACT_ZIP", default="80202")
NAMECOM_TEST_CONTACT_COUNTRY = config("NAMECOM_TEST_CONTACT_COUNTRY", default="US")
NAMECOM_TEST_CONTACT_EMAIL = config(
    "NAMECOM_TEST_CONTACT_EMAIL", default="demo-registrant@example.com"
)
NAMECOM_TEST_CONTACT_PHONE = config("NAMECOM_TEST_CONTACT_PHONE", default="+13035555555")

CELERY_BROKER_URL = REDIS_URL
CELERY_RESULT_BACKEND = REDIS_URL
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE

GOOGLE_CLIENT_ID = config("GOOGLE_CLIENT_ID")