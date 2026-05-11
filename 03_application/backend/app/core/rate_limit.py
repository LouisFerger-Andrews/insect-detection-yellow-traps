from __future__ import annotations

from collections import defaultdict, deque
from time import monotonic
from threading import Lock

from fastapi import HTTPException, Request, status

AUTH_RATE_LIMIT_ATTEMPTS = 8
AUTH_RATE_LIMIT_WINDOW_SECONDS = 60

_attempts: dict[str, deque[float]] = defaultdict(deque)
_lock = Lock()


def _client_host(request: Request | None) -> str:
    if request is None or request.client is None:
        return 'direct-call'
    forwarded = request.headers.get('x-forwarded-for')
    if forwarded:
        return forwarded.split(',', 1)[0].strip()
    return request.client.host


def check_rate_limit(
    request: Request | None,
    *,
    scope: str,
    identifier: str,
    limit: int = AUTH_RATE_LIMIT_ATTEMPTS,
    window_seconds: int = AUTH_RATE_LIMIT_WINDOW_SECONDS,
) -> None:
    key = f'{scope}:{_client_host(request)}:{identifier.lower().strip()}'
    now = monotonic()
    with _lock:
        window = _attempts[key]
        while window and now - window[0] > window_seconds:
            window.popleft()
        if len(window) >= limit:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail='Too many attempts. Try again later.',
                headers={'Retry-After': str(window_seconds)},
            )
        window.append(now)


def clear_rate_limit_state() -> None:
    with _lock:
        _attempts.clear()
