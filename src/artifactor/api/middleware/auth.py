"""Optional API key authentication middleware."""

from __future__ import annotations

import hmac

from fastapi import Request, Response
from starlette.middleware.base import (
    BaseHTTPMiddleware,
    RequestResponseEndpoint,
)
from starlette.responses import JSONResponse

from artifactor.constants import (
    AUTH_EXEMPT_PATHS,
    AUTH_EXEMPT_PREFIXES,
)


class ApiKeyMiddleware(BaseHTTPMiddleware):
    """Check X-API-Key header if api_key is configured.

    If ``Settings.api_key`` is empty, all requests pass through.
    Health endpoints are always exempt.
    """

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        path = request.url.path

        # Exempt paths and prefixes are always public
        if path in AUTH_EXEMPT_PATHS or path.startswith(
            AUTH_EXEMPT_PREFIXES
        ):
            return await call_next(request)

        settings = request.app.state.settings

        # If no API key configured, skip auth
        if not settings.api_key:
            return await call_next(request)

        # Check header
        provided = request.headers.get("X-API-Key", "")
        if not hmac.compare_digest(provided, settings.api_key):
            return JSONResponse(
                status_code=401,
                content={
                    "success": False,
                    "error": "Invalid or missing API key",
                    "data": None,
                    "metadata": {},
                },
            )

        return await call_next(request)
