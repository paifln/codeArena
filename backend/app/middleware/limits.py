from slowapi import Limiter
from slowapi.util import get_remote_address
from fastapi import HTTPException


def request_key(request):
    # One classroom may share a proxy/IP. Signed account IDs keep separate users
    # from consuming each other's ordinary request budget. Authentication endpoints
    # retain IP limits; invalid/expired cookies cannot create arbitrary buckets.
    if not (request.url.path.startswith("/api/v1/auth/") and request.method not in ("GET", "HEAD", "OPTIONS")):
        from ..security import decode_token

        raw = request.cookies.get("ca_session")
        if raw:
            try:
                return "account:" + decode_token(raw, "access")["sub"]
            except HTTPException:
                pass
    return "ip:" + get_remote_address(request)


# Single API process, as required by the SQLite deployment architecture.
limiter = Limiter(key_func=request_key, application_limits=["100/minute"])
