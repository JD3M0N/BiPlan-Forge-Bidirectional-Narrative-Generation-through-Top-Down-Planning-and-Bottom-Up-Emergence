"""The guards a local web app that spends quota needs.

StageCraft listens on localhost, but any page the person has open in the same browser can send
requests to localhost. Three things keep those pages out:

- every request that changes something must carry the X-StageCraft header, and a browser only
  lets another origin send a custom header after a CORS preflight this app never answers;
- the Host header must name this machine, which defeats DNS rebinding;
- a strict content security policy, so nothing but this app's own files ever runs in its page.
"""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

HEADER = "x-stagecraft"
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
CONTENT_SECURITY_POLICY = (
    "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
    "media-src 'self'; connect-src 'self'; font-src 'self'; object-src 'none'; "
    "base-uri 'none'; form-action 'self'; frame-ancestors 'none'"
)


class GuardMiddleware(BaseHTTPMiddleware):
    """Refuse foreign hosts and header-less writes, and stamp the security headers."""

    def __init__(self, app, allowed_hosts: tuple[str, ...]) -> None:
        """Remember which host names this app answers to."""
        super().__init__(app)
        self.allowed_hosts = frozenset(host.lower() for host in allowed_hosts)

    async def dispatch(self, request: Request, call_next) -> Response:
        """Check one request before it reaches a route, and harden its response."""
        host = (request.headers.get("host") or "").rsplit(":", 1)[0].strip("[]").lower()
        if host not in self.allowed_hosts:
            return JSONResponse({"detail": "Host no permitido."}, status_code=400)
        if request.method not in SAFE_METHODS and request.headers.get(HEADER) != "1":
            return JSONResponse(
                {"detail": "Falta la cabecera X-StageCraft: la petición no viene de StageCraft."},
                status_code=403,
            )
        response = await call_next(request)
        response.headers["Content-Security-Policy"] = CONTENT_SECURITY_POLICY
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Frame-Options"] = "DENY"
        return response
