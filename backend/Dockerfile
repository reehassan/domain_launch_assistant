FROM python:3.12-slim AS builder

# uv is distributed as a static binary — copy it in rather than pip-installing
# it, per astral's recommended pattern. Only needed in this stage; the
# runtime stage never gets uv copied into it.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

# Install dependencies first, separately from app code, so this layer is
# cached and only rebuilds when pyproject.toml/uv.lock actually change.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Now copy the rest of the source and finish the sync (installs the project
# itself, not just its deps).
COPY . .
RUN uv sync --frozen --no-dev

FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Everything needed to run — the finished venv and the app source — comes
# from the builder stage. uv itself, uv's download cache, and any
# intermediate layers from the two `uv sync` steps above are NOT part of
# this runtime stage and never end up in the final image.
COPY --from=builder /app /app
ENV PATH="/app/.venv/bin:${PATH}"

# This IS meant to persist into the running container — it's not a secret,
# and we want config.settings.production to be the real default so nobody
# has to remember to pass it at deploy time.
ENV DJANGO_SETTINGS_MODULE=config.settings.production

# collectstatic imports the full settings module, which means every
# no-default python-decouple config() call in base.py/production.py must
# resolve just to import it — even though collectstatic itself never
# touches the database or any external API. These values are scoped to
# THIS COMMAND ONLY (not an ENV instruction), so they never become part of
# the image's runtime environment or its default config. A container run
# without every one of these set at runtime WILL fail to boot — that's
# intentional, not a bug; see config/settings/production.py.
# CSRF_TRUSTED_ORIGINS needs a scheme (Django rejects bare hostnames for
# this setting), unlike DJANGO_ALLOWED_HOSTS above it.
RUN DJANGO_SECRET_KEY=build-time-placeholder \
    DJANGO_ALLOWED_HOSTS=build-time-placeholder \
    DATABASE_URL=postgres://build:build@localhost:5432/build \
    REDIS_URL=redis://localhost:6379/0 \
    GEMINI_API_KEY=build-time-placeholder \
    GEMINI_MODEL=build-time-placeholder \
    NAMECOM_USERNAME=build-time-placeholder \
    NAMECOM_API_TOKEN=build-time-placeholder \
    NAMECOM_TEST_USERNAME=build-time-placeholder \
    NAMECOM_TEST_API_TOKEN=build-time-placeholder \
    GOOGLE_CLIENT_ID=build-time-placeholder \
    CSRF_TRUSTED_ORIGINS=http://build-time-placeholder \
    python manage.py collectstatic --noinput

RUN chmod +x docker-entrypoint.sh

# Non-root user
RUN addgroup --system app \
    && adduser --system --ingroup app --home /home/app app \
    && chown -R app:app /app
USER app

EXPOSE 8000
ENTRYPOINT ["./docker-entrypoint.sh"]
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000"]