"""Request middleware for ContextIngest API."""

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from core.rate_limit.ip_limiter import is_ip_rate_limited

_RATE_LIMITED_PREFIXES = ("/v1/query", "/v1/feedback")


class IPRateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if any(path.startswith(p) for p in _RATE_LIMITED_PREFIXES):
            if is_ip_rate_limited(request):
                return JSONResponse(
                    status_code=429,
                    content={"message": "Too many requests. Please try again later."},
                    headers={"Retry-After": "60"},
                )
        return await call_next(request)
