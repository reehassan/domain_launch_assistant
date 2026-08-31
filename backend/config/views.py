import redis
from django.conf import settings
from django.db import connections
from django.db.utils import OperationalError
from django.http import JsonResponse


def health_check(request):
    """
    Lightweight, unauthenticated liveness/readiness check.

    Deliberately lives outside api/v1/ and is a plain Django view (not a
    DRF APIView) so REST_FRAMEWORK's DEFAULT_PERMISSION_CLASSES
    (IsAuthenticated) never applies to it — this has to be reachable with
    a bare GET and no token, since it's polled by the D5 deploy pipeline
    and any external uptime checker (D6).

    Checks the two things that actually matter for the demo staying up:
    the database, and Redis (Celery's broker/result backend, and what
    brand generation depends on). Returns 200 only if both are reachable,
    503 otherwise, so callers (curl -f, GitHub Actions, an uptime
    monitor) can tell success from failure by status code alone without
    parsing the body.
    """
    checks = {}
    healthy = True

    try:
        connections["default"].cursor()
        checks["database"] = "ok"
    except OperationalError:
        checks["database"] = "unreachable"
        healthy = False

    try:
        redis.Redis.from_url(settings.REDIS_URL, socket_connect_timeout=2).ping()
        checks["redis"] = "ok"
    except redis.exceptions.RedisError:
        checks["redis"] = "unreachable"
        healthy = False

    return JsonResponse(
        {"status": "ok" if healthy else "unhealthy", "checks": checks},
        status=200 if healthy else 503,
    )