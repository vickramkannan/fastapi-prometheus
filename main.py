
import time
import uuid
import logging
from datetime import datetime, timezone
from collections import deque

from fastapi import FastAPI, Request, Query
from fastapi.responses import Response
from prometheus_client import Counter, CollectorRegistry, generate_latest, CONTENT_TYPE_LATEST

EMAIL = "22f3000616@ds.study.iitm.ac.in"
START_TIME = time.monotonic()

app = FastAPI(title="Prometheus Instrumented API")

# Dedicated registry ensures the required counter is exposed.
registry = CollectorRegistry()
request_counter = Counter(
    "http_requests",
    "Total HTTP requests received",
    registry=registry,
)

# Keep recent structured log entries in memory.
recent_logs = deque(maxlen=1000)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("request_logger")


@app.middleware("http")
async def observe_requests(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())

    # Increment for every incoming request, including /metrics.
    request_counter.inc()

    status_code = 500
    level = "INFO"

    try:
        response = await call_next(request)
        status_code = response.status_code
        if status_code >= 500:
            level = "ERROR"
        response.headers["X-Request-ID"] = request_id
        return response
    except Exception:
        level = "ERROR"
        raise
    finally:
        entry = {
            "level": level,
            "ts": datetime.now(timezone.utc).isoformat(),
            "path": request.url.path,
            "request_id": request_id,
            "method": request.method,
            "status_code": status_code,
        }
        recent_logs.append(entry)
        logger.info("%s", __import__("json").dumps(entry))


@app.get("/work")
async def work(n: int = Query(default=1, ge=0, le=1000000)):
    # Perform n units of work.
    for _ in range(n):
        pass
    return {"email": EMAIL, "done": n}


@app.get("/metrics")
async def metrics():
    return Response(
        content=generate_latest(registry),
        media_type=CONTENT_TYPE_LATEST,
    )


@app.get("/healthz")
async def healthz():
    return {
        "status": "ok",
        "uptime_s": max(0.0, time.monotonic() - START_TIME),
    }


@app.get("/logs/tail")
async def logs_tail(limit: int = Query(default=100, ge=1, le=1000)):
    return list(recent_logs)[-limit:]
