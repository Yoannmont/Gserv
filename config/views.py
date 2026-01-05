import redis
from django.conf import settings
from django.db import connections
from django.db.utils import OperationalError
from django.http import JsonResponse


def health(request):
    status = {"database": False, "redis": False}

    try:
        connections["default"].cursor()
        status["database"] = True
    except OperationalError:
        status["database"] = False

    try:
        r = redis.Redis(host=settings.CHANNEL_HOST, port=settings.CHANNEL_PORT, db=1)
        r.ping()
        status["redis"] = True
    except redis.ConnectionError:
        status["redis"] = False

    status_code = 200 if all(status.values()) else 503
    return JsonResponse(status, status=status_code)
