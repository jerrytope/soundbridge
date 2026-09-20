import json
import logging
import time
import uuid


class SafeJsonFormatter(logging.Formatter):
    def format(self, record):
        # Request bodies, paths, cookies, email addresses and exception messages are excluded.
        data = {"level": record.levelname, "logger": record.name}
        for key in ("event", "request_id", "view", "status", "duration_ms"):
            if hasattr(record, key):
                data[key] = getattr(record, key)
        return json.dumps(data)


class RequestTelemetryMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.request_id = str(uuid.uuid4())
        started = time.monotonic()
        response = self.get_response(request)
        response["X-Request-ID"] = request.request_id
        if getattr(request, "user", None) and request.user.is_authenticated:
            response["Cache-Control"] = "no-store"
        match = getattr(request, "resolver_match", None)
        view = (
            match.func.__module__ + "." + match.func.__name__
            if match and hasattr(match.func, "__name__")
            else "unresolved"
        )
        logging.getLogger("soundbridge.requests").info(
            "request",
            extra={
                "event": "http.request",
                "request_id": request.request_id,
                "view": view,
                "status": response.status_code,
                "duration_ms": round((time.monotonic() - started) * 1000),
            },
        )
        return response
