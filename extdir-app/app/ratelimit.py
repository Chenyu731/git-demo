import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request

from .config import get_settings

_hits: dict[str, deque] = defaultdict(deque)


def client_ip(request: Request) -> str:
    if get_settings().trust_proxy:
        xff = request.headers.get("x-forwarded-for", "")
        if xff:
            return xff.split(",")[0].strip()
    return request.client.host if request.client else "?"


def public_rate_limit(request: Request) -> None:
    limit = get_settings().public_rate_limit_per_min
    ip = client_ip(request)
    now = time.monotonic()
    q = _hits[ip]
    while q and now - q[0] > 60:
        q.popleft()
    if len(q) >= limit:
        raise HTTPException(status_code=429, detail="too many requests", headers={"Retry-After": "60"})
    q.append(now)


def reset() -> None:
    _hits.clear()
